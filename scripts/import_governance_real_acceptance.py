#!/usr/bin/env python3
"""Run one isolated old-to-new real import acceptance sample.

The caller must provide an import-before SQLite seed plus the old and new raw
Spotify export directories.  All mutations are confined to a fresh workdir
outside the repository.  Run this command in three independent processes to
collect comparable cold samples.
"""

from __future__ import annotations

import argparse
import json
import resource
import sqlite3
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import incremental_import_end_to_end_acceptance as e2e  # noqa: E402

SCHEMA_VERSION = "import_governance_real_acceptance_v2"
EXPECTED_OLD_RECORDS = 92_908
EXPECTED_NEW_RECORDS = 94_760
EXPECTED_ADDED_RECORDS = 1_852
EXPECTED_LATE_RECORDS = 2


def _peak_rss_bytes() -> int:
    """Normalize ru_maxrss to bytes (macOS reports bytes, Linux reports KiB)."""

    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return peak if sys.platform == "darwin" else peak * 1024


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-seed-db", type=Path, required=True)
    parser.add_argument("--old-streaming-dir", type=Path, required=True)
    parser.add_argument("--new-streaming-dir", type=Path, required=True)
    parser.add_argument("--account-dir", type=Path, required=True)
    parser.add_argument("--frozen-metadata-db", type=Path, required=True)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--sample-id", required=True)
    return parser.parse_args(argv)


def _metrics(path: Path, *, generation_id: str | None = None) -> dict[str, Any]:
    conn = sqlite3.connect(path)
    try:
        where = " WHERE import_generation_id=?" if generation_id else ""
        params = (generation_id,) if generation_id else ()
        count, duration_ms = conn.execute(
            f"SELECT COUNT(*), COALESCE(SUM(ms_played), 0) FROM plays{where}",
            params,
        ).fetchone()
        first_ts, latest_ts = conn.execute(
            f"SELECT MIN(ts), MAX(ts) FROM plays{where}",
            params,
        ).fetchone()
        return {
            "record_count": int(count),
            "duration_ms": int(duration_ms),
            "first_ts": str(first_ts) if first_ts else None,
            "latest_ts": str(latest_ts) if latest_ts else None,
        }
    finally:
        conn.close()


def _state_vector(path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(path)
    try:
        active = conn.execute(
            """SELECT active_generation_id,dataset_digest,publication_state
               FROM playback_import_state WHERE state_id=1"""
        ).fetchone()
        revisions: dict[str, list[list[Any]]] = {}
        for table in (
            "analysis_source_revisions",
            "album_project_revision_state",
            "l3_album_attribution_revision_state",
            "music_search_revision_state",
            "music_search_snapshot_variant_state",
        ):
            columns = [str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')]
            quoted = ",".join(f'"{column}"' for column in columns)
            revisions[table] = (
                [list(row) for row in conn.execute(f'SELECT {quoted} FROM "{table}"').fetchall()]
                if columns
                else []
            )
        return {
            "active": list(active) if active is not None else None,
            "revisions": revisions,
        }
    finally:
        conn.close()


def _install_frozen_metadata(source_path: Path, target_path: Path) -> dict[str, int]:
    """Install one read-only provider snapshot into a disposable database."""

    source = sqlite3.connect(e2e._readonly_uri(source_path), uri=True)
    target = sqlite3.connect(target_path)
    counts: dict[str, int] = {}
    try:
        source.execute("PRAGMA query_only=ON")
        for table in ("spotify_track_meta", "spotify_album_meta", "spotify_artist_meta"):
            columns = [str(row[1]) for row in source.execute(f'PRAGMA table_info("{table}")')]
            target_columns = {
                str(row[1]) for row in target.execute(f'PRAGMA table_info("{table}")')
            }
            if not columns or not set(columns).issubset(target_columns):
                raise e2e.AcceptanceError(f"incompatible frozen metadata table: {table}")
            quoted = ",".join(f'"{column}"' for column in columns)
            rows = source.execute(f'SELECT {quoted} FROM "{table}"').fetchall()
            placeholders = ",".join("?" for _ in columns)
            target.execute(f'DELETE FROM "{table}"')
            target.executemany(
                f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})',
                rows,
            )
            counts[table] = len(rows)
        target.commit()
        return counts
    finally:
        target.close()
        source.close()


def _frozen_metadata_digest(path: Path) -> str:
    conn = sqlite3.connect(e2e._readonly_uri(path), uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        payload: dict[str, list[list[Any]]] = {}
        for table in ("spotify_track_meta", "spotify_album_meta", "spotify_artist_meta"):
            columns = [str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')]
            quoted = ",".join(f'"{column}"' for column in columns)
            payload[table] = [
                list(row)
                for row in conn.execute(
                    f'SELECT {quoted} FROM "{table}" ORDER BY 1'
                ).fetchall()
            ]
        return e2e._digest(payload)
    finally:
        conn.close()


def run(args: argparse.Namespace) -> dict[str, Any]:
    old_seed = args.old_seed_db.expanduser().resolve(strict=True)
    old_source = args.old_streaming_dir.expanduser().resolve(strict=True)
    new_source = args.new_streaming_dir.expanduser().resolve(strict=True)
    account = args.account_dir.expanduser().resolve(strict=True)
    frozen_metadata = args.frozen_metadata_db.expanduser().resolve(strict=True)
    workdir = e2e.validate_workdir(args.workdir, old_seed)
    output = args.json_output.expanduser().resolve(strict=False)
    if output == workdir or output.is_relative_to(workdir):
        raise e2e.AcceptanceError("json output must survive workdir cleanup")

    old_guard = e2e._source_guard(old_seed)
    metadata_guard = e2e._source_guard(frozen_metadata)
    metadata_digest_before = _frozen_metadata_digest(frozen_metadata)
    old_manifest = e2e._raw_bundle_manifest(old_source)
    new_manifest = e2e._raw_bundle_manifest(new_source)
    workdir.mkdir(parents=True, mode=0o700)
    started = time.perf_counter()
    baseline_db = workdir / "baseline.db"
    incremental_db = workdir / "incremental.db"
    replacement_db = workdir / "replacement.db"
    e2e._online_backup(old_seed, baseline_db)

    baseline_result, _unused_baseline_derived, baseline_timings = e2e._phase(
        baseline_db,
        old_source,
        account,
        expected_relation="baseline_required",
        mode="replace",
        generation_id=f"s6-{args.sample_id}-old-baseline",
        strategy="full",
        maintain_derived=False,
    )
    frozen_metadata_counts = _install_frozen_metadata(frozen_metadata, baseline_db)
    baseline_derived, baseline_derived_timings = e2e._run_derived(
        baseline_db,
        baseline_result["change_set"],
    )
    baseline_timings.update(
        {f"frozen_metadata_{key}": value for key, value in baseline_derived_timings.items()}
    )
    baseline_timings["end_to_end_ms"] = round(
        baseline_timings["end_to_end_ms"] + sum(baseline_derived_timings.values()),
        3,
    )
    baseline_metrics = _metrics(baseline_db)
    old_latest_ts = baseline_metrics["latest_ts"]
    baseline_noop, baseline_noop_ms = e2e._timed(
        lambda: e2e._assess(baseline_db, old_source, account)
    )
    try:
        baseline_noop_relation = baseline_noop.plan.relation.value
    finally:
        if baseline_noop.staging is not None:
            baseline_noop.staging.close()

    e2e._online_backup(baseline_db, incremental_db)
    e2e._online_backup(baseline_db, replacement_db)
    incremental_generation = f"s6-{args.sample_id}-incremental"
    incremental_result, incremental_derived, incremental_timings = e2e._phase(
        incremental_db,
        new_source,
        account,
        expected_relation="snapshot_superset",
        mode="append",
        generation_id=incremental_generation,
        strategy="incremental",
    )
    incremental_metrics = _metrics(incremental_db)
    added_metrics = _metrics(incremental_db, generation_id=incremental_generation)
    conn = sqlite3.connect(incremental_db)
    try:
        late_count = int(
            conn.execute(
                """SELECT COUNT(*) FROM plays
                   WHERE import_generation_id=? AND ts < ?""",
                (incremental_generation, old_latest_ts),
            ).fetchone()[0]
        )
    finally:
        conn.close()

    noop_state_before = _state_vector(incremental_db)
    noop_stat_before = incremental_db.stat()
    noop_assessment, noop_ms = e2e._timed(
        lambda: e2e._assess(incremental_db, new_source, account)
    )
    try:
        noop_relation = noop_assessment.plan.relation.value
    finally:
        if noop_assessment.staging is not None:
            noop_assessment.staging.close()
    noop_stat_after = incremental_db.stat()
    noop_state_after = _state_vector(incremental_db)
    noop_no_write = bool(
        noop_relation == "identical"
        and noop_stat_before.st_size == noop_stat_after.st_size
        and noop_stat_before.st_mtime_ns == noop_stat_after.st_mtime_ns
        and noop_state_before == noop_state_after
    )

    replacement_result, replacement_derived, replacement_timings = e2e._phase(
        replacement_db,
        new_source,
        account,
        expected_relation="snapshot_superset",
        mode="replace",
        generation_id=f"s6-{args.sample_id}-replacement",
        strategy="full",
        requested_mode="replace",
    )
    replacement_metrics = _metrics(replacement_db)
    incremental_snapshot = e2e._semantic_snapshot(incremental_db, incremental_derived)
    replacement_snapshot = e2e._semantic_snapshot(replacement_db, replacement_derived)
    equivalence = e2e._equivalence(incremental_snapshot, replacement_snapshot)
    open_edge_gate = bool(
        incremental_snapshot["billboard"]["latest_aggregate_week"]
        and incremental_metrics["latest_ts"]
        and incremental_snapshot["home"]["source_latest_date"]
    )
    source_unchanged = bool(
        e2e._verify_source_guard(old_guard)
        and metadata_digest_before == _frozen_metadata_digest(frozen_metadata)
        and old_manifest == e2e._raw_bundle_manifest(old_source)
        and new_manifest == e2e._raw_bundle_manifest(new_source)
    )
    gates = {
        "source_unchanged": source_unchanged,
        "old_baseline_initialized": baseline_result["active_records"] == EXPECTED_OLD_RECORDS,
        "old_baseline_noop": baseline_noop_relation == "identical",
        "snapshot_superset": incremental_result["inserted_records"] == EXPECTED_ADDED_RECORDS,
        "removed_zero": incremental_result["change_set"].removed_count == 0,
        "final_record_count": incremental_metrics["record_count"] == EXPECTED_NEW_RECORDS,
        "replacement_record_count": replacement_metrics["record_count"]
        == EXPECTED_NEW_RECORDS,
        "late_records": late_count == EXPECTED_LATE_RECORDS,
        "four_search_variants": incremental_derived["search"]["ready_count"] == 4,
        "noop_no_write": noop_no_write,
        "semantic_equivalence": equivalence["passed"],
        "open_edge_non_billboard_data_retained": open_edge_gate,
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "sample_id": args.sample_id,
        "status": "passed" if all(gates.values()) else "failed",
        "passed": all(gates.values()),
        "privacy": {
            "writes_confined_to_disposable_workdir": True,
            "source_paths_emitted": False,
            "raw_rows_emitted": False,
        },
        "gates": gates,
        "source_seed": old_guard["profile"],
        "frozen_metadata": {
            "source_profile": metadata_guard["profile"],
            "row_counts": frozen_metadata_counts,
            "content_digest": metadata_digest_before,
        },
        "manifests": {
            "old_file_count": len(old_manifest),
            "new_file_count": len(new_manifest),
        },
        "baseline": {
            "metrics": baseline_metrics,
            "relation": "baseline_required",
            "identical_recheck_relation": baseline_noop_relation,
            "derived": baseline_derived,
            "timings_ms": {**baseline_timings, "identical_recheck": baseline_noop_ms},
        },
        "incremental": {
            "relation": "snapshot_superset",
            "inserted_records": incremental_result["inserted_records"],
            "unchanged_records": incremental_result["unchanged_records"],
            "removed_records": incremental_result["change_set"].removed_count,
            "late_record_count": late_count,
            "metrics": incremental_metrics,
            "added_metrics": added_metrics,
            "change_set": incremental_result["change_set"].to_dict(),
            "derived": incremental_derived,
            "timings_ms": incremental_timings,
        },
        "noop": {
            "relation": noop_relation,
            "no_write": noop_no_write,
            "preflight_ms": noop_ms,
        },
        "replacement": {
            "metrics": replacement_metrics,
            "derived": replacement_derived,
            "timings_ms": replacement_timings,
        },
        "equivalence": equivalence,
        "public_incremental": e2e._public_projection(incremental_snapshot),
        "public_replacement": e2e._public_projection(replacement_snapshot),
        "resource": {
            "peak_rss_bytes": _peak_rss_bytes(),
            "peak_rss_mib": round(_peak_rss_bytes() / (1024 * 1024), 3),
            "wall_ms": round((time.perf_counter() - started) * 1000, 3),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = run(args)
    print(
        f"status={report['status']} sample={report['sample_id']} "
        f"inserted={report['incremental']['inserted_records']} "
        f"equivalent={report['equivalence']['passed']}"
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
