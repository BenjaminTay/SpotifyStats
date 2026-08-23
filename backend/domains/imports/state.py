"""Transactional persistence helpers for streaming-import generations.

The helpers in this module never commit.  Import orchestration owns the
transaction that publishes playback facts, the active generation state, and
the corresponding terminal run record atomically.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from backend.domains.imports.change_set import PlaybackChangeSet
from backend.domains.imports.incremental import (
    FINGERPRINT_VERSION,
    FingerprintRecord,
    ImportPlan,
    dataset_digest,
)

PlaybackImportRunStatus = Literal[
    "maintenance_pending",
    "recovery_blocked",
    "success",
    "noop",
    "needs_confirmation",
]
_ALLOWED_RUN_STATUSES = frozenset(
    {"maintenance_pending", "recovery_blocked", "success", "noop", "needs_confirmation"}
)


class FingerprintBaselineError(ValueError):
    """The current plays table cannot form one complete fingerprint baseline."""


@dataclass(frozen=True)
class PlaybackDatasetSummary:
    """Deterministic identity and time coverage of the current plays table."""

    fingerprint_version: int
    dataset_digest: str
    record_count: int
    first_ts: str | None
    latest_ts: str | None


def summarise_current_playback_dataset(
    conn: sqlite3.Connection,
    *,
    fingerprint_version: int = FINGERPRINT_VERSION,
) -> PlaybackDatasetSummary:
    """Compute the exact fingerprint-set summary for the current plays rows.

    A mixed legacy/versioned table fails closed instead of publishing a false
    baseline.  The baseline import must populate every row with the same
    supported fingerprint version before calling this helper.
    """

    rows = conn.execute(
        """SELECT content_type, source_fingerprint,
                  source_fingerprint_version, ts
           FROM plays ORDER BY play_id"""
    ).fetchall()
    records: list[FingerprintRecord] = []
    timestamps: list[str] = []
    for row in rows:
        source_type = row[0]
        fingerprint = row[1]
        version = row[2]
        if (
            source_type is None
            or fingerprint is None
            or version is None
            or int(version) != fingerprint_version
        ):
            raise FingerprintBaselineError(
                "all plays must have a source fingerprint at the active version"
            )
        records.append(
            FingerprintRecord(
                source_type=str(source_type),
                fingerprint=str(fingerprint),
            )
        )
        if row[3] is not None:
            timestamps.append(str(row[3]))

    if len({record.identity for record in records}) != len(records):
        raise FingerprintBaselineError("plays contains duplicate source fingerprints")

    return PlaybackDatasetSummary(
        fingerprint_version=fingerprint_version,
        dataset_digest=dataset_digest(records),
        record_count=len(records),
        first_ts=min(timestamps) if timestamps else None,
        latest_ts=max(timestamps) if timestamps else None,
    )


def publish_playback_import_state(
    conn: sqlite3.Connection,
    *,
    generation_id: str,
    account_identity_hash: str | None,
    relation: str,
    strategy: str,
    summary: PlaybackDatasetSummary | None = None,
    updated_at: datetime | None = None,
) -> PlaybackDatasetSummary:
    """Publish the singleton active playback generation in the caller transaction."""

    if not generation_id.strip():
        raise ValueError("generation_id must not be empty")
    active_summary = summary or summarise_current_playback_dataset(conn)
    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(playback_import_state)")}
    revision_assignment = (
        ", playback_revision=playback_import_state.playback_revision+1"
        if "playback_revision" in columns
        else ""
    )
    conn.execute(
        f"""INSERT INTO playback_import_state(
               state_id, active_generation_id, account_identity_hash,
               fingerprint_version, dataset_digest, record_count,
               first_ts, latest_ts, last_relation, last_strategy, updated_at
           ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(state_id) DO UPDATE SET
               active_generation_id=excluded.active_generation_id,
               account_identity_hash=excluded.account_identity_hash,
               fingerprint_version=excluded.fingerprint_version,
               dataset_digest=excluded.dataset_digest,
               record_count=excluded.record_count,
               first_ts=excluded.first_ts,
               latest_ts=excluded.latest_ts,
               last_relation=excluded.last_relation,
               last_strategy=excluded.last_strategy,
               updated_at=excluded.updated_at
               {revision_assignment}""",
        (
            generation_id,
            account_identity_hash,
            active_summary.fingerprint_version,
            active_summary.dataset_digest,
            active_summary.record_count,
            active_summary.first_ts,
            active_summary.latest_ts,
            relation,
            strategy,
            _isoformat(updated_at or datetime.now(timezone.utc)),
        ),
    )
    return active_summary


def record_playback_import_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    requested_mode: str,
    status: PlaybackImportRunStatus,
    plan: ImportPlan,
    earliest_changed_ts: datetime | None = None,
    latest_changed_ts: datetime | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    error_code: str | None = None,
    change_set: PlaybackChangeSet | None = None,
) -> None:
    """Record one planning/import outcome without committing it.

    ``plan_json`` is produced internally from a fixed allow-list of aggregate
    fields.  It never serialises source records, file payloads, account names,
    or caller-provided arbitrary dictionaries.
    """

    if not run_id.strip():
        raise ValueError("run_id must not be empty")
    if status not in _ALLOWED_RUN_STATUSES:
        raise ValueError(f"unsupported playback import run status: {status}")
    now = datetime.now(timezone.utc)
    existing = conn.execute(
        "SELECT started_at FROM playback_import_runs WHERE run_id=?",
        (run_id,),
    ).fetchone()
    if existing is not None:
        conn.execute("DELETE FROM playback_import_runs WHERE run_id=?", (run_id,))
    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(playback_import_runs)")}
    names = [
        "run_id",
        "requested_mode",
        "detected_relation",
        "status",
        "incoming_digest",
        "previous_digest",
        "incoming_count",
        "unchanged_count",
        "added_count",
        "removed_count",
        "first_ts",
        "latest_ts",
        "earliest_changed_ts",
        "latest_changed_ts",
        "plan_json",
        "started_at",
        "completed_at",
        "error_code",
    ]
    values: list[object] = [
        run_id,
        requested_mode,
        plan.relation.value,
        status,
        plan.incoming_digest,
        plan.previous_digest,
        plan.incoming_count,
        plan.unchanged_count,
        plan.added_count,
        plan.removed_count,
        _isoformat(plan.incoming_first_ts),
        _isoformat(plan.incoming_latest_ts),
        _isoformat(earliest_changed_ts) or (change_set.earliest_changed_ts if change_set else None),
        _isoformat(latest_changed_ts) or (change_set.latest_changed_ts if change_set else None),
        _compact_plan_json(plan),
        (
            _isoformat(started_at)
            if started_at is not None
            else (str(existing[0]) if existing and existing[0] else _isoformat(now))
        ),
        None if status == "maintenance_pending" else _isoformat(completed_at or now),
        error_code,
    ]
    if "change_set_json" in columns:
        names.append("change_set_json")
        values.append(
            json.dumps(
                change_set.to_dict(),
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            if change_set is not None
            else None
        )
    placeholders = ", ".join("?" for _ in names)
    conn.execute(
        f"INSERT INTO playback_import_runs({', '.join(names)}) VALUES ({placeholders})",
        values,
    )


def compare_and_set_playback_import_run_status(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    expected_status: PlaybackImportRunStatus,
    status: PlaybackImportRunStatus,
    error_code: str | None = None,
) -> bool:
    """Transition one durable run without replacing its recovery evidence."""

    if expected_status not in _ALLOWED_RUN_STATUSES or status not in _ALLOWED_RUN_STATUSES:
        raise ValueError("unsupported playback import run status transition")
    completed_at = (
        None if status == "maintenance_pending" else _isoformat(datetime.now(timezone.utc))
    )
    cursor = conn.execute(
        """UPDATE playback_import_runs
           SET status=?, completed_at=?, error_code=?
           WHERE run_id=? AND status=?""",
        (status, completed_at, error_code, run_id, expected_status),
    )
    return cursor.rowcount == 1


def _compact_plan_json(plan: ImportPlan) -> str:
    payload = {
        "schema_version": "playback_import_plan_summary_v1",
        "detected_relation": plan.relation.value,
        "estimated_strategy": plan.estimated_strategy.value,
        "requires_confirmation": plan.requires_confirmation,
        "existing_count": plan.existing_count,
        "incoming_count": plan.incoming_count,
        "unchanged_count": plan.unchanged_count,
        "added_count": plan.added_count,
        "removed_count": plan.removed_count,
    }
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
