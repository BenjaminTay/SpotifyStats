#!/usr/bin/env python3
"""Run privacy-safe Phase E acceptance on disposable real-database copies."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core import db as db_mod  # noqa: E402

REPORT_SCHEMA_VERSION = "phase_e_real_db_acceptance_v1"
CORRECTION_GENERATION_ID = "phase-e-historical-correction"
BASE_GENERATION_ID = "phase-e-synthetic-baseline"
TABLES = (
    "agg_weekly_tracks",
    "agg_weekly_albums",
    "agg_weekly_track_sources",
    "agg_weekly_artists",
)


class AcceptanceError(RuntimeError):
    """A fail-closed acceptance violation."""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, default=Path(db_mod.DB_PATH))
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--keep-workdir", action="store_true")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--_kill-worker-db", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--_kill-worker-input", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if bool(args._kill_worker_db) != bool(args._kill_worker_input):
        parser.error("internal kill worker requires both database and input")
    return args


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_workdir(source_db: Path, workdir: Path) -> tuple[Path, Path]:
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
        raise AcceptanceError("work directory must not already exist")
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
        target = Path(tempfile.mkdtemp(prefix="spotifystats-phase-e-", dir="/tmp")).resolve()
        shutil.rmtree(target)
    else:
        target = requested
    _, target = validate_workdir(source, target)
    target.mkdir(parents=True, mode=0o700)
    try:
        yield target
    finally:
        if not keep and target.exists():
            shutil.rmtree(target)


def _readonly_uri(path: Path) -> str:
    return f"file:{quote(str(path.resolve()), safe='/')}?mode=ro"


def _online_backup(source_path: Path, target_path: Path) -> None:
    if target_path.exists():
        raise AcceptanceError("backup target already exists")
    source = sqlite3.connect(_readonly_uri(source_path), uri=True)
    target = sqlite3.connect(target_path)
    try:
        source.execute("PRAGMA query_only=ON")
        source.backup(target)
        if str(target.execute("PRAGMA quick_check").fetchone()[0]) != "ok":
            raise AcceptanceError("backup failed quick_check")
    finally:
        target.close()
        source.close()


def _set_database(path: Path) -> None:
    db_mod.DB_PATH = str(path)


def _settings(conn: sqlite3.Connection) -> dict[str, Any]:
    from backend.domains.settings.repository import SettingsRepository

    return SettingsRepository(conn).load_all()


def _active_lineage(conn: sqlite3.Connection) -> tuple[str, str, int]:
    row = conn.execute(
        """SELECT active_generation_id, dataset_digest, record_count
           FROM playback_import_state WHERE state_id=1"""
    ).fetchone()
    if row is None or not row[0] or not row[1]:
        raise AcceptanceError("source database has no active fingerprint lineage")
    return str(row[0]), str(row[1]), int(row[2])


def _build_full_baseline(path: Path) -> dict[str, Any]:
    from backend.core.migrations import run_migrations
    from backend.domains.imports.state import (
        publish_playback_import_state,
        summarise_current_playback_dataset,
    )

    _set_database(path)
    run_migrations()
    conn = db_mod.get_db(readonly=False)
    try:
        state = conn.execute(
            """SELECT active_generation_id, dataset_digest, record_count
               FROM playback_import_state WHERE state_id=1"""
        ).fetchone()
        synthetic = not bool(state and state[0] and state[1] and int(state[2] or 0) > 0)
        if synthetic:
            if int(
                conn.execute(
                    "SELECT COUNT(*) FROM plays WHERE content_type IS NULL OR content_type=''"
                ).fetchone()[0]
            ):
                raise AcceptanceError("source copy contains plays without content_type")
            conn.execute(
                """UPDATE plays
                   SET source_fingerprint=printf('%064x', play_id),
                       source_fingerprint_version=1,
                       import_generation_id=?""",
                (BASE_GENERATION_ID,),
            )
            summary = summarise_current_playback_dataset(conn)
            publish_playback_import_state(
                conn,
                generation_id=BASE_GENERATION_ID,
                account_identity_hash=None,
                relation="acceptance_baseline",
                strategy="full",
                summary=summary,
            )
            conn.commit()
        generation_id, _digest, _count = _active_lineage(conn)
        settings = _settings(conn)
    finally:
        conn.close()
    started = time.perf_counter()
    report = db_mod.build_aggregations(
        min_ms=int(settings.get("min_ms", 30_000)),
        music_only=bool(settings.get("music_only", True)),
        week_start_dow=int(settings.get("bb_week_start_dow", 4)),
        week_start_hour=int(settings.get("bb_week_start_hour", 0)),
        dynamic_threshold=True,
        max_merge_gap_minutes=int(settings.get("max_merge_gap_minutes", 5)),
        expected_generation_id=generation_id,
    )
    return {
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "strategy": report.get("build_strategy"),
        "synthetic_fingerprint_baseline": synthetic,
        "validates_source_fingerprints": not synthetic,
    }


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _apply_historical_correction(path: Path):
    from backend.domains.imports.change_set import build_playback_change_set
    from backend.domains.imports.incremental import (
        ImportPlan,
        ImportRelation,
        ImportStrategy,
        RecordIdentity,
    )
    from backend.domains.imports.state import publish_playback_import_state

    _set_database(path)
    conn = db_mod.get_db(readonly=False)
    try:
        old_generation, previous_digest, existing_count = _active_lineage(conn)
        del old_generation
        range_row = conn.execute("SELECT MIN(ts), MAX(ts) FROM plays").fetchone()
        candidate = conn.execute(
            """SELECT * FROM plays
               WHERE track_id IS NOT NULL
                 AND source_fingerprint IS NOT NULL
                 AND ms_played >= 30000
                 AND ts < datetime((SELECT MAX(ts) FROM plays), '-30 days')
               ORDER BY ts, play_id LIMIT 1 OFFSET (
                   SELECT COUNT(*) / 2 FROM plays
                   WHERE track_id IS NOT NULL
                     AND source_fingerprint IS NOT NULL
                     AND ms_played >= 30000
                     AND ts < datetime((SELECT MAX(ts) FROM plays), '-30 days')
               )"""
        ).fetchone()
        if candidate is None:
            raise AcceptanceError("no completed-week correction candidate")
        old = dict(candidate)
        removed = RecordIdentity(str(old["content_type"]), str(old["source_fingerprint"]))
        new_fingerprint = hashlib.sha256(
            f"phase-e-correction\0{old['source_fingerprint']}".encode()
        ).hexdigest()
        added = RecordIdentity(str(old["content_type"]), new_fingerprint)
        columns = [str(row[1]) for row in conn.execute("PRAGMA table_info(plays)")]
        replacement = dict(old)
        replacement["play_id"] = int(
            conn.execute("SELECT COALESCE(MAX(play_id), 0) + 1 FROM plays").fetchone()[0]
        )
        old_ms = max(int(old["ms_played"] or 0), 0)
        replacement["ms_played"] = old_ms + max(old_ms, 60_000)
        replacement["source_fingerprint"] = new_fingerprint
        replacement["import_generation_id"] = CORRECTION_GENERATION_ID
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM plays WHERE play_id=?", (int(old["play_id"]),))
        conn.execute(
            f"INSERT INTO plays({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            tuple(replacement.get(column) for column in columns),
        )
        from backend.domains.imports.state import summarise_current_playback_dataset

        summary = summarise_current_playback_dataset(conn)
        plan = ImportPlan(
            relation=ImportRelation.RECONCILED_SNAPSHOT,
            estimated_strategy=ImportStrategy.MIXED,
            incoming_digest=summary.dataset_digest,
            previous_digest=previous_digest,
            incoming_count=existing_count,
            existing_count=existing_count,
            unchanged_count=existing_count - 1,
            added=frozenset({added}),
            removed=frozenset({removed}),
            incoming_first_ts=_parse_timestamp(summary.first_ts),
            incoming_latest_ts=_parse_timestamp(summary.latest_ts),
            existing_first_ts=_parse_timestamp(range_row[0]),
            existing_latest_ts=_parse_timestamp(range_row[1]),
            requires_confirmation=True,
        )
        removed_impact = {
            key: old.get(key)
            for key in (
                "play_id",
                "ts",
                "ts_date",
                "ts_year",
                "ts_month",
                "track_id",
                "source_album_id",
                "ms_played",
                "spotify_track_id_at_play",
                "spotify_album_id_at_play",
            )
        }
        change_set = build_playback_change_set(
            conn,
            generation_id=CORRECTION_GENERATION_ID,
            strategy="reconcile",
            plan=plan,
            removed_rows=[removed_impact],
        )
        publish_playback_import_state(
            conn,
            generation_id=CORRECTION_GENERATION_ID,
            account_identity_hash="phase-e-private-copy",
            relation="reconciled_snapshot",
            strategy="reconcile",
        )
        conn.commit()
        return change_set, summary.dataset_digest
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _table_digest(path: Path, table: str, *, excluded_weeks: set[str] | None = None) -> str:
    conn = sqlite3.connect(path)
    digest = hashlib.sha256()
    try:
        query = f'SELECT * FROM "{table}"'
        params: tuple[Any, ...] = ()
        if excluded_weeks:
            placeholders = ",".join("?" for _ in excluded_weeks)
            query += f" WHERE billboard_week NOT IN ({placeholders})"
            params = tuple(sorted(excluded_weeks))
        query += " ORDER BY 1, 2, 3"
        for row in conn.execute(query, params):
            digest.update(json.dumps(row, ensure_ascii=True, default=str).encode("utf-8"))
            digest.update(b"\n")
    finally:
        conn.close()
    return digest.hexdigest()


def _compare_tables(left: Path, right: Path) -> dict[str, int]:
    conn = sqlite3.connect(left)
    try:
        conn.execute("ATTACH DATABASE ? AS reference", (str(right),))
        differences: dict[str, int] = {}
        for table in TABLES:
            left_only = int(
                conn.execute(
                    f'SELECT COUNT(*) FROM (SELECT * FROM main."{table}" '
                    f'EXCEPT SELECT * FROM reference."{table}")'
                ).fetchone()[0]
            )
            right_only = int(
                conn.execute(
                    f'SELECT COUNT(*) FROM (SELECT * FROM reference."{table}" '
                    f'EXCEPT SELECT * FROM main."{table}")'
                ).fetchone()[0]
            )
            differences[table] = left_only + right_only
        return differences
    finally:
        conn.close()


def _historical_acceptance(baseline: Path, workdir: Path) -> dict[str, Any]:
    partition = workdir / "historical-partition.db"
    full = workdir / "historical-full.db"
    _online_backup(baseline, partition)
    _online_backup(baseline, full)
    try:
        change_set, current_digest = _apply_historical_correction(partition)
        if not change_set.billboard_scope_exact or not change_set.billboard_weeks:
            open_weeks = {
                value
                for value in (change_set.previous_open_week, change_set.current_open_week)
                if value
            }
            raise AcceptanceError(
                "historical correction did not prove a bounded week scope: "
                f"exact={change_set.billboard_scope_exact}, "
                f"week_count={len(change_set.billboard_weeks)}, "
                f"open_touched={bool(change_set.billboard_weeks & open_weeks)}"
            )
        unaffected_before = {
            table: _table_digest(
                baseline,
                table,
                excluded_weeks=set(change_set.billboard_weeks),
            )
            for table in TABLES
        }
        _set_database(partition)
        conn = db_mod.get_db(readonly=True)
        try:
            settings = _settings(conn)
        finally:
            conn.close()
        started = time.perf_counter()
        partition_report = db_mod.build_aggregations_for_replaced_weeks(
            set(change_set.billboard_weeks),
            replacement_scope_exact=change_set.billboard_scope_exact,
            expected_generation_id=change_set.generation_id,
            expected_dataset_digest=current_digest,
            previous_dataset_digest=change_set.previous_dataset_digest,
            min_ms=int(settings.get("min_ms", 30_000)),
            music_only=bool(settings.get("music_only", True)),
            week_start_dow=int(settings.get("bb_week_start_dow", 4)),
            week_start_hour=int(settings.get("bb_week_start_hour", 0)),
            dynamic_threshold=True,
            max_merge_gap_minutes=int(settings.get("max_merge_gap_minutes", 5)),
        )
        partition_seconds = time.perf_counter() - started
        _apply_historical_correction(full)
        _set_database(full)
        started = time.perf_counter()
        full_report = db_mod.build_aggregations(
            min_ms=int(settings.get("min_ms", 30_000)),
            music_only=bool(settings.get("music_only", True)),
            week_start_dow=int(settings.get("bb_week_start_dow", 4)),
            week_start_hour=int(settings.get("bb_week_start_hour", 0)),
            dynamic_threshold=True,
            max_merge_gap_minutes=int(settings.get("max_merge_gap_minutes", 5)),
            expected_generation_id=CORRECTION_GENERATION_ID,
        )
        full_seconds = time.perf_counter() - started
        differences = _compare_tables(partition, full)
        unaffected_after = {
            table: _table_digest(
                partition,
                table,
                excluded_weeks=set(change_set.billboard_weeks),
            )
            for table in TABLES
        }
        passed = (
            partition_report.get("build_strategy") == "historical_partition"
            and full_report.get("build_strategy") == "full"
            and all(value == 0 for value in differences.values())
            and unaffected_before == unaffected_after
        )
        return {
            "passed": passed,
            "affected_week_count": len(change_set.billboard_weeks),
            "partition_seconds": round(partition_seconds, 3),
            "full_seconds": round(full_seconds, 3),
            "table_difference_counts": differences,
            "unaffected_weeks_unchanged": unaffected_before == unaffected_after,
        }
    finally:
        for path in (partition, full):
            path.unlink(missing_ok=True)


def _fact_profile(path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(path)
    try:
        lineage = conn.execute(
            """SELECT active_generation_id, dataset_digest, record_count, last_strategy
               FROM playback_import_state WHERE state_id=1"""
        ).fetchone()
        digest = hashlib.sha256()
        for row in conn.execute(
            """SELECT content_type, source_fingerprint, import_generation_id,
                      ts, track_id, source_album_id, ms_played
               FROM plays ORDER BY content_type, source_fingerprint"""
        ):
            digest.update(json.dumps(row, default=str).encode("utf-8"))
        return {
            "quick_check": str(conn.execute("PRAGMA quick_check").fetchone()[0]),
            "lineage": tuple(lineage) if lineage is not None else None,
            "fact_digest": digest.hexdigest(),
            "track_album_count": int(
                conn.execute("SELECT COUNT(*) FROM track_albums").fetchone()[0]
            ),
            "aggregate_counts": {
                table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
                for table in TABLES
            },
        }
    finally:
        conn.close()


def _kill_worker(database: Path, input_dir: Path) -> None:
    from backend.core import db as worker_db
    from backend.core.import_data import import_data

    worker_db.DB_PATH = str(database)

    def terminate_before_commit(_conn, _result) -> None:
        os.kill(os.getpid(), signal.SIGKILL)

    import_data(
        str(input_dir),
        build_preaggregations=False,
        mode="replace",
        generation_id="phase-e-killed-replace",
        before_final_commit=terminate_before_commit,
    )
    raise AcceptanceError("kill worker unexpectedly returned")


def _hard_kill_acceptance(baseline: Path, workdir: Path) -> dict[str, Any]:
    target = workdir / "hard-kill.db"
    input_dir = workdir / "hard-kill-input"
    input_dir.mkdir()
    _online_backup(baseline, target)
    record = {
        "ts": "2026-01-01T00:00:00Z",
        "platform": "phase-e",
        "ms_played": 45_000,
        "conn_country": "CN",
        "master_metadata_track_name": "Synthetic acceptance record",
        "master_metadata_album_artist_name": "Synthetic acceptance artist",
        "master_metadata_album_album_name": "Synthetic acceptance album",
        "spotify_track_uri": "spotify:track:phase-e-synthetic",
    }
    (input_dir / "Streaming_History_Audio_acceptance.json").write_text(
        json.dumps([record]), encoding="utf-8"
    )
    before = _fact_profile(target)
    process = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--_kill-worker-db",
            str(target),
            "--_kill-worker-input",
            str(input_dir),
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    after = _fact_profile(target)
    passed = process.returncode == -signal.SIGKILL and before == after
    target.unlink(missing_ok=True)
    shutil.rmtree(input_dir)
    return {
        "passed": passed,
        "worker_returncode": process.returncode,
        "quick_check": after["quick_check"],
        "facts_unchanged": before == after,
    }


class _AcceptanceQueue:
    def __init__(self) -> None:
        self.jobs: dict[tuple[str, str, str], Any] = {}

    def enqueue_if_not_pending(self, job):
        key = (job.job_type, job.entity_type, job.entity_id)
        if key in self.jobs:
            return None
        self.jobs[key] = job
        return job.job_id


def _startup_recovery_acceptance(baseline: Path, workdir: Path) -> dict[str, Any]:
    from backend.domains.imports.change_set import PlaybackChangeSet
    from backend.domains.imports.incremental import (
        ImportPlan,
        ImportRelation,
        ImportStrategy,
    )
    from backend.domains.imports.state import record_playback_import_run
    from backend.services.import_maintenance_recovery_service import (
        enqueue_pending_import_maintenance,
    )

    target = workdir / "startup-recovery.db"
    _online_backup(baseline, target)
    _set_database(target)
    conn = db_mod.get_db(readonly=False)
    try:
        generation_id, digest, record_count = _active_lineage(conn)
        generation_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM plays WHERE import_generation_id=?",
                (generation_id,),
            ).fetchone()[0]
        )
        if generation_count <= 0:
            raise AcceptanceError("active generation has no recoverable fact rows")
        change_set = PlaybackChangeSet(
            generation_id=generation_id,
            strategy="incremental",
            previous_dataset_digest=digest,
            added_count=generation_count,
            removed_count=0,
            earliest_changed_ts=None,
            latest_changed_ts=None,
            track_ids=frozenset(),
            album_ids=frozenset(),
            source_album_ids=frozenset(),
            artist_ids=frozenset(),
            spotify_track_ids=frozenset(),
            spotify_album_ids=frozenset(),
            dates=frozenset(),
            months=frozenset(),
            years=frozenset(),
            billboard_weeks=frozenset(),
            billboard_scope_exact=False,
            previous_open_week=None,
            current_open_week=None,
            semantic_revisions={"acceptance": 1},
        )
        plan = ImportPlan(
            relation=ImportRelation.IDENTICAL,
            estimated_strategy=ImportStrategy.NOOP,
            incoming_digest=digest,
            previous_digest=digest,
            incoming_count=record_count,
            existing_count=record_count,
            unchanged_count=record_count,
            added=frozenset(),
            removed=frozenset(),
            incoming_first_ts=None,
            incoming_latest_ts=None,
            existing_first_ts=None,
            existing_latest_ts=None,
            requires_confirmation=False,
        )
        record_playback_import_run(
            conn,
            run_id="phase-e-pending-recovery",
            requested_mode="auto",
            status="maintenance_pending",
            plan=plan,
            change_set=change_set,
        )
        conn.commit()
    finally:
        conn.close()
    queue = _AcceptanceQueue()
    enqueued = enqueue_pending_import_maintenance(queue)  # type: ignore[arg-type]
    conn = sqlite3.connect(target)
    conn.execute("UPDATE playback_import_state SET dataset_digest='drifted'")
    conn.commit()
    conn.close()
    blocked = enqueue_pending_import_maintenance(_AcceptanceQueue())  # type: ignore[arg-type]
    conn = sqlite3.connect(target)
    status = conn.execute(
        """SELECT status, error_code FROM playback_import_runs
           WHERE run_id='phase-e-pending-recovery'"""
    ).fetchone()
    conn.close()
    target.unlink(missing_ok=True)
    passed = (
        enqueued["enqueued"] == 1
        and blocked["blocked"] == 1
        and status == ("recovery_blocked", "recovery_active_digest_drift")
    )
    return {
        "passed": passed,
        "valid_pending_enqueued": enqueued["enqueued"],
        "drifted_pending_blocked": blocked["blocked"],
        "blocked_error_code": status[1] if status else None,
    }


def run_acceptance(source: Path, workdir: Path) -> dict[str, Any]:
    baseline = workdir / "baseline.db"
    source_stat = source.stat()
    _online_backup(source, baseline)
    baseline_build = _build_full_baseline(baseline)
    historical = _historical_acceptance(baseline, workdir)
    hard_kill = _hard_kill_acceptance(baseline, workdir)
    recovery = _startup_recovery_acceptance(baseline, workdir)
    source_after = source.stat()
    source_unchanged = (
        source_stat.st_size,
        source_stat.st_mtime_ns,
        source_stat.st_ino,
    ) == (source_after.st_size, source_after.st_mtime_ns, source_after.st_ino)
    passed = historical["passed"] and hard_kill["passed"] and recovery["passed"]
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "passed" if passed and source_unchanged else "failed",
        "source": {
            "read_only": True,
            "unchanged": source_unchanged,
            "database_path_emitted": False,
        },
        "baseline_build": baseline_build,
        "historical_correction": historical,
        "hard_kill_before_fact_publish": hard_kill,
        "startup_pending_recovery": recovery,
        "privacy": {
            "entity_content_emitted": False,
            "fingerprints_emitted": False,
            "listening_rows_emitted": False,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args._kill_worker_db:
        _kill_worker(args._kill_worker_db, args._kill_worker_input)
        return 1
    source = args.source_db.expanduser().resolve(strict=True)
    with managed_workdir(source, args.workdir, keep=args.keep_workdir) as workdir:
        report = run_acceptance(source, workdir)
        encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
        if args.json_output:
            args.json_output.write_text(encoded + "\n", encoding="utf-8")
        if args.json:
            print(encoded)
        else:
            historical = report["historical_correction"]
            print(
                f"Phase E {report['status']}: historical={historical['partition_seconds']}s "
                f"vs full={historical['full_seconds']}s; "
                f"hard_kill={report['hard_kill_before_fact_publish']['passed']}; "
                f"recovery={report['startup_pending_recovery']['passed']}"
            )
        return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
