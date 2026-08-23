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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core import db as db_mod  # noqa: E402
from scripts import phase_d_real_db_acceptance as phase_d  # noqa: E402

REPORT_SCHEMA_VERSION = "phase_d2_search_delta_acceptance_v1"
PRIVACY_REPORT = {
    "database_path_emitted": False,
    "entity_content_emitted": False,
    "listening_history_rows_emitted": False,
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


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare a true within-open-week search snapshot delta with the "
            "shared-full reference on disposable database copies"
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
        help="Preserve the private database copies for local debugging",
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
    args = parser.parse_args(argv)
    if args.append_gap_seconds < 0:
        parser.error("--append-gap-seconds must be non-negative")
    return args


def _set_database(path: Path) -> None:
    db_mod.DB_PATH = str(path.resolve(strict=True))


def _build_contexts(conn: sqlite3.Connection) -> tuple[Any, ...]:
    from backend.domains.music_search.variants import build_music_search_variant_contexts
    from backend.services.music_search_maintenance_service import _current_filter_values

    contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
    variants = {(int(context.merge_level), bool(context.dynamic_threshold)) for context in contexts}
    if len(contexts) != 6 or len({context.filter_fingerprint for context in contexts}) != 6:
        raise AcceptanceError("music-search contexts are not an exact six-variant set")
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
        if lineage_count != 6 or ledger_rows <= 0:
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
    if any(week < current_open for week in affected_weeks):
        raise AcceptanceError("tail append affected a completed Billboard week")
    if not bool(getattr(change_set, "billboard_scope_exact", False)):
        raise AcceptanceError("tail append lacks an exact Billboard scope")


def _prepare_appended_search(path: Path, *, baseline: dict[str, Any], gap: float) -> Any:
    from backend.core.db import get_db
    from backend.domains.music_search.index import rebuild_music_search_index
    from backend.domains.music_search.revisions import bump_music_search_revisions

    change_set = phase_d._append_tail(path, baseline=baseline, gap_seconds=gap)
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
        raise AcceptanceError("same-week Billboard partition update fell back")

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
        raise AcceptanceError("same-week ChangeSet did not produce an incremental search plan")
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
                all_contexts_equal and all_ledgers_equal and lineage_ready and len(reports) == 6
            ),
            "contexts_equal": all_contexts_equal,
            "weekly_ledgers_equal": all_ledgers_equal,
            "delta_lineage_ready": lineage_ready and len(reports) == 6,
            "variants": reports,
        }
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
    baseline_search = _prepare_baseline_search(
        baseline_path,
        generation_id=str(baseline["generation_id"]),
    )
    phase_d._online_backup(baseline_path, delta_path)
    phase_d._online_backup(baseline_path, full_path)

    delta_change_set = _prepare_appended_search(
        delta_path,
        baseline=baseline,
        gap=args.append_gap_seconds,
    )
    full_change_set = _prepare_appended_search(
        full_path,
        baseline=baseline,
        gap=args.append_gap_seconds,
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
    strategy_gate = bool(
        delta_report.get("strategy") == "incremental_snapshot_delta"
        and delta_report.get("lifetime_scan") is False
        and delta_report.get("base_snapshot_count") == 6
        and delta_report.get("ready_count") == 6
        and full_report.get("strategy") == "shared_full_snapshot_rebuild"
        and full_report.get("ready_count") == 6
    )

    source_after = source.stat()
    source_unchanged = (
        source_before.st_size == source_after.st_size
        and source_before.st_mtime_ns == source_after.st_mtime_ns
        and source_before.st_ino == source_after.st_ino
    )
    if not source_unchanged:
        raise AcceptanceError("source database changed during acceptance")
    passed = bool(equivalence["passed"] and strategy_gate)
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "passed" if passed else "failed",
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
            "same_open_week": True,
            "affected_week_count": len(delta_change_set.billboard_weeks),
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
        "privacy": PRIVACY_REPORT,
        "workdir_preserved": bool(args.keep_workdir),
        "gate": {
            "same_open_week": True,
            "strategy_valid": strategy_gate,
            "six_contexts_equivalent": bool(equivalence["contexts_equal"]),
            "weekly_ledgers_equivalent": bool(equivalence["weekly_ledgers_equal"]),
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
            f"contexts={gate.get('six_contexts_equivalent')} "
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
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "error": {"type": type(exc).__name__},
            "privacy": PRIVACY_REPORT,
            "workdir_preserved": bool(args.keep_workdir),
            "gate": {
                "same_open_week": False,
                "strategy_valid": False,
                "six_contexts_equivalent": False,
                "weekly_ledgers_equivalent": False,
                "delta_lineage_ready": False,
                "passed": False,
            },
        }
    _emit_report(report, args)
    return 0 if (report.get("gate") or {}).get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
