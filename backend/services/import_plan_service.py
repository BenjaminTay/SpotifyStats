"""Read-only orchestration for streaming-import relationship plans."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Literal

import pandas as pd

from backend.core.db import get_db
from backend.domains.imports.incremental import (
    FINGERPRINT_VERSION,
    FingerprintRecord,
    ImportCoverage,
    ImportPlan,
    build_import_plan,
    dataset_digest,
)
from backend.domains.imports.source_inspector import inspect_data_sources_for_planning
from backend.domains.playback.logical_timeline import billboard_week_for_timestamps
from backend.domains.settings.repository import SettingsRepository

ImportRequestedMode = Literal["auto", "append", "replace"]


@dataclass(frozen=True)
class StreamingImportAssessment:
    """Internal evidence bundle; only ``report`` may cross the API boundary."""

    report: dict[str, Any]
    plan: ImportPlan
    baseline_status: str
    existing_account_identity_hash: str | None
    incoming_account_identity_hash: str | None


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _account_identity_hash(account_dir: str | os.PathLike[str]) -> str | None:
    """Hash the stable Spotify username without exposing it in API output."""
    path = os.path.join(os.fspath(account_dir), "UserAttributes.json")
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    username = payload.get("username")
    if not isinstance(username, str) or not username.strip():
        return None
    canonical = username.strip().casefold().encode("utf-8")
    return hashlib.sha256(b"spotifystats-account-v1\0" + canonical).hexdigest()


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
        is not None
    )


def _play_columns(conn: sqlite3.Connection) -> set[str]:
    if not _table_exists(conn, "plays"):
        return set()
    return {str(row[1]) for row in conn.execute("PRAGMA table_info(plays)").fetchall()}


def _existing_date_range(conn: sqlite3.Connection) -> tuple[str | None, str | None, int]:
    if not _table_exists(conn, "plays"):
        return None, None, 0
    row = conn.execute("SELECT MIN(ts), MAX(ts), COUNT(*) FROM plays").fetchone()
    if row is None:
        return None, None, 0
    return (
        str(row[0]) if row[0] else None,
        str(row[1]) if row[1] else None,
        int(row[2] or 0),
    )


def _load_existing_baseline(
    conn: sqlite3.Connection,
) -> tuple[list[FingerprintRecord] | None, str, str | None]:
    """Return records, baseline status, and the persisted account hash."""
    columns = _play_columns(conn)
    required = {
        "content_type",
        "source_fingerprint",
        "source_fingerprint_version",
        "import_generation_id",
        "ts",
    }
    if not required.issubset(columns) or not _table_exists(conn, "playback_import_state"):
        return None, "missing", None

    state = conn.execute(
        """SELECT active_generation_id, account_identity_hash,
                  fingerprint_version, dataset_digest, record_count
           FROM playback_import_state WHERE state_id=1"""
    ).fetchone()
    if state is None:
        return None, "missing", None
    account_hash = str(state[1]) if state[1] else None
    state_version = int(state[2]) if state[2] is not None else None
    if state_version is not None and state_version != FINGERPRINT_VERSION:
        return None, "incompatible", account_hash

    first_ts, latest_ts, play_count = _existing_date_range(conn)
    del first_ts, latest_ts
    if play_count == 0:
        if state_version == FINGERPRINT_VERSION and state[3]:
            return [], "ready", account_hash
        return None, "missing", account_hash

    if not state[0] or state_version != FINGERPRINT_VERSION or not state[3]:
        return None, "missing", account_hash
    if int(state[4] or 0) != play_count:
        return None, "incompatible", account_hash

    rows = conn.execute(
        """SELECT content_type, source_fingerprint, source_fingerprint_version, ts
           FROM plays ORDER BY play_id"""
    ).fetchall()
    if any(row[1] is None or row[2] is None or int(row[2]) != FINGERPRINT_VERSION for row in rows):
        return None, "missing", account_hash
    records = [
        FingerprintRecord(
            source_type=str(row[0]),
            fingerprint=str(row[1]),
            timestamp=_parse_timestamp(row[3]),
        )
        for row in rows
    ]
    if len({record.identity for record in records}) != play_count:
        return None, "incompatible", account_hash
    if dataset_digest(records) != str(state[3]):
        return None, "incompatible", account_hash
    return records, "ready", account_hash


def _date_range(first: datetime | None, latest: datetime | None) -> dict[str, str | None] | None:
    if first is None and latest is None:
        return None
    return {
        "first_date": first.date().isoformat() if first is not None else None,
        "last_date": latest.date().isoformat() if latest is not None else None,
    }


def _account_identity_status(existing_hash: str | None, incoming_hash: str | None) -> str:
    if incoming_hash is None:
        return "not_provided"
    if existing_hash is None:
        return "unknown"
    return "matched" if existing_hash == incoming_hash else "mismatched"


def _changed_timestamps(
    plan: ImportPlan,
    incoming_records: list[FingerprintRecord],
    existing_records: list[FingerprintRecord] | None,
) -> list[datetime]:
    incoming = {record.identity: record.timestamp for record in incoming_records}
    existing = {record.identity: record.timestamp for record in existing_records or []}
    timestamps = [incoming.get(identity) for identity in plan.added]
    timestamps.extend(existing.get(identity) for identity in plan.removed)
    return [value for value in timestamps if value is not None]


def _affected_scope(
    conn: sqlite3.Connection,
    timestamps: list[datetime],
) -> tuple[int, int]:
    if not timestamps:
        return 0, 0
    years = {timestamp.year for timestamp in timestamps}
    try:
        settings = SettingsRepository(conn).load_all()
        weeks = billboard_week_for_timestamps(
            pd.Series(timestamps),
            week_start_dow=int(settings.get("bb_week_start_dow", 4)),
            week_start_hour=int(settings.get("bb_week_start_hour", 0)),
        )
        week_count = int(weeks.nunique())
    except sqlite3.OperationalError:
        week_count = 0
    return week_count, len(years)


def _planned_actions(plan: ImportPlan, requested_mode: ImportRequestedMode) -> list[str]:
    relation = plan.relation.value
    if relation == "baseline_required":
        primary = "需要一次完整导入建立持久化记录指纹基线"
    elif relation == "identical":
        primary = "已证明输入记录集合与当前活动数据集相同"
    elif relation in {"snapshot_superset", "delta_tail"}:
        primary = "已证明可只处理新增播放记录"
    elif relation == "reconciled_snapshot":
        primary = "完整快照包含历史增删，需要生成精确 ChangeSet"
    else:
        primary = "输入关系证据不足，执行前必须确认追加或替换语义"
    if requested_mode == "append" and relation == "baseline_required":
        execution = "当前库没有完整指纹基线，Phase B 将阻断追加；请先完整替换"
    elif requested_mode == "append" and relation not in {
        "identical",
        "snapshot_superset",
        "delta_tail",
    }:
        execution = "Phase B 不能证明该输入可安全追加，将阻断写入"
    elif requested_mode == "replace":
        execution = "明确选择完整替换；写入前仍会创建数据库快照"
    elif relation == "identical":
        execution = "Phase B 将跳过数据库快照、播放写入和派生数据重建"
    elif relation in {"snapshot_superset", "delta_tail"}:
        execution = "Phase B 只追加新增播放；派生维护暂时仍使用完整路径"
    elif relation == "baseline_required" and plan.existing_count > 0:
        execution = "旧库无法证明输入包覆盖全部历史；确认后才会完整替换并建立基线"
    elif relation == "baseline_required":
        execution = "空库将执行一次完整导入以建立持久化指纹基线"
    else:
        execution = "Phase B 不会在证据不足时自动追加；请明确选择完整替换"
    return [primary, execution]


def _confirmation_token(
    report: dict[str, Any],
    plan: ImportPlan,
    *,
    existing_account_hash: str | None,
    incoming_account_hash: str | None,
) -> str:
    """Bind a confirmation to the exact source and active-dataset evidence."""
    payload = {
        "schema_version": "streaming-import-confirmation-v1",
        "source_report": report,
        "incoming_digest": plan.incoming_digest,
        "previous_digest": plan.previous_digest,
        "existing_count": plan.existing_count,
        "incoming_count": plan.incoming_count,
        "existing_account_hash": existing_account_hash,
        "incoming_account_hash": incoming_account_hash,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def assess_streaming_import(
    streaming_dir: str | os.PathLike[str],
    account_dir: str | os.PathLike[str],
    *,
    requested_mode: ImportRequestedMode = "auto",
    conn: sqlite3.Connection | None = None,
) -> StreamingImportAssessment:
    """Build the public report and retain private execution evidence."""
    report = inspect_data_sources_for_planning(streaming_dir, account_dir)
    internal_records = report.pop("_streaming_records", [])
    incoming_records = [
        FingerprintRecord(
            source_type=str(item["source_type"]),
            fingerprint=str(item["fingerprint"]),
            timestamp=_parse_timestamp(item.get("timestamp")),
        )
        for item in internal_records
    ]

    owns_connection = conn is None
    active_conn = conn or get_db(readonly=True)
    try:
        existing_records, baseline_status, existing_account_hash = _load_existing_baseline(
            active_conn
        )
        incoming_account_hash = _account_identity_hash(account_dir)
        existing_first, existing_latest, existing_count = _existing_date_range(active_conn)
        coverage = {
            "auto": ImportCoverage.UNKNOWN,
            "append": ImportCoverage.DELTA,
            "replace": ImportCoverage.SNAPSHOT,
        }[requested_mode]
        plan = build_import_plan(
            incoming_records,
            existing_records=existing_records,
            existing_account_identity_hash=existing_account_hash,
            incoming_account_identity_hash=incoming_account_hash,
            coverage=coverage,
        )
        if plan.relation.value == "baseline_required" and existing_count > 0:
            # The legacy rows cannot be matched exactly, but their count still
            # matters for both the audit record and the destructive-write gate.
            plan = replace(
                plan,
                existing_count=existing_count,
                requires_confirmation=True,
            )
        changed_timestamps = _changed_timestamps(plan, incoming_records, existing_records)
        affected_weeks, affected_years = _affected_scope(active_conn, changed_timestamps)
    finally:
        if owns_connection:
            active_conn.close()

    legacy_replace_confirmation = plan.relation.value == "baseline_required" and existing_count > 0
    confirmation_token = _confirmation_token(
        report,
        plan,
        existing_account_hash=existing_account_hash,
        incoming_account_hash=incoming_account_hash,
    )
    report.update(
        account_identity_status=_account_identity_status(
            existing_account_hash,
            incoming_account_hash,
        ),
        fingerprint_baseline_status=baseline_status,
        detected_relation=plan.relation.value,
        requested_mode=requested_mode,
        requires_confirmation=plan.requires_confirmation or legacy_replace_confirmation,
        existing_record_count=existing_count,
        incoming_record_count=plan.incoming_count,
        unchanged_record_count=plan.unchanged_count,
        added_record_count=plan.added_count,
        removed_record_count=plan.removed_count,
        existing_date_range=(
            {
                "first_date": existing_first[:10] if existing_first else None,
                "last_date": existing_latest[:10] if existing_latest else None,
            }
            if existing_first or existing_latest
            else None
        ),
        incoming_date_range=_date_range(plan.incoming_first_ts, plan.incoming_latest_ts),
        affected_weeks_count=affected_weeks,
        affected_years_count=affected_years,
        planned_actions=_planned_actions(plan, requested_mode),
        estimated_strategy=(
            "full" if requested_mode == "replace" else plan.estimated_strategy.value
        ),
    )
    report["confirmation_token"] = confirmation_token
    return StreamingImportAssessment(
        report=report,
        plan=plan,
        baseline_status=baseline_status,
        existing_account_identity_hash=existing_account_hash,
        incoming_account_identity_hash=incoming_account_hash,
    )


def build_streaming_import_preflight(
    streaming_dir: str | os.PathLike[str],
    account_dir: str | os.PathLike[str],
    *,
    requested_mode: ImportRequestedMode = "auto",
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Combine source inspection and the persisted baseline without writes."""
    return assess_streaming_import(
        streaming_dir,
        account_dir,
        requested_mode=requested_mode,
        conn=conn,
    ).report
