#!/usr/bin/env python3
"""Validate Phase D incremental derived data on disposable real-DB copies.

The source database is always opened read-only and copied with SQLite Online
Backup.  Every mutation is confined to a newly-created work directory outside
the repository.  The default work directory is removed in ``finally``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core import db as db_mod  # noqa: E402

REPORT_SCHEMA_VERSION = "phase_d_real_db_acceptance_v1"
BASE_GENERATION_ID = "phase-d-benchmark-base"
APPEND_GENERATION_ID = "phase-d-benchmark-append"
BILLBOARD_TABLES = (
    "agg_weekly_tracks",
    "agg_weekly_albums",
    "agg_weekly_track_sources",
    "agg_weekly_artists",
)
SEARCH_PAYLOAD_COLUMNS = (
    "entity_key",
    "play_events",
    "total_ms",
    "peak_position",
    "peak_weeks",
    "weeks_on_chart",
    "weeks_at_no1",
    "power_score",
    "power_rank",
    "first_week",
    "latest_week",
    "first_peak_week",
)
EXPECTED_VARIANTS = frozenset(
    (merge_level, dynamic_threshold)
    for merge_level in (2, 3)
    for dynamic_threshold in (False, True)
)
PRIVACY_REPORT = {
    "database_path_emitted": False,
    "entity_content_emitted": False,
    "listening_history_rows_emitted": False,
}


class AcceptanceError(RuntimeError):
    """A fail-closed Phase D acceptance violation."""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare Phase D Billboard partition and search shared-frame builders "
            "with their full-rebuild references on disposable database copies"
        )
    )
    parser.add_argument(
        "--source-db",
        type=Path,
        default=Path(db_mod.DB_PATH),
        help="Read-only source database; it is never migrated or written",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional durable JSON report path (stdout is always supported)",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        help="New, non-existing work directory outside the repository",
    )
    parser.add_argument(
        "--keep-workdir",
        action="store_true",
        help="Preserve private database copies for debugging",
    )
    parser.add_argument(
        "--skip-search",
        action="store_true",
        help="Run only the Billboard equivalence gate; overall status is partial",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=1,
        help="Search A/B trials; use 3 or more for a performance conclusion",
    )
    parser.add_argument(
        "--append-gap-seconds",
        type=float,
        default=1.0,
        help="Idle gap between the old tail and synthetic appended play",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the machine-readable report instead of a short summary",
    )
    parser.add_argument(
        "--_worker-strategy",
        choices=("shared", "ordinary"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--_worker-db", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--_worker-generation", help=argparse.SUPPRESS)
    parser.add_argument("--_worker-report", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.trials < 1:
        parser.error("--trials must be at least 1")
    if args.trials > 20:
        parser.error("--trials must not exceed 20")
    if args.append_gap_seconds < 0:
        parser.error("--append-gap-seconds must be non-negative")
    worker_values = (args._worker_db, args._worker_generation, args._worker_report)
    if args._worker_strategy and any(value is None for value in worker_values):
        parser.error("internal worker mode requires database, generation, and report")
    return args


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_workdir(source_db: Path, workdir: Path) -> tuple[Path, Path]:
    """Resolve and reject targets capable of touching source or repository data."""
    source = source_db.expanduser().resolve(strict=True)
    target = workdir.expanduser().resolve(strict=False)
    if not source.is_file():
        raise AcceptanceError("source database is not a regular file")
    if target == source or _is_relative_to(target, source.parent):
        raise AcceptanceError("work directory must be outside the source database directory")
    if target == PROJECT_ROOT or _is_relative_to(target, PROJECT_ROOT):
        raise AcceptanceError("work directory must be outside the repository")
    if target == Path(target.anchor) or target == Path.home().resolve():
        raise AcceptanceError("work directory target is too broad")
    if target.exists():
        raise AcceptanceError("explicit work directory must not already exist")
    return source, target


@contextmanager
def managed_workdir(
    source_db: Path,
    requested: Path | None,
    *,
    keep: bool,
) -> Iterator[Path]:
    source = source_db.expanduser().resolve(strict=True)
    if requested is None:
        target = Path(tempfile.mkdtemp(prefix="spotifystats-phase-d-", dir="/tmp")).resolve()
        # The generated path must pass the same guard as an explicit target.
        shutil.rmtree(target)
        _, target = validate_workdir(source, target)
        target.mkdir(mode=0o700)
    else:
        _, target = validate_workdir(source, requested)
        target.mkdir(parents=True, mode=0o700)
    try:
        yield target
    finally:
        if not keep and target.exists():
            shutil.rmtree(target)


def _readonly_uri(path: Path) -> str:
    return f"file:{quote(str(path.resolve()), safe='/')}?mode=ro"


def _online_backup(source_path: Path, target_path: Path) -> None:
    source = source_path.resolve(strict=True)
    target = target_path.resolve(strict=False)
    if target.exists():
        raise AcceptanceError("backup target already exists")
    if source == target:
        raise AcceptanceError("backup target is the source database")
    target.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(_readonly_uri(source), uri=True)
    target_conn = sqlite3.connect(target)
    try:
        source_conn.execute("PRAGMA query_only=ON")
        source_conn.backup(target_conn)
        result = str(target_conn.execute("PRAGMA quick_check").fetchone()[0])
        if result != "ok":
            raise AcceptanceError("online-backup target failed quick_check")
    finally:
        target_conn.close()
        source_conn.close()


def _database_profile(path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(_readonly_uri(path), uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        play_count = int(conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0])
        has_migrations = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        migration = (
            conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            if has_migrations
            else None
        )
        quick_check = str(conn.execute("PRAGMA quick_check").fetchone()[0])
        return {
            "play_count": play_count,
            "migration_max": int(migration[0] or 0) if migration else 0,
            "quick_check": quick_check,
            "database_bytes": path.stat().st_size,
        }
    finally:
        conn.close()


def _set_database(path: Path) -> None:
    db_mod.DB_PATH = str(path.resolve(strict=True))


def _settings_for_aggregation(conn: sqlite3.Connection) -> dict[str, Any]:
    from backend.domains.settings.repository import SettingsRepository

    settings = SettingsRepository(conn).load_all()
    return {
        "min_ms": int(settings.get("min_ms", 30_000)),
        "music_only": bool(settings.get("music_only", True)),
        "week_start_dow": int(settings.get("bb_week_start_dow", 4)),
        "week_start_hour": int(settings.get("bb_week_start_hour", 0)),
        "dynamic_threshold": True,
        "max_merge_gap_minutes": int(settings.get("max_merge_gap_minutes", 5)),
    }


def _prepare_baseline(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    from backend.core.db import build_aggregations, get_db
    from backend.core.migrations import run_migrations
    from backend.domains.imports.state import (
        publish_playback_import_state,
        summarise_current_playback_dataset,
    )

    _set_database(path)
    run_migrations()
    conn = get_db(readonly=False)
    try:
        missing_content_type = int(
            conn.execute(
                "SELECT COUNT(*) FROM plays WHERE content_type IS NULL OR content_type=''"
            ).fetchone()[0]
        )
        if missing_content_type:
            raise AcceptanceError("source copy contains plays without content_type")
        # The current real database predates Phase B fingerprints.  A synthetic,
        # deterministic baseline is sufficient for Phase D generation binding and
        # deliberately does not claim to validate source-record fingerprinting.
        conn.execute(
            "UPDATE plays SET source_fingerprint=NULL, "
            "source_fingerprint_version=NULL, import_generation_id=NULL"
        )
        conn.execute(
            "UPDATE plays SET source_fingerprint=printf('%064x', play_id), "
            "source_fingerprint_version=1"
        )
        summary = summarise_current_playback_dataset(conn)
        publish_playback_import_state(
            conn,
            generation_id=BASE_GENERATION_ID,
            account_identity_hash=None,
            relation="benchmark_baseline",
            strategy="full",
            summary=summary,
        )
        conn.commit()
        settings = _settings_for_aggregation(conn)
    finally:
        conn.close()

    started = time.perf_counter()
    result = build_aggregations(
        **settings,
        expected_generation_id=BASE_GENERATION_ID,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    if result.get("build_strategy") != "full":
        raise AcceptanceError("baseline Billboard build was not full")
    return (
        {
            "generation_id": BASE_GENERATION_ID,
            "dataset_digest": summary.dataset_digest,
            "record_count": summary.record_count,
        },
        {
            "elapsed_ms": round(elapsed_ms, 3),
            "row_counts": {
                key: int(result.get(key, 0))
                for key in result
                if key in {"tracks", "albums", "track_sources", "artists"}
            },
        },
    )


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _append_tail(
    path: Path,
    *,
    baseline: dict[str, Any],
    gap_seconds: float,
) -> Any:
    from backend.core.db import get_db
    from backend.domains.imports.change_set import build_playback_change_set
    from backend.domains.imports.incremental import (
        ImportPlan,
        ImportRelation,
        ImportStrategy,
        RecordIdentity,
    )
    from backend.domains.imports.state import (
        publish_playback_import_state,
        summarise_current_playback_dataset,
    )

    _set_database(path)
    conn = get_db(readonly=False)
    try:
        conn.row_factory = sqlite3.Row
        last = conn.execute(
            """SELECT p.*, stm.duration_ms AS benchmark_duration_ms
               FROM plays p
               JOIN tracks t ON t.track_id=p.track_id
               LEFT JOIN spotify_track_meta stm
                 ON stm.spotify_track_id=t.spotify_track_id
               WHERE p.track_id IS NOT NULL
               ORDER BY p.ts DESC, p.play_id DESC LIMIT 1"""
        ).fetchone()
        if last is None:
            raise AcceptanceError("source copy contains no music play for tail append")
        values = dict(last)
        duration_ms = max(
            int(values.pop("benchmark_duration_ms") or values.get("ms_played") or 60_000),
            60_000,
        )
        old_end = _parse_timestamp(str(values.get("ts") or ""))
        if old_end is None:
            raise AcceptanceError("latest music play has no parseable timestamp")
        new_end = old_end + timedelta(milliseconds=duration_ms, seconds=gap_seconds)
        local = new_end.astimezone(ZoneInfo("Asia/Shanghai"))
        fingerprint = hashlib.sha256(
            (
                f"phase-d-tail:{baseline['dataset_digest']}:"
                f"{new_end.isoformat()}:{values.get('track_id')}"
            ).encode()
        ).hexdigest()
        if conn.execute(
            "SELECT 1 FROM plays WHERE content_type='audio' AND source_fingerprint=?",
            (fingerprint,),
        ).fetchone():
            raise AcceptanceError("synthetic tail fingerprint collision")
        values.update(
            {
                "ts": new_end.isoformat().replace("+00:00", "Z"),
                "ts_date": local.date().isoformat(),
                "ts_year": local.year,
                "ts_month": local.month,
                "ts_week": int(local.isocalendar().week),
                "ts_dow": local.weekday(),
                "ts_hour": local.hour,
                "ms_played": duration_ms,
                "content_type": "audio",
                "source_fingerprint": fingerprint,
                "source_fingerprint_version": 1,
                "import_generation_id": APPEND_GENERATION_ID,
            }
        )
        columns = [
            str(row[1])
            for row in conn.execute("PRAGMA table_info(plays)").fetchall()
            if str(row[1]) != "play_id"
        ]
        quoted = ",".join(f'"{column}"' for column in columns)
        placeholders = ",".join("?" for _ in columns)
        conn.execute(
            f"INSERT INTO plays({quoted}) VALUES ({placeholders})",
            [values.get(column) for column in columns],
        )
        summary = summarise_current_playback_dataset(conn)
        publish_playback_import_state(
            conn,
            generation_id=APPEND_GENERATION_ID,
            account_identity_hash=None,
            relation="delta_tail",
            strategy="incremental",
            summary=summary,
        )
        conn.commit()

        baseline_first = conn.execute(
            "SELECT MIN(ts) FROM plays WHERE play_id!=(SELECT MAX(play_id) FROM plays)"
        ).fetchone()[0]
        plan = ImportPlan(
            relation=ImportRelation.DELTA_TAIL,
            estimated_strategy=ImportStrategy.INCREMENTAL,
            incoming_digest=summary.dataset_digest,
            previous_digest=str(baseline["dataset_digest"]),
            incoming_count=summary.record_count,
            existing_count=int(baseline["record_count"]),
            unchanged_count=int(baseline["record_count"]),
            added=frozenset({RecordIdentity("audio", fingerprint)}),
            removed=frozenset(),
            incoming_first_ts=_parse_timestamp(str(baseline_first or "")),
            incoming_latest_ts=new_end,
            existing_first_ts=_parse_timestamp(str(baseline_first or "")),
            existing_latest_ts=old_end,
            requires_confirmation=False,
        )
        change_set = build_playback_change_set(
            conn,
            generation_id=APPEND_GENERATION_ID,
            strategy="incremental",
            plan=plan,
        )
        if change_set.added_count != 1 or not change_set.billboard_scope_exact:
            raise AcceptanceError("tail append did not produce one exact Billboard ChangeSet")
        return change_set
    finally:
        conn.close()


def _run_billboard_strategy(
    path: Path,
    *,
    strategy: str,
    change_set: Any,
) -> tuple[dict[str, Any], float]:
    from backend.core.db import build_aggregations, build_aggregations_for_weeks, get_db

    _set_database(path)
    conn = get_db(readonly=True)
    try:
        settings = _settings_for_aggregation(conn)
    finally:
        conn.close()
    started = time.perf_counter()
    if strategy == "partition":
        result = build_aggregations_for_weeks(
            set(change_set.billboard_weeks),
            change_generation_id=change_set.generation_id,
            previous_dataset_digest=change_set.previous_dataset_digest,
            billboard_scope_exact=change_set.billboard_scope_exact,
            **settings,
            expected_generation_id=change_set.generation_id,
        )
    elif strategy == "full":
        result = build_aggregations(
            **settings,
            expected_generation_id=change_set.generation_id,
        )
    else:  # pragma: no cover - internal boundary
        raise ValueError(strategy)
    return dict(result), round((time.perf_counter() - started) * 1000, 3)


def _table_columns(conn: sqlite3.Connection, schema: str, table: str) -> tuple[str, ...]:
    return tuple(
        str(row[1]) for row in conn.execute(f'PRAGMA "{schema}".table_info("{table}")').fetchall()
    )


def _compare_billboard(partition_path: Path, full_path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(partition_path)
    try:
        conn.execute("ATTACH DATABASE ? AS full", (str(full_path),))
        tables: dict[str, Any] = {}
        passed = True
        for table in BILLBOARD_TABLES:
            main_columns = _table_columns(conn, "main", table)
            full_columns = _table_columns(conn, "full", table)
            if not main_columns or main_columns != full_columns:
                raise AcceptanceError(f"Billboard table schema mismatch: {table}")
            left_only = int(
                conn.execute(
                    f'SELECT COUNT(*) FROM (SELECT * FROM main."{table}" '
                    f'EXCEPT SELECT * FROM full."{table}")'
                ).fetchone()[0]
            )
            right_only = int(
                conn.execute(
                    f'SELECT COUNT(*) FROM (SELECT * FROM full."{table}" '
                    f'EXCEPT SELECT * FROM main."{table}")'
                ).fetchone()[0]
            )
            main_count = int(conn.execute(f'SELECT COUNT(*) FROM main."{table}"').fetchone()[0])
            full_count = int(conn.execute(f'SELECT COUNT(*) FROM full."{table}"').fetchone()[0])
            table_passed = left_only == 0 and right_only == 0 and main_count == full_count
            passed = passed and table_passed
            tables[table] = {
                "partition_rows": main_count,
                "full_rows": full_count,
                "partition_only_rows": left_only,
                "full_only_rows": right_only,
                "passed": table_passed,
            }
        config = {
            str(row[0]): str(row[1])
            for row in conn.execute("SELECT key, value FROM main.agg_config").fetchall()
        }
        full_config = {
            str(row[0]): str(row[1])
            for row in conn.execute("SELECT key, value FROM full.agg_config").fetchall()
        }
        required_config = (
            "data_generation_id",
            "source_dataset_digest",
            "builder_version",
            "playback_policy_version",
            "identity_revision",
            "track_credit_revision",
            "album_project_revision",
            "duration_revision",
            "credit_membership_revision",
        )
        config_complete = all(config.get(key) for key in required_config)
        full_config_complete = all(full_config.get(key) for key in required_config)
        config_mismatches = [
            key for key in required_config if config.get(key) != full_config.get(key)
        ]
        semantic_config_equal = not config_mismatches
        passed = passed and config_complete and full_config_complete and semantic_config_equal
        return {
            "passed": passed,
            "tables": tables,
            "partition_config_complete": config_complete,
            "full_config_complete": full_config_complete,
            "semantic_config_equal": semantic_config_equal,
            "semantic_config_mismatches": config_mismatches,
            "partition_build_strategy": config.get("build_strategy"),
        }
    finally:
        conn.close()


def _prepare_search_canonical(path: Path, change_set: Any) -> dict[str, Any]:
    from backend.core.db import get_db
    from backend.domains.music_search.index import rebuild_music_search_index
    from backend.domains.music_search.revisions import bump_music_search_revisions
    from backend.domains.music_search.variants import build_music_search_variant_contexts
    from backend.services.music_search_maintenance_service import (
        _current_filter_values,
        build_shared_full_music_search_plan,
    )

    _set_database(path)
    conn = get_db(readonly=False)
    try:
        bump_music_search_revisions(conn, "playback", "billboard", "candidate")
        conn.commit()
        index_report = rebuild_music_search_index(conn)
        contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
        fingerprints = tuple(context.filter_fingerprint for context in contexts)
        if len(contexts) != 4 or len(set(fingerprints)) != 4:
            raise AcceptanceError("current music-search context is not an exact four-variant set")
        placeholders = ",".join("?" for _ in fingerprints)
        conn.execute(
            f"DELETE FROM music_search_entity_context WHERE snapshot_key IN ({placeholders})",
            fingerprints,
        )
        conn.execute(
            f"DELETE FROM music_search_snapshot_meta WHERE snapshot_key IN ({placeholders})",
            fingerprints,
        )
        conn.commit()
        plan = build_shared_full_music_search_plan(conn, change_set=change_set)
        if plan is None:
            raise AcceptanceError("exact append did not produce a compatible shared search plan")
        return {
            "candidate_status": str(index_report.get("status") or "ready"),
            "candidate_documents": int(index_report.get("document_count") or 0),
            "semantic_base_key": contexts[0].semantic_base_key,
            "shared_plan_schema": str(plan.get("schema_version") or ""),
        }
    finally:
        conn.close()


def _peak_rss_bytes() -> int:
    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return peak if sys.platform == "darwin" else peak * 1024


def _safe_worker_variants(raw: dict[str, Any]) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    for item in raw.get("variants") or []:
        variants.append(
            {
                "merge_level": int(item.get("merge_level") or 0),
                "dynamic_threshold": bool(item.get("dynamic_threshold")),
                "status": str(item.get("status") or "unknown"),
                "entity_count": int(item.get("entity_count") or 0),
                "duration_ms": round(float(item.get("duration_ms") or 0.0), 3),
                "revalidated": bool(item.get("revalidated", False)),
                "reuse_reason": item.get("reuse_reason"),
            }
        )
    return variants


def _worker_main(args: argparse.Namespace) -> int:
    from backend.core.db import get_db
    from backend.domains.music_search.snapshot import (
        build_music_search_snapshot_set,
        build_shared_full_music_search_snapshot_set,
    )
    from backend.domains.music_search.variants import build_music_search_variant_contexts
    from backend.services.music_search_maintenance_service import _current_filter_values

    assert args._worker_db is not None
    assert args._worker_generation is not None
    assert args._worker_report is not None
    report: dict[str, Any]
    conn: sqlite3.Connection | None = None
    started = time.perf_counter()
    try:
        _set_database(args._worker_db)
        conn = get_db(readonly=False)
        contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
        if args._worker_strategy == "shared":
            raw = build_shared_full_music_search_snapshot_set(
                conn,
                contexts,
                source_generation_id=args._worker_generation,
            )
            if raw is None:
                raise AcceptanceError("shared builder rejected the prepared generation")
            strategy = str(raw.get("strategy") or "shared")
        else:
            raw = build_music_search_snapshot_set(conn, contexts)
            strategy = "ordinary_full_snapshot_set"
        variants = _safe_worker_variants(raw)
        variant_set = {(item["merge_level"], item["dynamic_threshold"]) for item in variants}
        ledger_table_exists = conn.execute(
            """SELECT 1 FROM sqlite_master
               WHERE type='table' AND name='music_search_weekly_chart_context'"""
        ).fetchone()
        weekly_ledger_rows = (
            int(
                conn.execute("SELECT COUNT(*) FROM music_search_weekly_chart_context").fetchone()[0]
            )
            if ledger_table_exists
            else 0
        )
        lineage_ready_count = (
            int(
                conn.execute(
                    """SELECT COUNT(*) FROM music_search_snapshot_meta
                       WHERE status='ready' AND policy_key IS NOT NULL
                         AND source_generation_id IS NOT NULL
                         AND source_dataset_digest IS NOT NULL
                         AND dependency_digest IS NOT NULL
                         AND build_strategy='shared_full'"""
                ).fetchone()[0]
            )
            if ledger_table_exists
            else 0
        )
        report = {
            "status": str(raw.get("status") or "unknown"),
            "strategy": strategy,
            "semantic_base_key": str(raw.get("semantic_base_key") or ""),
            "ready_count": int(raw.get("ready_count") or 0),
            "failed_count": int(raw.get("failed_count") or 0),
            "helper_elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "peak_rss_bytes": _peak_rss_bytes(),
            "shared_logical_frame_sets": raw.get("shared_logical_frame_sets"),
            "weekly_ledger_ready": bool(raw.get("weekly_ledger_ready", False)),
            "weekly_ledger_rows": weekly_ledger_rows,
            "lineage_ready_count": lineage_ready_count,
            "exact_variant_set": variant_set == EXPECTED_VARIANTS,
            "variants": variants,
        }
        report["passed"] = bool(
            report["status"] == "ready"
            and report["ready_count"] == 4
            and report["failed_count"] == 0
            and report["exact_variant_set"]
            and (
                args._worker_strategy == "shared"
                or all(not item["revalidated"] for item in variants)
            )
            and (
                args._worker_strategy != "shared"
                or report["strategy"] == "shared_full_snapshot_rebuild"
            )
            and (args._worker_strategy != "shared" or report["shared_logical_frame_sets"] == 2)
            and (args._worker_strategy != "shared" or report["weekly_ledger_ready"])
            and (args._worker_strategy != "shared" or report["weekly_ledger_rows"] > 0)
            and (args._worker_strategy != "shared" or report["lineage_ready_count"] == 4)
        )
    except Exception as exc:
        report = {
            "status": "failed",
            "passed": False,
            "strategy": str(args._worker_strategy),
            "error_type": type(exc).__name__,
            "helper_elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "peak_rss_bytes": _peak_rss_bytes(),
            "variants": [],
        }
    finally:
        if conn is not None:
            conn.close()
    args._worker_report.write_text(
        json.dumps(report, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if report.get("passed") else 1


def _run_search_worker(
    *,
    strategy: str,
    database: Path,
    generation_id: str,
    report_path: Path,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--_worker-strategy",
        strategy,
        "--_worker-db",
        str(database),
        "--_worker-generation",
        generation_id,
        "--_worker-report",
        str(report_path),
    ]
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("PYTHONHASHSEED", "0")
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    wall_ms = round((time.perf_counter() - started) * 1000, 3)
    if not report_path.is_file():
        raise AcceptanceError(f"{strategy} search worker did not write a report")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["process_wall_ms"] = wall_ms
    report["process_returncode"] = completed.returncode
    return report


def _search_projection(schema: str) -> str:
    columns = ", ".join(f"c.{column}" for column in SEARCH_PAYLOAD_COLUMNS)
    return (
        f"SELECT m.merge_level, m.dynamic_threshold, {columns} "
        f"FROM {schema}.music_search_snapshot_meta m "
        f"JOIN {schema}.music_search_entity_context c "
        "ON c.snapshot_key=m.snapshot_key WHERE m.semantic_base_key=?"
    )


def _compare_search(
    shared_path: Path,
    ordinary_path: Path,
    *,
    semantic_base_key: str,
) -> dict[str, Any]:
    conn = sqlite3.connect(shared_path)
    try:
        conn.execute("ATTACH DATABASE ? AS ordinary", (str(ordinary_path),))
        shared_projection = _search_projection("main")
        ordinary_projection = _search_projection("ordinary")
        shared_only = int(
            conn.execute(
                f"SELECT COUNT(*) FROM ({shared_projection} EXCEPT {ordinary_projection})",
                (semantic_base_key, semantic_base_key),
            ).fetchone()[0]
        )
        ordinary_only = int(
            conn.execute(
                f"SELECT COUNT(*) FROM ({ordinary_projection} EXCEPT {shared_projection})",
                (semantic_base_key, semantic_base_key),
            ).fetchone()[0]
        )
        meta_projection = (
            "SELECT snapshot_key, filter_fingerprint, source_revision, status, "
            "semantic_base_key, merge_level, dynamic_threshold, builder_version "
            "FROM {schema}.music_search_snapshot_meta WHERE semantic_base_key=?"
        )
        shared_meta = meta_projection.format(schema="main")
        ordinary_meta = meta_projection.format(schema="ordinary")
        shared_meta_only = int(
            conn.execute(
                f"SELECT COUNT(*) FROM ({shared_meta} EXCEPT {ordinary_meta})",
                (semantic_base_key, semantic_base_key),
            ).fetchone()[0]
        )
        ordinary_meta_only = int(
            conn.execute(
                f"SELECT COUNT(*) FROM ({ordinary_meta} EXCEPT {shared_meta})",
                (semantic_base_key, semantic_base_key),
            ).fetchone()[0]
        )
        shared_rows = int(
            conn.execute(
                f"SELECT COUNT(*) FROM ({shared_projection})",
                (semantic_base_key,),
            ).fetchone()[0]
        )
        ordinary_rows = int(
            conn.execute(
                f"SELECT COUNT(*) FROM ({ordinary_projection})",
                (semantic_base_key,),
            ).fetchone()[0]
        )
        passed = (
            all(
                value == 0
                for value in (
                    shared_only,
                    ordinary_only,
                    shared_meta_only,
                    ordinary_meta_only,
                )
            )
            and shared_rows == ordinary_rows
        )
        return {
            "passed": passed,
            "shared_rows": shared_rows,
            "ordinary_rows": ordinary_rows,
            "shared_only_rows": shared_only,
            "ordinary_only_rows": ordinary_only,
            "shared_meta_only_rows": shared_meta_only,
            "ordinary_meta_only_rows": ordinary_meta_only,
        }
    finally:
        conn.close()


def _remove_database(path: Path) -> None:
    for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        if candidate.exists():
            candidate.unlink()


def _run_search_trials(
    canonical: Path,
    workdir: Path,
    *,
    trials: int,
    keep_workdir: bool,
    semantic_base_key: str,
) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    for trial in range(1, trials + 1):
        shared_path = workdir / f"search-shared-{trial}.db"
        ordinary_path = workdir / f"search-ordinary-{trial}.db"
        _online_backup(canonical, shared_path)
        _online_backup(canonical, ordinary_path)
        order = ("shared", "ordinary") if trial % 2 else ("ordinary", "shared")
        worker_reports: dict[str, dict[str, Any]] = {}
        paths = {"shared": shared_path, "ordinary": ordinary_path}
        for strategy in order:
            worker_reports[strategy] = _run_search_worker(
                strategy=strategy,
                database=paths[strategy],
                generation_id=APPEND_GENERATION_ID,
                report_path=workdir / f"search-{strategy}-{trial}.json",
            )
        workers_passed = bool(
            worker_reports["shared"].get("passed") and worker_reports["ordinary"].get("passed")
        )
        equivalence = (
            _compare_search(
                shared_path,
                ordinary_path,
                semantic_base_key=semantic_base_key,
            )
            if workers_passed
            else {
                "status": "not_compared",
                "passed": False,
                "reason": "builder_failed",
            }
        )
        trial_passed = bool(equivalence["passed"] and workers_passed)
        reports.append(
            {
                "trial": trial,
                "order": list(order),
                "passed": trial_passed,
                "shared": worker_reports["shared"],
                "ordinary": worker_reports["ordinary"],
                "equivalence": equivalence,
            }
        )
        if not keep_workdir:
            _remove_database(shared_path)
            _remove_database(ordinary_path)

    shared_times = [float(item["shared"]["helper_elapsed_ms"]) for item in reports]
    ordinary_times = [float(item["ordinary"]["helper_elapsed_ms"]) for item in reports]
    shared_median = statistics.median(shared_times)
    ordinary_median = statistics.median(ordinary_times)
    return {
        "status": "passed" if all(item["passed"] for item in reports) else "failed",
        "passed": all(item["passed"] for item in reports),
        "trial_count": trials,
        "performance_conclusion_ready": trials >= 3,
        "shared_median_ms": round(shared_median, 3),
        "ordinary_median_ms": round(ordinary_median, 3),
        "shared_speedup": round(ordinary_median / shared_median, 3) if shared_median > 0 else None,
        "trials": reports,
    }


def _git_evidence() -> dict[str, Any]:
    def command(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.stdout.strip() if completed.returncode == 0 else "unavailable"

    implementation_files = (
        PROJECT_ROOT / "backend/core/db.py",
        PROJECT_ROOT / "backend/domains/imports/change_set.py",
        PROJECT_ROOT / "backend/domains/music_search/snapshot.py",
        PROJECT_ROOT / "backend/services/music_search_maintenance_service.py",
        Path(__file__).resolve(),
    )
    hashes = {
        str(path.relative_to(PROJECT_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in implementation_files
        if path.is_file()
    }
    status = command("status", "--short")
    return {
        "head": command("rev-parse", "HEAD"),
        "dirty": bool(status and status != "unavailable"),
        "status_lines": len(status.splitlines()) if status != "unavailable" else None,
        "implementation_sha256": hashes,
    }


def build_final_report(
    *,
    source_profile: dict[str, Any],
    backup_profile: dict[str, Any],
    baseline_build: dict[str, Any],
    append_scope: dict[str, Any],
    billboard: dict[str, Any],
    search: dict[str, Any] | None,
    keep_workdir: bool,
) -> dict[str, Any]:
    billboard_passed = bool(billboard.get("passed"))
    search_passed = search is not None and bool(search.get("passed"))
    requested_checks_passed = billboard_passed and (search is None or search_passed)
    complete_phase_d = billboard_passed and search_passed
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "passed"
        if complete_phase_d
        else "partial"
        if requested_checks_passed
        else "failed",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "source": source_profile,
        "backup": backup_profile,
        "synthetic_baseline": {
            "used": True,
            "validates_phase_b_fingerprints": False,
            "build": baseline_build,
        },
        "append": append_scope,
        "billboard": billboard,
        "search": search or {"status": "skipped", "passed": None},
        "git": _git_evidence(),
        "privacy": PRIVACY_REPORT,
        "workdir_preserved": keep_workdir,
        "gate": {
            "billboard_equivalent": billboard_passed,
            "search_equivalent": search_passed if search is not None else None,
            "requested_checks_passed": requested_checks_passed,
            "complete_phase_d": complete_phase_d,
        },
    }


def _run_acceptance(args: argparse.Namespace, workdir: Path) -> dict[str, Any]:
    source_path = args.source_db.expanduser().resolve(strict=True)
    source_before = source_path.stat()
    source_profile = _database_profile(source_path)
    if source_profile["quick_check"] != "ok":
        raise AcceptanceError("source database failed quick_check")

    baseline_path = workdir / "baseline.db"
    partition_path = workdir / "partition.db"
    full_path = workdir / "full.db"
    _online_backup(source_path, baseline_path)
    backup_profile = _database_profile(baseline_path)
    if backup_profile["play_count"] != source_profile["play_count"]:
        raise AcceptanceError("online backup changed the source play count")
    baseline, baseline_build = _prepare_baseline(baseline_path)

    _online_backup(baseline_path, partition_path)
    _online_backup(baseline_path, full_path)
    partition_change_set = _append_tail(
        partition_path,
        baseline=baseline,
        gap_seconds=args.append_gap_seconds,
    )
    full_change_set = _append_tail(
        full_path,
        baseline=baseline,
        gap_seconds=args.append_gap_seconds,
    )
    if partition_change_set.to_dict() != full_change_set.to_dict():
        raise AcceptanceError("partition and full clones produced different ChangeSets")

    partition_result, partition_ms = _run_billboard_strategy(
        partition_path,
        strategy="partition",
        change_set=partition_change_set,
    )
    full_result, full_ms = _run_billboard_strategy(
        full_path,
        strategy="full",
        change_set=full_change_set,
    )
    equivalence = _compare_billboard(partition_path, full_path)
    partition_gate = bool(
        partition_result.get("build_strategy") == "partition"
        and partition_result.get("fallback_reason") is None
    )
    billboard = {
        "status": "passed" if equivalence["passed"] and partition_gate else "failed",
        "passed": bool(equivalence["passed"] and partition_gate),
        "partition_elapsed_ms": partition_ms,
        "full_elapsed_ms": full_ms,
        "partition_speedup": round(full_ms / partition_ms, 3) if partition_ms > 0 else None,
        "affected_week_count": len(partition_change_set.billboard_weeks),
        "partition_strategy_gate": partition_gate,
        "partition_report": {
            "build_strategy": partition_result.get("build_strategy"),
            "fallback_reason": partition_result.get("fallback_reason"),
        },
        "full_report": {"build_strategy": full_result.get("build_strategy")},
        "equivalence": equivalence,
    }

    search: dict[str, Any] | None = None
    if not args.skip_search:
        search_setup = _prepare_search_canonical(full_path, full_change_set)
        search = _run_search_trials(
            full_path,
            workdir,
            trials=args.trials,
            keep_workdir=args.keep_workdir,
            semantic_base_key=str(search_setup["semantic_base_key"]),
        )
        search["setup"] = search_setup

    source_after = source_path.stat()
    source_unchanged = (
        source_before.st_size == source_after.st_size
        and source_before.st_mtime_ns == source_after.st_mtime_ns
        and source_before.st_ino == source_after.st_ino
    )
    if not source_unchanged:
        raise AcceptanceError("source database changed during acceptance; evidence is not stable")
    append_scope = {
        "added_count": partition_change_set.added_count,
        "removed_count": partition_change_set.removed_count,
        "billboard_scope_exact": partition_change_set.billboard_scope_exact,
        "affected_week_count": len(partition_change_set.billboard_weeks),
        "logical_tail_gap_seconds": args.append_gap_seconds,
    }
    return build_final_report(
        source_profile=source_profile,
        backup_profile=backup_profile,
        baseline_build=baseline_build,
        append_scope=append_scope,
        billboard=billboard,
        search=search,
        keep_workdir=args.keep_workdir,
    )


def _emit_report(report: dict[str, Any], args: argparse.Namespace) -> None:
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.json_output:
        output = args.json_output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    if args.json:
        print(payload, end="")
        return
    gate = report.get("gate") or {}
    print(
        "Phase D acceptance: "
        f"status={report.get('status')} "
        f"billboard={gate.get('billboard_equivalent')} "
        f"search={gate.get('search_equivalent')}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args._worker_strategy:
        return _worker_main(args)
    report: dict[str, Any]
    try:
        source = args.source_db.expanduser().resolve(strict=True)
        with managed_workdir(source, args.workdir, keep=args.keep_workdir) as workdir:
            if args.json_output and not args.keep_workdir:
                output = args.json_output.expanduser().resolve()
                if _is_relative_to(output, workdir):
                    raise AcceptanceError(
                        "--json-output inside the temporary workdir would be deleted"
                    )
            report = _run_acceptance(args, workdir)
            if args.keep_workdir:
                print(f"Private benchmark copies preserved at: {workdir}", file=sys.stderr)
    except Exception as exc:
        report = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "status": "failed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "error": {"type": type(exc).__name__},
            "privacy": PRIVACY_REPORT,
            "gate": {
                "billboard_equivalent": False,
                "search_equivalent": False,
                "requested_checks_passed": False,
                "complete_phase_d": False,
            },
        }
    _emit_report(report, args)
    return 0 if (report.get("gate") or {}).get("requested_checks_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
