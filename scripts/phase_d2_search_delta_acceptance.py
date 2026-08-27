#!/usr/bin/env python3
"""Validate the Phase D2 search delta builder on disposable real-DB copies.

The source database is opened read-only and copied with SQLite Online Backup.
All migrations, synthetic tail data, index rebuilds, and snapshot publications
are confined to a private work directory outside the repository.  The default
work directory is removed in ``finally``.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from datetime import time as datetime_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core import db as db_mod  # noqa: E402
from scripts import phase_d_real_db_acceptance as phase_d  # noqa: E402

REPORT_SCHEMA_VERSION = "phase_d2_search_delta_acceptance_v2"
PRIVACY_REPORT = {
    "database_path_emitted": False,
    "entity_content_emitted": False,
    "listening_history_rows_emitted": False,
    "week_boundary_values_emitted": False,
}
ENTITY_CONTEXT_COLUMNS = (
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
WEEKLY_LEDGER_COLUMNS = (
    "family",
    "week",
    "entity_key",
    "rank",
    "play_count",
    "total_ms",
    "stable_sort_key",
)


class AcceptanceError(RuntimeError):
    """A fail-closed Phase D2 acceptance violation."""


@dataclass(frozen=True)
class SnapshotVariant:
    fingerprint: str
    merge_level: int
    dynamic_threshold: bool


@dataclass(frozen=True)
class CrossWeekBoundary:
    gap_seconds: float
    previous_open_week: date
    current_open_week: date


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare a bounded search snapshot delta with the shared-full "
            "reference on disposable database copies"
        )
    )
    parser.add_argument(
        "--scenario",
        choices=("within-open-week", "cross-week"),
        default="within-open-week",
        help="Synthetic append scenario; the default preserves the D2b acceptance",
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
        help="Preserve the private database copies for local debugging",
    )
    parser.add_argument(
        "--append-gap-seconds",
        type=float,
        default=1.0,
        help=(
            "Within-week idle gap, or cross-week safety margin after the next Billboard boundary"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the machine-readable report instead of a short summary",
    )
    args = parser.parse_args(argv)
    if args.append_gap_seconds < 0:
        parser.error("--append-gap-seconds must be non-negative")
    return args


def _compute_cross_week_boundary(
    *,
    old_end: datetime,
    duration_ms: int,
    week_start_dow: int,
    week_start_hour: int,
    margin_seconds: float,
) -> CrossWeekBoundary:
    from backend.domains.billboard.week_coverage import (
        open_billboard_week_for_latest_timestamp,
    )
    from backend.domains.playback.logical_timeline import PLAYBACK_TIMEZONE

    if old_end.tzinfo is None:
        old_end = old_end.replace(tzinfo=timezone.utc)
    old_end = old_end.astimezone(timezone.utc)
    if duration_ms <= 0 or margin_seconds < 0:
        raise AcceptanceError("cross-week append timing is invalid")
    previous_open = open_billboard_week_for_latest_timestamp(
        old_end,
        week_start_dow=week_start_dow,
        week_start_hour=week_start_hour,
    )
    if previous_open is None:
        raise AcceptanceError("baseline open Billboard week is unavailable")
    current_open = previous_open + timedelta(days=7)
    boundary_local = datetime.combine(
        current_open,
        datetime_time(hour=week_start_hour),
        tzinfo=ZoneInfo(PLAYBACK_TIMEZONE),
    )
    event_start = boundary_local.astimezone(timezone.utc) + timedelta(seconds=margin_seconds)
    event_end = event_start + timedelta(milliseconds=duration_ms)
    following_boundary = boundary_local + timedelta(days=7)
    if event_end >= following_boundary.astimezone(timezone.utc):
        raise AcceptanceError("synthetic cross-week play would cross another week boundary")
    start_open = open_billboard_week_for_latest_timestamp(
        event_start,
        week_start_dow=week_start_dow,
        week_start_hour=week_start_hour,
    )
    end_open = open_billboard_week_for_latest_timestamp(
        event_end,
        week_start_dow=week_start_dow,
        week_start_hour=week_start_hour,
    )
    gap_seconds = (event_start - old_end).total_seconds()
    if gap_seconds < 0 or start_open != current_open or end_open != current_open:
        raise AcceptanceError("synthetic append is not confined to the next open week")
    return CrossWeekBoundary(
        gap_seconds=gap_seconds,
        previous_open_week=previous_open,
        current_open_week=current_open,
    )


def _cross_week_boundary_for_database(
    path: Path,
    *,
    margin_seconds: float,
) -> CrossWeekBoundary:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        settings = phase_d._settings_for_aggregation(conn)
        row = conn.execute(
            """SELECT p.ts, p.ms_played, stm.duration_ms
               FROM plays p
               JOIN tracks t ON t.track_id=p.track_id
               LEFT JOIN spotify_track_meta stm
                 ON stm.spotify_track_id=t.spotify_track_id
               WHERE p.track_id IS NOT NULL
               ORDER BY p.ts DESC, p.play_id DESC LIMIT 1"""
        ).fetchone()
        if row is None:
            raise AcceptanceError("source copy contains no music play for cross-week append")
        old_end = phase_d._parse_timestamp(str(row["ts"] or ""))
        if old_end is None:
            raise AcceptanceError("latest music play has no parseable timestamp")
        duration_ms = max(int(row["duration_ms"] or row["ms_played"] or 60_000), 60_000)
        return _compute_cross_week_boundary(
            old_end=old_end,
            duration_ms=duration_ms,
            week_start_dow=int(settings["week_start_dow"]),
            week_start_hour=int(settings["week_start_hour"]),
            margin_seconds=margin_seconds,
        )
    finally:
        conn.close()


def _set_database(path: Path) -> None:
    db_mod.DB_PATH = str(path.resolve(strict=True))


def _build_contexts(conn: sqlite3.Connection) -> tuple[Any, ...]:
    from backend.domains.music_search.variants import build_music_search_variant_contexts
    from backend.services.music_search_maintenance_service import _current_filter_values

    contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
    variants = {(int(context.merge_level), bool(context.dynamic_threshold)) for context in contexts}
    if len(contexts) != 4 or len({context.filter_fingerprint for context in contexts}) != 4:
        raise AcceptanceError("music-search contexts are not an exact four-variant set")
    if variants != phase_d.EXPECTED_VARIANTS:
        raise AcceptanceError("music-search contexts do not cover the expected variants")
    return contexts


def _snapshot_variants(contexts: tuple[Any, ...]) -> tuple[SnapshotVariant, ...]:
    return tuple(
        SnapshotVariant(
            fingerprint=str(context.filter_fingerprint),
            merge_level=int(context.merge_level),
            dynamic_threshold=bool(context.dynamic_threshold),
        )
        for context in contexts
    )


def _prepare_baseline_search(path: Path, *, generation_id: str) -> dict[str, Any]:
    from backend.core.db import get_db
    from backend.domains.music_search.index import rebuild_music_search_index
    from backend.domains.music_search.revisions import bump_music_search_revisions
    from backend.domains.music_search.snapshot import (
        build_shared_full_music_search_snapshot_set,
    )
    from backend.domains.music_search.snapshot_lineage import (
        active_playback_lineage,
        music_search_snapshot_dependency_digest,
    )

    _set_database(path)
    conn = get_db(readonly=False)
    try:
        active_generation, baseline_digest = active_playback_lineage(conn)
        if active_generation != generation_id or not baseline_digest:
            raise AcceptanceError("baseline playback lineage is incomplete")
        bump_music_search_revisions(conn, "playback", "billboard", "candidate")
        conn.commit()
        index_report = rebuild_music_search_index(conn)
        if str(index_report.get("status") or "") not in {"ready", "degraded"}:
            raise AcceptanceError("baseline candidate index is not ready")
        dependency_digest = music_search_snapshot_dependency_digest(conn)
        contexts = _build_contexts(conn)
        started = time.perf_counter()
        report = build_shared_full_music_search_snapshot_set(
            conn,
            contexts,
            source_generation_id=generation_id,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        if report is None or report.get("strategy") != "shared_full_snapshot_rebuild":
            raise AcceptanceError("baseline shared-full snapshot build was rejected")
        fingerprints = tuple(str(context.filter_fingerprint) for context in contexts)
        placeholders = ",".join("?" for _ in fingerprints)
        lineage_count = int(
            conn.execute(
                f"""SELECT COUNT(*) FROM music_search_snapshot_meta
                    WHERE snapshot_key IN ({placeholders}) AND status='ready'
                      AND build_strategy='shared_full' AND base_snapshot_key IS NULL
                      AND source_generation_id=? AND source_dataset_digest=?
                      AND dependency_digest=?""",
                (*fingerprints, generation_id, baseline_digest, dependency_digest),
            ).fetchone()[0]
        )
        ledger_rows = int(
            conn.execute(
                f"""SELECT COUNT(*) FROM music_search_weekly_chart_context
                    WHERE snapshot_key IN ({placeholders})""",
                fingerprints,
            ).fetchone()[0]
        )
        if lineage_count != 4 or ledger_rows <= 0:
            raise AcceptanceError("baseline snapshots lack complete lineage or weekly ledger")
        return {
            "dataset_digest": baseline_digest,
            "dependency_digest": dependency_digest,
            "variants": _snapshot_variants(contexts),
            "elapsed_ms": elapsed_ms,
            "entity_rows": int(
                conn.execute(
                    f"""SELECT COUNT(*) FROM music_search_entity_context
                        WHERE snapshot_key IN ({placeholders})""",
                    fingerprints,
                ).fetchone()[0]
            ),
            "ledger_rows": ledger_rows,
        }
    finally:
        conn.close()


def _assert_same_open_week(change_set: Any) -> None:
    previous_open = str(getattr(change_set, "previous_open_week", None) or "")
    current_open = str(getattr(change_set, "current_open_week", None) or "")
    affected_weeks = tuple(
        sorted(str(value) for value in getattr(change_set, "billboard_weeks", ()) or ())
    )
    if not previous_open or previous_open != current_open:
        raise AcceptanceError("tail append crossed the open Billboard week boundary")
    if affected_weeks != (current_open,):
        raise AcceptanceError("same-week append has an unexpected Billboard scope")
    if not bool(getattr(change_set, "billboard_scope_exact", False)):
        raise AcceptanceError("tail append lacks an exact Billboard scope")


def _assert_cross_week_scope(
    change_set: Any,
    boundary: CrossWeekBoundary,
) -> None:
    previous_open = str(getattr(change_set, "previous_open_week", None) or "")
    current_open = str(getattr(change_set, "current_open_week", None) or "")
    affected_weeks = {str(value) for value in getattr(change_set, "billboard_weeks", ()) or ()}
    expected_weeks = {
        boundary.previous_open_week.isoformat(),
        boundary.current_open_week.isoformat(),
    }
    if (
        getattr(change_set, "strategy", None) != "incremental"
        or int(getattr(change_set, "added_count", 0) or 0) != 1
        or int(getattr(change_set, "removed_count", 0) or 0) != 0
        or not bool(getattr(change_set, "billboard_scope_exact", False))
        or previous_open != boundary.previous_open_week.isoformat()
        or current_open != boundary.current_open_week.isoformat()
        or boundary.current_open_week != boundary.previous_open_week + timedelta(days=7)
        or affected_weeks != expected_weeks
    ):
        raise AcceptanceError("cross-week append lacks the exact one-week boundary proof")


def _prepare_appended_search(
    path: Path,
    *,
    baseline: dict[str, Any],
    gap: float,
    scenario: str,
    cross_week_boundary: CrossWeekBoundary | None,
) -> Any:
    from backend.core.db import get_db
    from backend.domains.music_search.index import rebuild_music_search_index
    from backend.domains.music_search.revisions import bump_music_search_revisions

    change_set = phase_d._append_tail(path, baseline=baseline, gap_seconds=gap)
    if scenario == "cross-week":
        if cross_week_boundary is None:
            raise AcceptanceError("cross-week boundary proof is unavailable")
        _assert_cross_week_scope(change_set, cross_week_boundary)
    else:
        _assert_same_open_week(change_set)
    billboard_report, _elapsed_ms = phase_d._run_billboard_strategy(
        path,
        strategy="partition",
        change_set=change_set,
    )
    if (
        billboard_report.get("build_strategy") != "partition"
        or billboard_report.get("fallback_reason") is not None
    ):
        raise AcceptanceError("Billboard partition update fell back")

    _set_database(path)
    conn = get_db(readonly=False)
    try:
        bump_music_search_revisions(conn, "playback", "billboard", "candidate")
        conn.commit()
        index_report = rebuild_music_search_index(conn)
        if str(index_report.get("status") or "") not in {"ready", "degraded"}:
            raise AcceptanceError("appended candidate index is not ready")
        _build_contexts(conn)
    finally:
        conn.close()
    return change_set


def _run_delta(path: Path, change_set: Any) -> tuple[dict[str, Any], tuple[SnapshotVariant, ...]]:
    from backend.core.db import get_db
    from backend.domains.music_search.snapshot_delta import (
        build_incremental_music_search_snapshot_set,
        build_music_search_incremental_plan,
    )

    plan = build_music_search_incremental_plan(change_set)
    if plan is None:
        raise AcceptanceError("ChangeSet did not produce an incremental search plan")
    _set_database(path)
    conn = get_db(readonly=False)
    try:
        contexts = _build_contexts(conn)
        started = time.perf_counter()
        report = build_incremental_music_search_snapshot_set(conn, contexts, plan)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        if report is None:
            raise AcceptanceError("incremental search snapshot builder rejected the prepared plan")
        return ({**report, "acceptance_elapsed_ms": elapsed_ms}, _snapshot_variants(contexts))
    finally:
        conn.close()


def _run_shared_full(
    path: Path,
    *,
    generation_id: str,
) -> tuple[dict[str, Any], tuple[SnapshotVariant, ...]]:
    from backend.core.db import get_db
    from backend.domains.music_search.snapshot import (
        build_shared_full_music_search_snapshot_set,
    )

    _set_database(path)
    conn = get_db(readonly=False)
    try:
        contexts = _build_contexts(conn)
        started = time.perf_counter()
        report = build_shared_full_music_search_snapshot_set(
            conn,
            contexts,
            source_generation_id=generation_id,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        if report is None:
            raise AcceptanceError("shared-full reference builder rejected the prepared generation")
        return ({**report, "acceptance_elapsed_ms": elapsed_ms}, _snapshot_variants(contexts))
    finally:
        conn.close()


def _except_count(
    conn: sqlite3.Connection,
    *,
    left_schema: str,
    right_schema: str,
    table: str,
    columns: tuple[str, ...],
    snapshot_key: str,
) -> int:
    selected = ", ".join(f'"{column}"' for column in columns)
    return int(
        conn.execute(
            f"""SELECT COUNT(*) FROM (
                    SELECT {selected} FROM {left_schema}."{table}" WHERE snapshot_key=?
                    EXCEPT
                    SELECT {selected} FROM {right_schema}."{table}" WHERE snapshot_key=?
                )""",
            (snapshot_key, snapshot_key),
        ).fetchone()[0]
    )


def _compare_snapshot_outputs(
    delta_path: Path,
    full_path: Path,
    variants: tuple[SnapshotVariant, ...],
    *,
    baseline_digest: str,
    appended_digest: str,
) -> dict[str, Any]:
    conn = sqlite3.connect(delta_path)
    try:
        conn.execute("ATTACH DATABASE ? AS full", (str(full_path),))
        reports: list[dict[str, Any]] = []
        all_contexts_equal = True
        all_ledgers_equal = True
        lineage_ready = True
        for variant in variants:
            fingerprint = variant.fingerprint
            entity_delta_only = _except_count(
                conn,
                left_schema="main",
                right_schema="full",
                table="music_search_entity_context",
                columns=ENTITY_CONTEXT_COLUMNS,
                snapshot_key=fingerprint,
            )
            entity_full_only = _except_count(
                conn,
                left_schema="full",
                right_schema="main",
                table="music_search_entity_context",
                columns=ENTITY_CONTEXT_COLUMNS,
                snapshot_key=fingerprint,
            )
            ledger_delta_only = _except_count(
                conn,
                left_schema="main",
                right_schema="full",
                table="music_search_weekly_chart_context",
                columns=WEEKLY_LEDGER_COLUMNS,
                snapshot_key=fingerprint,
            )
            ledger_full_only = _except_count(
                conn,
                left_schema="full",
                right_schema="main",
                table="music_search_weekly_chart_context",
                columns=WEEKLY_LEDGER_COLUMNS,
                snapshot_key=fingerprint,
            )
            entity_rows = int(
                conn.execute(
                    "SELECT COUNT(*) FROM music_search_entity_context WHERE snapshot_key=?",
                    (fingerprint,),
                ).fetchone()[0]
            )
            full_entity_rows = int(
                conn.execute(
                    "SELECT COUNT(*) FROM full.music_search_entity_context WHERE snapshot_key=?",
                    (fingerprint,),
                ).fetchone()[0]
            )
            ledger_rows = int(
                conn.execute(
                    "SELECT COUNT(*) FROM music_search_weekly_chart_context WHERE snapshot_key=?",
                    (fingerprint,),
                ).fetchone()[0]
            )
            full_ledger_rows = int(
                conn.execute(
                    "SELECT COUNT(*) FROM full.music_search_weekly_chart_context WHERE snapshot_key=?",
                    (fingerprint,),
                ).fetchone()[0]
            )
            meta = conn.execute(
                """SELECT source_generation_id, source_dataset_digest, base_snapshot_key,
                          build_strategy, dependency_digest, change_set_digest
                   FROM music_search_snapshot_meta WHERE snapshot_key=?""",
                (fingerprint,),
            ).fetchone()
            base = (
                conn.execute(
                    """SELECT source_dataset_digest, build_strategy, dependency_digest
                       FROM music_search_snapshot_meta WHERE snapshot_key=?""",
                    (str(meta[2]),),
                ).fetchone()
                if meta is not None and meta[2]
                else None
            )
            variant_lineage = bool(
                meta is not None
                and meta[0]
                and str(meta[1] or "") == appended_digest
                and meta[2]
                and str(meta[3] or "") == "delta"
                and meta[4]
                and meta[5]
                and base is not None
                and str(base[0] or "") == baseline_digest
                and str(base[1] or "") == "shared_full"
                and str(base[2] or "") == str(meta[4] or "")
            )
            context_equal = bool(
                entity_delta_only == 0 and entity_full_only == 0 and entity_rows == full_entity_rows
            )
            ledger_equal = bool(
                ledger_delta_only == 0 and ledger_full_only == 0 and ledger_rows == full_ledger_rows
            )
            all_contexts_equal = all_contexts_equal and context_equal
            all_ledgers_equal = all_ledgers_equal and ledger_equal
            lineage_ready = lineage_ready and variant_lineage
            reports.append(
                {
                    "merge_level": variant.merge_level,
                    "dynamic_threshold": variant.dynamic_threshold,
                    "entity_rows": entity_rows,
                    "reference_entity_rows": full_entity_rows,
                    "entity_delta_only_rows": entity_delta_only,
                    "entity_reference_only_rows": entity_full_only,
                    "ledger_rows": ledger_rows,
                    "reference_ledger_rows": full_ledger_rows,
                    "ledger_delta_only_rows": ledger_delta_only,
                    "ledger_reference_only_rows": ledger_full_only,
                    "lineage_ready": variant_lineage,
                    "passed": context_equal and ledger_equal and variant_lineage,
                }
            )
        return {
            "passed": (
                all_contexts_equal and all_ledgers_equal and lineage_ready and len(reports) == 4
            ),
            "contexts_equal": all_contexts_equal,
            "weekly_ledgers_equal": all_ledgers_equal,
            "delta_lineage_ready": lineage_ready and len(reports) == 4,
            "variants": reports,
        }
    finally:
        conn.close()


def _ledger_count(
    conn: sqlite3.Connection,
    *,
    schema: str,
    snapshot_key: str,
    week: date,
) -> int:
    return int(
        conn.execute(
            f"""SELECT COUNT(*) FROM {schema}.music_search_weekly_chart_context
                WHERE snapshot_key=? AND week=?""",
            (snapshot_key, week.isoformat()),
        ).fetchone()[0]
    )


def _historical_ledger_except_count(
    conn: sqlite3.Connection,
    *,
    left_schema: str,
    left_key: str,
    right_schema: str,
    right_key: str,
    before_week: date,
) -> int:
    selected = ", ".join(f'"{column}"' for column in WEEKLY_LEDGER_COLUMNS)
    return int(
        conn.execute(
            f"""SELECT COUNT(*) FROM (
                    SELECT {selected}
                    FROM {left_schema}.music_search_weekly_chart_context
                    WHERE snapshot_key=? AND week<?
                    EXCEPT
                    SELECT {selected}
                    FROM {right_schema}.music_search_weekly_chart_context
                    WHERE snapshot_key=? AND week<?
                )""",
            (
                left_key,
                before_week.isoformat(),
                right_key,
                before_week.isoformat(),
            ),
        ).fetchone()[0]
    )


def _compare_cross_week_transition(
    baseline_path: Path,
    delta_path: Path,
    full_path: Path,
    *,
    baseline_variants: tuple[SnapshotVariant, ...],
    target_variants: tuple[SnapshotVariant, ...],
    boundary: CrossWeekBoundary,
) -> dict[str, Any]:
    conn = sqlite3.connect(delta_path)
    try:
        conn.execute("ATTACH DATABASE ? AS baseline", (str(baseline_path),))
        conn.execute("ATTACH DATABASE ? AS full", (str(full_path),))
        baseline_by_variant = {
            (variant.merge_level, variant.dynamic_threshold): variant
            for variant in baseline_variants
        }
        reports: list[dict[str, Any]] = []
        passed = len(target_variants) == 4 and len(baseline_by_variant) == 4
        for target in target_variants:
            baseline = baseline_by_variant.get((target.merge_level, target.dynamic_threshold))
            if baseline is None:
                passed = False
                continue
            base_previous = _ledger_count(
                conn,
                schema="baseline",
                snapshot_key=baseline.fingerprint,
                week=boundary.previous_open_week,
            )
            base_current = _ledger_count(
                conn,
                schema="baseline",
                snapshot_key=baseline.fingerprint,
                week=boundary.current_open_week,
            )
            delta_previous = _ledger_count(
                conn,
                schema="main",
                snapshot_key=target.fingerprint,
                week=boundary.previous_open_week,
            )
            full_previous = _ledger_count(
                conn,
                schema="full",
                snapshot_key=target.fingerprint,
                week=boundary.previous_open_week,
            )
            delta_current = _ledger_count(
                conn,
                schema="main",
                snapshot_key=target.fingerprint,
                week=boundary.current_open_week,
            )
            full_current = _ledger_count(
                conn,
                schema="full",
                snapshot_key=target.fingerprint,
                week=boundary.current_open_week,
            )
            delta_historical_only = _historical_ledger_except_count(
                conn,
                left_schema="main",
                left_key=target.fingerprint,
                right_schema="baseline",
                right_key=baseline.fingerprint,
                before_week=boundary.previous_open_week,
            )
            baseline_historical_only = _historical_ledger_except_count(
                conn,
                left_schema="baseline",
                left_key=baseline.fingerprint,
                right_schema="main",
                right_key=target.fingerprint,
                before_week=boundary.previous_open_week,
            )
            baseline_excluded = base_previous == 0 and base_current == 0
            completed_published = delta_previous > 0 and delta_previous == full_previous
            current_excluded = delta_current == 0 and full_current == 0
            history_unchanged = delta_historical_only == 0 and baseline_historical_only == 0
            variant_passed = bool(
                baseline_excluded and completed_published and current_excluded and history_unchanged
            )
            passed = passed and variant_passed
            reports.append(
                {
                    "merge_level": target.merge_level,
                    "dynamic_threshold": target.dynamic_threshold,
                    "baseline_completed_week_rows": base_previous,
                    "delta_completed_week_rows": delta_previous,
                    "reference_completed_week_rows": full_previous,
                    "delta_current_open_week_rows": delta_current,
                    "reference_current_open_week_rows": full_current,
                    "delta_historical_only_rows": delta_historical_only,
                    "baseline_historical_only_rows": baseline_historical_only,
                    "baseline_open_week_excluded": baseline_excluded,
                    "newly_completed_week_published": completed_published,
                    "current_open_week_excluded": current_excluded,
                    "historical_weeks_unchanged": history_unchanged,
                    "passed": variant_passed,
                }
            )
        return {
            "status": "passed" if passed and len(reports) == 4 else "failed",
            "newly_completed_week_count": 1,
            "open_week_advanced_by_one": True,
            "baseline_open_week_excluded": bool(
                reports and all(item["baseline_open_week_excluded"] for item in reports)
            ),
            "newly_completed_week_published": bool(
                reports and all(item["newly_completed_week_published"] for item in reports)
            ),
            "current_open_week_excluded": bool(
                reports and all(item["current_open_week_excluded"] for item in reports)
            ),
            "historical_weeks_unchanged": bool(
                reports and all(item["historical_weeks_unchanged"] for item in reports)
            ),
            "passed": passed and len(reports) == 4,
            "variants": reports,
        }
    finally:
        conn.close()


def _assert_baseline_open_weeks_unpublished(
    path: Path,
    variants: tuple[SnapshotVariant, ...],
    boundary: CrossWeekBoundary,
) -> None:
    conn = sqlite3.connect(path)
    try:
        for variant in variants:
            if _ledger_count(
                conn,
                schema="main",
                snapshot_key=variant.fingerprint,
                week=boundary.previous_open_week,
            ) or _ledger_count(
                conn,
                schema="main",
                snapshot_key=variant.fingerprint,
                week=boundary.current_open_week,
            ):
                raise AcceptanceError("baseline published an open-week ledger")
    finally:
        conn.close()


def _database_digest(path: Path) -> str:
    conn = sqlite3.connect(phase_d._readonly_uri(path), uri=True)
    try:
        row = conn.execute(
            "SELECT dataset_digest FROM playback_import_state WHERE state_id=1"
        ).fetchone()
        return str(row[0] or "") if row else ""
    finally:
        conn.close()


def _run_acceptance(args: argparse.Namespace, workdir: Path) -> dict[str, Any]:
    source = args.source_db.expanduser().resolve(strict=True)
    source_before = source.stat()
    source_profile = phase_d._database_profile(source)
    if source_profile["quick_check"] != "ok":
        raise AcceptanceError("source database failed quick_check")

    baseline_path = workdir / "baseline.db"
    delta_path = workdir / "delta.db"
    full_path = workdir / "shared-full.db"
    phase_d._online_backup(source, baseline_path)
    backup_profile = phase_d._database_profile(baseline_path)
    if backup_profile["play_count"] != source_profile["play_count"]:
        raise AcceptanceError("online backup changed the source play count")

    baseline, billboard_build = phase_d._prepare_baseline(baseline_path)
    cross_week_boundary = (
        _cross_week_boundary_for_database(
            baseline_path,
            margin_seconds=args.append_gap_seconds,
        )
        if args.scenario == "cross-week"
        else None
    )
    baseline_search = _prepare_baseline_search(
        baseline_path,
        generation_id=str(baseline["generation_id"]),
    )
    baseline_variants = tuple(baseline_search["variants"])
    if cross_week_boundary is not None:
        _assert_baseline_open_weeks_unpublished(
            baseline_path,
            baseline_variants,
            cross_week_boundary,
        )
    phase_d._online_backup(baseline_path, delta_path)
    phase_d._online_backup(baseline_path, full_path)

    append_gap = (
        cross_week_boundary.gap_seconds
        if cross_week_boundary is not None
        else args.append_gap_seconds
    )
    delta_change_set = _prepare_appended_search(
        delta_path,
        baseline=baseline,
        gap=append_gap,
        scenario=args.scenario,
        cross_week_boundary=cross_week_boundary,
    )
    full_change_set = _prepare_appended_search(
        full_path,
        baseline=baseline,
        gap=append_gap,
        scenario=args.scenario,
        cross_week_boundary=cross_week_boundary,
    )
    if delta_change_set.to_dict() != full_change_set.to_dict():
        raise AcceptanceError("delta and reference copies produced different ChangeSets")
    appended_digest = _database_digest(delta_path)
    if not appended_digest or appended_digest != _database_digest(full_path):
        raise AcceptanceError("appended copies do not share one dataset digest")

    delta_report, delta_variants = _run_delta(delta_path, delta_change_set)
    full_report, full_variants = _run_shared_full(
        full_path,
        generation_id=str(full_change_set.generation_id),
    )
    if delta_variants != full_variants:
        raise AcceptanceError("delta and reference contexts do not match")
    equivalence = _compare_snapshot_outputs(
        delta_path,
        full_path,
        delta_variants,
        baseline_digest=str(baseline["dataset_digest"]),
        appended_digest=appended_digest,
    )
    week_transition = (
        _compare_cross_week_transition(
            baseline_path,
            delta_path,
            full_path,
            baseline_variants=baseline_variants,
            target_variants=delta_variants,
            boundary=cross_week_boundary,
        )
        if cross_week_boundary is not None
        else {
            "status": "not_applicable",
            "newly_completed_week_count": 0,
            "passed": True,
            "variants": [],
        }
    )
    chart_strategy = str(delta_report.get("chart_strategy") or "")
    chart_strategy_gate = (
        bool(chart_strategy and chart_strategy != "clone_unchanged_open_week")
        if args.scenario == "cross-week"
        else chart_strategy == "clone_unchanged_open_week"
    )
    strategy_gate = bool(
        delta_report.get("strategy") == "incremental_snapshot_delta"
        and delta_report.get("lifetime_scan") is False
        and delta_report.get("base_snapshot_count") == 4
        and delta_report.get("ready_count") == 4
        and full_report.get("strategy") == "shared_full_snapshot_rebuild"
        and full_report.get("ready_count") == 4
        and chart_strategy_gate
    )

    source_after = source.stat()
    source_unchanged = (
        source_before.st_size == source_after.st_size
        and source_before.st_mtime_ns == source_after.st_mtime_ns
        and source_before.st_ino == source_after.st_ino
    )
    if not source_unchanged:
        raise AcceptanceError("source database changed during acceptance")
    passed = bool(equivalence["passed"] and week_transition["passed"] and strategy_gate)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "passed" if passed else "failed",
        "scenario": args.scenario,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "source": source_profile,
        "backup": backup_profile,
        "synthetic_baseline": {
            "used": True,
            "validates_phase_b_fingerprints": False,
            "billboard_elapsed_ms": billboard_build.get("elapsed_ms"),
            "search_elapsed_ms": baseline_search["elapsed_ms"],
            "search_entity_rows": baseline_search["entity_rows"],
            "search_ledger_rows": baseline_search["ledger_rows"],
        },
        "append": {
            "added_count": int(delta_change_set.added_count),
            "removed_count": int(delta_change_set.removed_count),
            "billboard_scope_exact": bool(delta_change_set.billboard_scope_exact),
            "same_open_week": args.scenario == "within-open-week",
            "open_week_advanced_by_one": args.scenario == "cross-week",
            "affected_week_count": len(delta_change_set.billboard_weeks),
            "newly_completed_week_count": int(week_transition["newly_completed_week_count"]),
        },
        "delta": {
            "strategy": delta_report.get("strategy"),
            "elapsed_ms": delta_report.get("acceptance_elapsed_ms"),
            "ready_count": delta_report.get("ready_count"),
            "base_snapshot_count": delta_report.get("base_snapshot_count"),
            "lifetime_scan": delta_report.get("lifetime_scan"),
            "chart_strategy": delta_report.get("chart_strategy"),
        },
        "reference": {
            "strategy": full_report.get("strategy"),
            "elapsed_ms": full_report.get("acceptance_elapsed_ms"),
            "ready_count": full_report.get("ready_count"),
        },
        "equivalence": equivalence,
        "week_transition": week_transition,
        "privacy": PRIVACY_REPORT,
        "workdir_preserved": bool(args.keep_workdir),
        "gate": {
            "scope_proven": True,
            "same_open_week": args.scenario == "within-open-week",
            "open_week_advanced_by_one": args.scenario == "cross-week",
            "strategy_valid": strategy_gate,
            "four_contexts_equivalent": bool(equivalence["contexts_equal"]),
            "weekly_ledgers_equivalent": bool(equivalence["weekly_ledgers_equal"]),
            "week_transition_valid": bool(week_transition["passed"]),
            "delta_lineage_ready": bool(equivalence["delta_lineage_ready"]),
            "passed": passed,
        },
    }


def _emit_report(report: dict[str, Any], args: argparse.Namespace) -> None:
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.json_output:
        output = args.json_output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    if args.json:
        print(payload, end="")
    else:
        gate = report.get("gate") or {}
        print(
            "Phase D2 search delta acceptance: "
            f"status={report.get('status')} "
            f"scenario={report.get('scenario')} "
            f"contexts={gate.get('four_contexts_equivalent')} "
            f"ledgers={gate.get('weekly_ledgers_equivalent')} "
            f"lineage={gate.get('delta_lineage_ready')}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report: dict[str, Any]
    try:
        source = args.source_db.expanduser().resolve(strict=True)
        with phase_d.managed_workdir(source, args.workdir, keep=args.keep_workdir) as workdir:
            if args.json_output and not args.keep_workdir:
                output = args.json_output.expanduser().resolve()
                if phase_d._is_relative_to(output, workdir):
                    raise AcceptanceError(
                        "--json-output inside the temporary workdir would be deleted"
                    )
            report = _run_acceptance(args, workdir)
    except Exception as exc:
        report = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "status": "failed",
            "scenario": args.scenario,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "error": {"type": type(exc).__name__},
            "privacy": PRIVACY_REPORT,
            "workdir_preserved": bool(args.keep_workdir),
            "gate": {
                "scope_proven": False,
                "same_open_week": False,
                "open_week_advanced_by_one": False,
                "strategy_valid": False,
                "four_contexts_equivalent": False,
                "weekly_ledgers_equivalent": False,
                "week_transition_valid": False,
                "delta_lineage_ready": False,
                "passed": False,
            },
        }
    _emit_report(report, args)
    return 0 if (report.get("gate") or {}).get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
