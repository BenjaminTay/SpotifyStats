#!/usr/bin/env python3
"""Run an end-to-end incremental-import matrix on disposable synthetic data.

The script exercises the production ``import_data`` parser/writer rather than
inserting playback rows directly.  Every write is confined to a newly-created
directory under ``/tmp`` (or an explicitly supplied directory outside the
repository).  The configured source database is opened read-only only to prove
that the acceptance run did not mutate it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.core import db as db_mod  # noqa: E402

REPORT_SCHEMA_VERSION = "incremental_import_end_to_end_acceptance_v1"
ACCOUNT_USERNAME = "incremental-acceptance-fixture"
BASE_GENERATION = "acceptance-baseline"
APPEND_GENERATION = "acceptance-append"
SECOND_APPEND_GENERATION = "acceptance-second-append"
RECONCILE_GENERATION = "acceptance-reconcile"
REPLACE_GENERATION = "acceptance-replace"
ImportRequestMode = Literal["auto", "append", "replace"]
ImportExecutionMode = Literal["replace", "append", "reconcile"]
ImportStrategy = Literal["incremental", "reconcile", "full"]

AGGREGATE_TABLES = (
    "agg_weekly_tracks",
    "agg_weekly_albums",
    "agg_weekly_track_sources",
    "agg_weekly_artists",
)
AGGREGATE_PROJECTIONS = {
    "agg_weekly_tracks": """SELECT a.billboard_week, t.spotify_track_id,
           t.track_name, ar.artist_name, a.play_count, a.total_ms
        FROM agg_weekly_tracks a
        JOIN tracks t ON t.track_id=a.track_id
        LEFT JOIN artists ar ON ar.artist_id=t.artist_id
        ORDER BY a.billboard_week, t.spotify_track_id, t.track_name, ar.artist_name""",
    "agg_weekly_albums": """SELECT a.billboard_week,
           al.album_name, ar.artist_name, a.play_count, a.total_ms
        FROM agg_weekly_albums a
        JOIN albums al ON al.album_id=a.album_id
        LEFT JOIN artists ar ON ar.artist_id=al.artist_id
        ORDER BY a.billboard_week, al.album_name, ar.artist_name""",
    "agg_weekly_track_sources": """SELECT a.billboard_week, a.play_date,
           t.spotify_track_id, t.track_name, source.album_name,
           source_artist.artist_name, a.play_count, a.total_ms
        FROM agg_weekly_track_sources a
        JOIN tracks t ON t.track_id=a.track_id
        LEFT JOIN albums source ON source.album_id=NULLIF(a.source_album_id, 0)
        LEFT JOIN artists source_artist ON source_artist.artist_id=source.artist_id
        ORDER BY a.billboard_week, a.play_date, t.spotify_track_id, t.track_name,
                 source.album_name, source_artist.artist_name""",
    "agg_weekly_artists": """SELECT a.billboard_week,
           ar.artist_name, a.play_count, a.total_ms
        FROM agg_weekly_artists a
        JOIN artists ar ON ar.artist_id=a.artist_id
        ORDER BY a.billboard_week, ar.artist_name""",
}
FACT_PROJECTION = """SELECT p.ts, p.ms_played, p.content_type,
       p.source_fingerprint, p.spotify_track_id_at_play,
       p.reason_start, p.reason_end, p.shuffle, p.skipped, p.offline,
       p.incognito_mode, t.track_name, al.album_name, ar.artist_name
FROM plays p
LEFT JOIN tracks t ON t.track_id=p.track_id
LEFT JOIN albums al ON al.album_id=p.source_album_id
LEFT JOIN artists ar ON ar.artist_id=t.artist_id
ORDER BY p.ts, p.content_type, p.source_fingerprint"""
CREDIT_PROJECTION = """SELECT t.track_name, primary_artist.artist_name,
       credited.artist_name, ta.role
FROM track_artists ta
JOIN tracks t ON t.track_id=ta.track_id
JOIN artists credited ON credited.artist_id=ta.artist_id
JOIN artists primary_artist ON primary_artist.artist_id=t.artist_id
WHERE EXISTS (SELECT 1 FROM plays p WHERE p.track_id=ta.track_id)
ORDER BY t.track_name, primary_artist.artist_name, credited.artist_name, ta.role"""
ALBUM_PROJECT_PROJECTIONS = {
    "projects": """SELECT ap.canonical_name, ar.artist_name, al.album_name,
           ap.release_date, ap.scope, ap.project_type, ap.include_in_charts,
           ap.is_manual
    FROM album_projects ap
    LEFT JOIN artists ar ON ar.artist_id=ap.artist_id
    LEFT JOIN albums al ON al.album_id=ap.primary_album_id
    ORDER BY ap.canonical_name, ar.artist_name, al.album_name""",
    "albums": """SELECT ap.canonical_name, ar.artist_name, al.album_name,
           apa.role, apa.source_bucket, apa.inferred
    FROM album_project_albums apa
    JOIN album_projects ap ON ap.project_id=apa.project_id
    LEFT JOIN artists ar ON ar.artist_id=ap.artist_id
    JOIN albums al ON al.album_id=apa.album_id
    ORDER BY ap.canonical_name, ar.artist_name, al.album_name""",
    "tracks": """SELECT ap.canonical_name, ar.artist_name, t.track_name,
           apt.membership_role, apt.min_merge_level, apt.is_exclusive,
           apt.inferred
    FROM album_project_tracks apt
    JOIN album_projects ap ON ap.project_id=apt.project_id
    LEFT JOIN artists ar ON ar.artist_id=ap.artist_id
    JOIN tracks t ON t.track_id=apt.track_id
    ORDER BY ap.canonical_name, ar.artist_name, t.track_name,
             apt.min_merge_level""",
}
TRACK_GROUP_PROJECTIONS = {
    "groups": """SELECT tg.scope, tg.is_manual, tg.canonical_name,
           primary_track.spotify_track_id, primary_track.track_name,
           primary_artist.artist_name, tg.automatic_spotify_track_id,
           automatic_artist.artist_name
        FROM track_groups tg
        LEFT JOIN tracks primary_track ON primary_track.track_id=tg.primary_track_id
        LEFT JOIN artists primary_artist ON primary_artist.artist_id=primary_track.artist_id
        LEFT JOIN artists automatic_artist ON automatic_artist.artist_id=tg.automatic_artist_id
        ORDER BY tg.scope, tg.is_manual, tg.canonical_name,
                 primary_track.spotify_track_id, primary_track.track_name""",
    "members": """SELECT tg.scope, tg.is_manual, tg.canonical_name,
           tg.automatic_spotify_track_id, owner_artist.artist_name,
           member.spotify_track_id, member.track_name, member_artist.artist_name
        FROM track_group_members tgm
        JOIN track_groups tg ON tg.group_id=tgm.group_id
        LEFT JOIN artists owner_artist ON owner_artist.artist_id=tg.automatic_artist_id
        JOIN tracks member ON member.track_id=tgm.track_id
        LEFT JOIN artists member_artist ON member_artist.artist_id=member.artist_id
        ORDER BY tg.scope, tg.is_manual, tg.canonical_name,
                 tg.automatic_spotify_track_id, owner_artist.artist_name,
                 member.spotify_track_id, member.track_name, member_artist.artist_name""",
}
SEARCH_CONTEXT_COLUMNS = (
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


class AcceptanceError(RuntimeError):
    """Raised when an acceptance invariant fails closed."""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, default=Path(db_mod.DB_PATH))
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--keep-workdir", action="store_true")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--real-source-baseline",
        action="store_true",
        help="Also import the configured real raw export into a disposable empty database",
    )
    parser.add_argument(
        "--real-streaming-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "streaming",
    )
    parser.add_argument(
        "--real-account-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "account",
    )
    return parser.parse_args(argv)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_workdir(workdir: Path, source_db: Path | None = None) -> Path:
    target = workdir.expanduser().resolve(strict=False)
    if target == Path(target.anchor) or target == Path.home().resolve():
        raise AcceptanceError("work directory target is too broad")
    if target == PROJECT_ROOT or _is_relative_to(target, PROJECT_ROOT):
        raise AcceptanceError("work directory must be outside the repository")
    if source_db is not None:
        source = source_db.expanduser().resolve(strict=False)
        if target == source or _is_relative_to(target, source.parent):
            raise AcceptanceError("work directory must be outside the source database directory")
    if target.exists():
        raise AcceptanceError("work directory must not already exist")
    return target


@contextmanager
def managed_workdir(
    requested: Path | None,
    *,
    source_db: Path | None,
    keep: bool,
) -> Iterator[Path]:
    if requested is None:
        target = Path(tempfile.mkdtemp(prefix="spotifystats-import-e2e-", dir="/tmp"))
        shutil.rmtree(target)
    else:
        target = requested
    target = validate_workdir(target, source_db)
    target.mkdir(parents=True, mode=0o700)
    try:
        yield target
    finally:
        if not keep and target.exists():
            shutil.rmtree(target)


def _readonly_uri(path: Path) -> str:
    return f"file:{quote(str(path.resolve()), safe='/')}?mode=ro"


def _source_guard(path: Path) -> dict[str, Any]:
    source = path.expanduser().resolve(strict=True)
    before = source.stat()
    conn = sqlite3.connect(_readonly_uri(source), uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        quick_check = str(conn.execute("PRAGMA quick_check").fetchone()[0])
        play_count = int(conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0])
        migration = conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
        ).fetchone()
    finally:
        conn.close()
    return {
        "path": source,
        "stat": before,
        "profile": {
            "quick_check": quick_check,
            "play_count": play_count,
            "migration_max": int(migration[0] or 0) if migration else 0,
            "database_bytes": before.st_size,
        },
    }


def _verify_source_guard(guard: dict[str, Any]) -> bool:
    before = guard["stat"]
    after = guard["path"].stat()
    return bool(
        before.st_size == after.st_size
        and before.st_mtime_ns == after.st_mtime_ns
        and before.st_ino == after.st_ino
    )


def _record(track_index: int, timestamp: datetime, *, ms_played: int) -> dict[str, Any]:
    track_name = (
        "Acceptance Track 3 (feat. Acceptance Guest)"
        if track_index == 2
        else f"Acceptance Track {track_index + 1}"
    )
    return {
        "ts": timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "conn_country": "CN",
        "platform": "ios",
        "ms_played": ms_played,
        "master_metadata_track_name": track_name,
        "master_metadata_album_artist_name": "Acceptance Artist",
        "master_metadata_album_album_name": "Acceptance Album",
        "spotify_track_uri": f"spotify:track:acceptance-track-{track_index + 1}",
        "reason_start": "trackdone",
        "reason_end": "trackdone",
        "shuffle": False,
        "skipped": False,
        "offline": False,
        "incognito_mode": False,
    }


def _correctable_record(timestamp: datetime, *, album_name: str, ms_played: int) -> dict[str, Any]:
    return {
        **_record(3, timestamp, ms_played=ms_played),
        "master_metadata_track_name": "Acceptance Corrected Track",
        "master_metadata_album_album_name": album_name,
        "spotify_track_uri": "spotify:track:acceptance-track-corrected",
    }


def synthetic_datasets() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Return baseline, cross-week append, same-week append, and reconcile snapshots."""
    first_week = datetime(2025, 1, 3, 12, 0, tzinfo=timezone.utc)
    baseline: list[dict[str, Any]] = []
    for week_index in range(12):
        week = first_week + timedelta(days=7 * week_index)
        for track_index in range(3):
            baseline.append(
                _record(
                    track_index,
                    week + timedelta(minutes=track_index),
                    ms_played=180_000 + track_index * 1_000,
                )
            )
    baseline.append(
        _correctable_record(
            first_week + timedelta(hours=2),
            album_name="Acceptance Legacy Album",
            ms_played=188_000,
        )
    )
    appended = [dict(record) for record in baseline]
    append_week = first_week + timedelta(days=7 * 12)
    for track_index in range(3):
        appended.append(
            _record(
                track_index,
                append_week + timedelta(minutes=track_index),
                ms_played=185_000 + track_index * 1_000,
            )
        )
    same_week_appended = [dict(record) for record in appended]
    same_week_appended.append(_record(0, append_week + timedelta(hours=1), ms_played=191_000))
    reconciled = [dict(record) for record in same_week_appended]
    correction_index = next(
        index
        for index, record in enumerate(reconciled)
        if record.get("spotify_track_uri") == "spotify:track:acceptance-track-corrected"
    )
    reconciled[correction_index] = _correctable_record(
        first_week + timedelta(hours=2),
        album_name="Acceptance Corrected Album",
        ms_played=235_000,
    )
    reconciled[correction_index]["reason_end"] = "unexpected-exit-while-paused"
    return baseline, appended, same_week_appended, reconciled


def _write_bundle(directory: Path, records: list[dict[str, Any]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "Streaming_History_Audio_000.json").write_text(
        json.dumps(records, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def _write_account(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "UserAttributes.json").write_text(
        json.dumps({"username": ACCOUNT_USERNAME}, separators=(",", ":")),
        encoding="utf-8",
    )


def _online_backup(source: Path, target: Path) -> None:
    if target.exists():
        raise AcceptanceError("backup target already exists")
    source_conn = sqlite3.connect(_readonly_uri(source), uri=True)
    target_conn = sqlite3.connect(target)
    try:
        source_conn.execute("PRAGMA query_only=ON")
        source_conn.backup(target_conn)
        if str(target_conn.execute("PRAGMA quick_check").fetchone()[0]) != "ok":
            raise AcceptanceError("disposable backup failed quick_check")
    finally:
        target_conn.close()
        source_conn.close()


def _set_database(path: Path) -> None:
    from backend.core.cache_manager import invalidate_all

    db_mod.DB_PATH = str(path.resolve())
    invalidate_all()


def _timed(call: Callable[[], Any]) -> tuple[Any, float]:
    started = time.perf_counter()
    result = call()
    return result, round((time.perf_counter() - started) * 1000, 3)


def _seed_synthetic_metadata(path: Path) -> None:
    _set_database(path)
    conn = db_mod.get_db(readonly=False)
    try:
        conn.execute(
            """INSERT OR REPLACE INTO spotify_album_meta(
                   spotify_album_id, album_name, album_type, release_date,
                   album_artists, total_tracks
               ) VALUES ('acceptance-album', 'Acceptance Album', 'album',
                         '2024-12-20', 'Acceptance Artist', 3)"""
        )
        rows = conn.execute(
            """SELECT spotify_track_id, track_name FROM tracks
               WHERE spotify_track_id LIKE 'acceptance-track-%'
               ORDER BY spotify_track_id"""
        ).fetchall()
        conn.executemany(
            """INSERT OR REPLACE INTO spotify_track_meta(
                   spotify_track_id, track_name, duration_ms, spotify_album_id
               ) VALUES (?, ?, 210000, 'acceptance-album')""",
            [(str(row[0]), str(row[1])) for row in rows],
        )
        primary = conn.execute(
            """SELECT track_id, artist_id, album_id
               FROM tracks WHERE spotify_track_id='acceptance-track-1'
               ORDER BY track_id LIMIT 1"""
        ).fetchone()
        if primary is None:
            raise AcceptanceError("synthetic primary track is missing")
        conn.execute(
            """INSERT OR IGNORE INTO tracks(
                   track_name, artist_id, album_id, spotify_track_uri, spotify_track_id
               ) VALUES (
                   'Acceptance Track 1 Alternate', ?, ?,
                   'spotify:track:acceptance-track-1', 'acceptance-track-1'
               )""",
            (int(primary[1]), int(primary[2])),
        )
        duplicate_track_id = int(
            conn.execute(
                """SELECT track_id FROM tracks
                   WHERE track_name='Acceptance Track 1 Alternate'
                     AND artist_id=? AND spotify_track_id='acceptance-track-1'""",
                (int(primary[1]),),
            ).fetchone()[0]
        )
        conn.execute(
            """INSERT OR IGNORE INTO track_artists(track_id, artist_id, role)
               VALUES (?, ?, 'primary')""",
            (duplicate_track_id, int(primary[1])),
        )
        conn.commit()
    finally:
        conn.close()


def _assess(
    path: Path,
    data_dir: Path,
    account_dir: Path,
    requested_mode: ImportRequestMode = "auto",
):
    from backend.services.import_plan_service import assess_streaming_import

    _set_database(path)
    return assess_streaming_import(
        data_dir,
        account_dir,
        requested_mode=requested_mode,
        retain_staging=True,
    )


def _execute_import(
    path: Path,
    data_dir: Path,
    assessment: Any,
    *,
    mode: ImportExecutionMode,
    generation_id: str,
    strategy: ImportStrategy,
) -> tuple[dict[str, Any], dict[str, float]]:
    from backend.api import import_ as import_api
    from backend.core.import_data import import_data
    from backend.domains.imports.change_set import (
        build_playback_change_set,
        publish_year_partition_state,
    )

    _set_database(path)
    finalizer_ms = 0.0

    def finalizer(conn: sqlite3.Connection, result: dict[str, Any]) -> None:
        nonlocal finalizer_ms
        started = time.perf_counter()
        import_api._publish_import_state(
            assessment,
            result,
            executed_strategy=strategy,
            conn=conn,
        )
        result["change_set"] = build_playback_change_set(
            conn,
            generation_id=generation_id,
            strategy=strategy,
            plan=assessment.plan,
            removed_rows=result.get("_removed_impact_rows"),
        )
        publish_year_partition_state(conn, result["change_set"])
        finalizer_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    try:
        result = import_data(
            str(data_dir),
            build_preaggregations=False,
            mode=mode,
            generation_id=generation_id,
            expected_previous_digest=(
                assessment.plan.previous_digest if mode in {"append", "reconcile"} else None
            ),
            removed_identities=(assessment.plan.removed if mode == "reconcile" else None),
            before_final_commit=finalizer,
            staging=assessment.staging,
        )
    finally:
        if assessment.staging is not None:
            assessment.staging.close()
    return result, {
        "facts_publish_ms": round((time.perf_counter() - started) * 1000, 3),
        "transactional_finalizer_ms": round(finalizer_ms, 3),
    }


def _aggregation_settings(conn: sqlite3.Connection) -> dict[str, Any]:
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


def _run_derived(path: Path, change_set: Any) -> tuple[dict[str, Any], dict[str, float]]:
    from backend.core.db import (
        build_aggregations,
        build_aggregations_for_replaced_weeks,
        build_aggregations_for_weeks,
    )
    from backend.domains.music_search.revisions import bump_music_search_revisions
    from backend.domains.playback.album_projects import rebuild_album_projects_for_impact
    from backend.services.import_maintenance_service import _auto_group_tracks_by_spotify_id
    from backend.services.music_search_maintenance_service import (
        build_shared_full_music_search_plan,
        rebuild_current_music_search_derived_data,
    )

    _set_database(path)
    conn = db_mod.get_db(readonly=False)
    try:
        group_started = time.perf_counter()
        groups_created, members_added = _auto_group_tracks_by_spotify_id(
            conn,
            track_ids=(
                change_set.track_ids
                if change_set.strategy in {"incremental", "reconcile"}
                else None
            ),
            spotify_track_ids=(
                frozenset() if change_set.strategy in {"incremental", "reconcile"} else None
            ),
        )
        track_group_ms = (time.perf_counter() - group_started) * 1000
        ap_started = time.perf_counter()
        album_project = rebuild_album_projects_for_impact(
            conn,
            local_album_ids=change_set.album_ids,
            spotify_album_ids=change_set.spotify_album_ids,
            spotify_track_ids=change_set.spotify_track_ids,
            impact_scope_exact=change_set.strategy in {"incremental", "reconcile"},
            has_deletions=bool(change_set.removed_count),
        )
        album_project_ms = (time.perf_counter() - ap_started) * 1000
        settings = _aggregation_settings(conn)

        billboard_started = time.perf_counter()
        if change_set.strategy == "incremental":
            aggregation = build_aggregations_for_weeks(
                set(change_set.billboard_weeks),
                change_generation_id=change_set.generation_id,
                previous_dataset_digest=change_set.previous_dataset_digest,
                billboard_scope_exact=change_set.billboard_scope_exact,
                expected_generation_id=change_set.generation_id,
                **settings,
            )
        elif change_set.strategy == "reconcile":
            state = conn.execute(
                """SELECT dataset_digest FROM playback_import_state
                   WHERE state_id=1 AND active_generation_id=?""",
                (change_set.generation_id,),
            ).fetchone()
            if state is None:
                raise AcceptanceError("reconcile active lineage is missing")
            aggregation = build_aggregations_for_replaced_weeks(
                set(change_set.billboard_weeks),
                replacement_scope_exact=change_set.billboard_scope_exact,
                expected_generation_id=change_set.generation_id,
                expected_dataset_digest=str(state[0]),
                previous_dataset_digest=change_set.previous_dataset_digest,
                **settings,
            )
        else:
            aggregation = build_aggregations(
                expected_generation_id=change_set.generation_id,
                **settings,
            )
        billboard_ms = (time.perf_counter() - billboard_started) * 1000

        bump_music_search_revisions(conn, "playback", "billboard", "candidate")
        conn.commit()
        shared_plan = build_shared_full_music_search_plan(conn, change_set=change_set)
        search_started = time.perf_counter()
        search = rebuild_current_music_search_derived_data(
            conn,
            rebuild_documents=True,
            shared_full_snapshot_plan=shared_plan,
        )
        search_ms = (time.perf_counter() - search_started) * 1000
        if search["snapshot_set"]["ready_count"] != 4 or search["snapshot_set"]["failed_count"]:
            raise AcceptanceError("music-search did not publish exactly four ready snapshots")
        return (
            {
                "track_group": {
                    "groups_created": groups_created,
                    "members_added": members_added,
                },
                "album_project": {
                    "strategy": album_project.strategy,
                    "fallback_reason": album_project.fallback_reason,
                    "affected_albums": album_project.affected_album_count,
                    "affected_projects": album_project.affected_project_count,
                },
                "aggregation": {
                    "strategy": aggregation.get("build_strategy", "full"),
                    "fallback_reason": aggregation.get("fallback_reason"),
                    "affected_weeks": aggregation.get("affected_weeks", 0),
                },
                "search": {
                    "strategy": search["snapshot_set"].get("strategy", "full"),
                    "ready_count": search["snapshot_set"]["ready_count"],
                    "failed_count": search["snapshot_set"]["failed_count"],
                    "candidate_action": search["candidate_index"]["action"],
                    "variants": [
                        {
                            "snapshot_key": item["snapshot_key"],
                            "merge_level": int(item["merge_level"]),
                            "dynamic_threshold": bool(item["dynamic_threshold"]),
                            "entity_count": int(item["entity_count"]),
                        }
                        for item in search["snapshot_set"]["variants"]
                    ],
                },
            },
            {
                "track_group_ms": round(track_group_ms, 3),
                "album_project_ms": round(album_project_ms, 3),
                "billboard_ms": round(billboard_ms, 3),
                "search_ms": round(search_ms, 3),
            },
        )
    finally:
        conn.close()


def _rows(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[list[Any]]:
    return [list(row) for row in conn.execute(query, params).fetchall()]


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _projection(conn: sqlite3.Connection, query: str) -> dict[str, Any]:
    rows = _rows(conn, query)
    return {"row_count": len(rows), "digest": _digest(rows), "rows": rows}


def _candidate_projection(conn: sqlite3.Connection) -> dict[str, Any]:
    state = conn.execute(
        "SELECT active_generation_id FROM music_search_index_state WHERE state_id=1"
    ).fetchone()
    if state is None or not state[0]:
        raise AcceptanceError("candidate index has no active generation")
    query = """SELECT d.kind, d.merge_level, d.label, d.normalized_label,
                      d.secondary, d.normalized_secondary, d.alias_text,
                      d.normalized_alias, d.search_text, d.popularity_tiebreaker,
                      d.album_name, d.artist_name,
                      COALESCE(t.spotify_track_id, ''),
                      COALESCE(al.album_name, ''),
                      COALESCE(ar.artist_name, ''),
                      COALESCE(ap.canonical_name, '')
               FROM music_search_documents d
               LEFT JOIN tracks t ON t.track_id=d.track_id
               LEFT JOIN albums al ON al.album_id=d.album_id
               LEFT JOIN artists ar ON ar.artist_id=d.artist_id
               LEFT JOIN album_projects ap ON ap.project_id=d.album_project_id
               WHERE d.generation_id=?
               ORDER BY d.kind, d.merge_level, d.normalized_label,
                        d.normalized_secondary, d.label, d.secondary,
                        COALESCE(t.spotify_track_id, ''),
                        COALESCE(al.album_name, ''),
                        COALESCE(ar.artist_name, ''),
                        COALESCE(ap.canonical_name, '')"""
    rows = _rows(conn, query, (str(state[0]),))
    return {"row_count": len(rows), "digest": _digest(rows), "rows": rows}


def _search_projection(conn: sqlite3.Connection, variants: list[dict[str, Any]]) -> dict[str, Any]:
    payload: dict[str, list[list[Any]]] = {}
    state = conn.execute(
        "SELECT active_generation_id FROM music_search_index_state WHERE state_id=1"
    ).fetchone()
    if state is None or not state[0]:
        raise AcceptanceError("candidate index has no active generation")
    metric_columns = ", ".join(f"ctx.{column}" for column in SEARCH_CONTEXT_COLUMNS[1:])
    for variant in variants:
        key = f"L{variant['merge_level']}:dynamic={int(variant['dynamic_threshold'])}"
        payload[key] = _rows(
            conn,
            f"""SELECT d.kind, d.merge_level, d.label, d.secondary,
                       d.album_name, d.artist_name,
                       COALESCE(t.spotify_track_id, ''),
                       COALESCE(al.album_name, ''),
                       COALESCE(ar.artist_name, ''),
                       COALESCE(ap.canonical_name, ''),
                       {metric_columns}
                FROM music_search_entity_context ctx
                JOIN music_search_documents d
                  ON d.generation_id=?
                 AND d.entity_key=ctx.entity_key
                 AND (
                     (d.kind='track' AND d.merge_level=?)
                     OR (d.kind!='track' AND d.merge_level=0)
                 )
                LEFT JOIN tracks t ON t.track_id=d.track_id
                LEFT JOIN albums al ON al.album_id=d.album_id
                LEFT JOIN artists ar ON ar.artist_id=d.artist_id
                LEFT JOIN album_projects ap ON ap.project_id=d.album_project_id
                WHERE ctx.snapshot_key=?
                ORDER BY d.kind, d.merge_level, d.normalized_label,
                         d.normalized_secondary, d.label, d.secondary,
                         COALESCE(t.spotify_track_id, ''),
                         COALESCE(al.album_name, ''),
                         COALESCE(ar.artist_name, ''),
                         COALESCE(ap.canonical_name, '')""",
            (
                str(state[0]),
                int(variant["merge_level"]),
                str(variant["snapshot_key"]),
            ),
        )
    return {
        "variant_count": len(payload),
        "row_count": sum(len(rows) for rows in payload.values()),
        "digest": _digest(payload),
        "rows": payload,
    }


def _year_projection(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = _rows(
        conn,
        """SELECT report_year, direct_digest, record_count, first_ts, latest_ts
           FROM playback_year_partition_state ORDER BY report_year""",
    )
    audit_rows = _rows(
        conn,
        """SELECT report_year, prefix_digest, impact_revision,
                  source_generation_id
           FROM playback_year_partition_state ORDER BY report_year""",
    )
    return {
        "fact_row_count": len(rows),
        "fact_digest": _digest(rows),
        "fact_rows": rows,
        "audit_digest": _digest(audit_rows),
        "audit_rows": audit_rows,
    }


def _yearly_invalidation_state(path: Path, *, year: int = 2025) -> dict[str, Any]:
    """Read the factual partition and cache invalidation state without building an artifact."""

    from backend.services.yearly_review_service import (
        _prepare_artifact,
        build_default_yearly_review_context,
    )

    _set_database(path)
    conn = db_mod.get_db(readonly=True)
    try:
        row = conn.execute(
            """SELECT direct_digest, prefix_digest, impact_revision,
                      source_generation_id
               FROM playback_year_partition_state WHERE report_year=?""",
            (year,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise AcceptanceError(f"yearly partition state is missing for {year}")
    prepared = _prepare_artifact(year, build_default_yearly_review_context())
    return {
        "year": year,
        "direct_digest": str(row[0]),
        "prefix_digest": str(row[1]),
        "impact_revision": int(row[2]),
        "source_generation_id": str(row[3]),
        "cache_key": prepared.cache_key,
    }


def _accepted_change_invalidated(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return bool(
        before["direct_digest"] != after["direct_digest"]
        and before["impact_revision"] < after["impact_revision"]
        and before["cache_key"] != after["cache_key"]
    )


def _semantic_snapshot(path: Path, derived: dict[str, Any]) -> dict[str, Any]:
    from backend.core.cache_manager import invalidate_all
    from backend.domains.billboard.chart_compute import compute_billboard_data
    from backend.domains.billboard.chart_year_end_api import compute_year_end_staged
    from backend.domains.home.overview import build_home_overview
    from backend.services.yearly_review_service import (
        _prepare_artifact,
        build_default_yearly_review_context,
    )

    _set_database(path)
    conn = db_mod.get_db(readonly=False)
    try:
        facts = _projection(conn, FACT_PROJECTION)
        credits = _projection(conn, CREDIT_PROJECTION)
        active_track_albums = _projection(
            conn,
            """SELECT t.spotify_track_id, t.track_name, al.album_name
               FROM track_albums ta
               JOIN tracks t ON t.track_id=ta.track_id
               JOIN albums al ON al.album_id=ta.album_id
               ORDER BY t.spotify_track_id, t.track_name, al.album_name""",
        )
        album_projects = {
            name: _projection(conn, query) for name, query in ALBUM_PROJECT_PROJECTIONS.items()
        }
        track_groups = {
            name: _projection(conn, query) for name, query in TRACK_GROUP_PROJECTIONS.items()
        }
        aggregates = {
            table: _projection(conn, AGGREGATE_PROJECTIONS[table]) for table in AGGREGATE_TABLES
        }
        candidates = _candidate_projection(conn)
        search = _search_projection(conn, derived["search"]["variants"])
        year_partition = _year_projection(conn)
        context = build_default_yearly_review_context()
        invalidate_all()
        billboard, billboard_ms = _timed(lambda: compute_billboard_data(dynamic_threshold=True))
        getattr(compute_year_end_staged, "cache_clear")()
        year_end, year_end_ms = _timed(
            lambda: compute_year_end_staged(year=2025, dynamic_threshold=True)
        )
        home, home_ms = _timed(lambda: build_home_overview(conn, context))
        prepared = _prepare_artifact(2025, context)
        latest_week = conn.execute("SELECT MAX(billboard_week) FROM agg_weekly_tracks").fetchone()[
            0
        ]
        return {
            "facts": facts,
            "credits": credits,
            "active_track_albums": active_track_albums,
            "album_projects": album_projects,
            "track_groups": track_groups,
            "aggregates": aggregates,
            "candidates": candidates,
            "search": search,
            "year_partition": year_partition,
            "billboard": {
                "digest": _digest(billboard),
                "weeks": billboard["meta"]["all_weeks_asc"],
                "power_digest": _digest(
                    {
                        "tracks": billboard["power_scores"],
                        "albums": billboard["album_power_scores"],
                        "artists": billboard["artist_power_scores"],
                    }
                ),
                "records_digest": _digest(billboard["records"]),
                "latest_aggregate_week": str(latest_week) if latest_week else None,
            },
            "year_end": {"digest": _digest(year_end), "payload": year_end},
            "yearly_artifact": {
                "cache_key": prepared.cache_key,
                "db_revision": prepared.db_revision,
            },
            "home": {
                "state": home["state"],
                "archive_digest": _digest(home["archive"]),
                "source_latest_date": home["coverage"]["source_latest_date"],
            },
            "timings": {
                "billboard_payload_ms": billboard_ms,
                "year_end_payload_ms": year_end_ms,
                "home_first_response_ms": home_ms,
            },
        }
    finally:
        conn.close()


def _published_billboard_weeks(path: Path) -> set[str]:
    from backend.core.cache_manager import invalidate_all
    from backend.domains.billboard.chart_compute import compute_billboard_data

    _set_database(path)
    invalidate_all()
    payload = compute_billboard_data(dynamic_threshold=True)
    return {str(value) for value in payload["meta"]["all_weeks_asc"]}


def _public_projection(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "facts": {k: snapshot["facts"][k] for k in ("row_count", "digest")},
        "credits": {k: snapshot["credits"][k] for k in ("row_count", "digest")},
        "active_track_albums": {
            k: snapshot["active_track_albums"][k] for k in ("row_count", "digest")
        },
        "album_projects": {
            name: {k: value[k] for k in ("row_count", "digest")}
            for name, value in snapshot["album_projects"].items()
        },
        "track_groups": {
            name: {k: value[k] for k in ("row_count", "digest")}
            for name, value in snapshot["track_groups"].items()
        },
        "aggregates": {
            name: {k: value[k] for k in ("row_count", "digest")}
            for name, value in snapshot["aggregates"].items()
        },
        "candidates": {k: snapshot["candidates"][k] for k in ("row_count", "digest")},
        "search": {k: snapshot["search"][k] for k in ("variant_count", "row_count", "digest")},
        "year_partition": {
            k: snapshot["year_partition"][k]
            for k in ("fact_row_count", "fact_digest", "audit_digest")
        },
        "billboard": snapshot["billboard"],
        "year_end": {"digest": snapshot["year_end"]["digest"]},
        "yearly_artifact": snapshot["yearly_artifact"],
        "home": snapshot["home"],
        "timings": snapshot["timings"],
    }


def _equivalence(incremental: dict[str, Any], replacement: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "active_facts": incremental["facts"]["rows"] == replacement["facts"]["rows"],
        "credits": incremental["credits"]["rows"] == replacement["credits"]["rows"],
        "active_track_album_closure": incremental["active_track_albums"]["rows"]
        == replacement["active_track_albums"]["rows"],
        "album_projects": all(
            incremental["album_projects"][name]["rows"]
            == replacement["album_projects"][name]["rows"]
            for name in ALBUM_PROJECT_PROJECTIONS
        ),
        "track_groups": all(
            incremental["track_groups"][name]["rows"] == replacement["track_groups"][name]["rows"]
            for name in TRACK_GROUP_PROJECTIONS
        ),
        "billboard_aggregates": all(
            incremental["aggregates"][table]["rows"] == replacement["aggregates"][table]["rows"]
            for table in AGGREGATE_TABLES
        ),
        "billboard_payload": incremental["billboard"]["digest"]
        == replacement["billboard"]["digest"],
        "power": incremental["billboard"]["power_digest"]
        == replacement["billboard"]["power_digest"],
        "records": incremental["billboard"]["records_digest"]
        == replacement["billboard"]["records_digest"],
        "year_end_input_and_payload": incremental["year_end"]["payload"]
        == replacement["year_end"]["payload"],
        "search_candidates": incremental["candidates"]["rows"] == replacement["candidates"]["rows"],
        "four_search_snapshots": incremental["search"]["rows"] == replacement["search"]["rows"],
        "year_partition_facts": incremental["year_partition"]["fact_rows"]
        == replacement["year_partition"]["fact_rows"],
        "home_archive": incremental["home"]["archive_digest"]
        == replacement["home"]["archive_digest"],
    }
    return {"passed": all(checks.values()), "checks": checks}


def _phase(
    path: Path,
    data_dir: Path,
    account_dir: Path,
    *,
    expected_relation: str,
    mode: ImportExecutionMode,
    generation_id: str,
    strategy: ImportStrategy,
    requested_mode: ImportRequestMode = "auto",
    maintain_derived: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, float]]:
    started = time.perf_counter()
    assessment, staging_ms = _timed(
        lambda: _assess(path, data_dir, account_dir, requested_mode=requested_mode)
    )
    if assessment.plan.relation.value != expected_relation:
        if assessment.staging is not None:
            assessment.staging.close()
        raise AcceptanceError(
            f"expected relation {expected_relation}, got {assessment.plan.relation.value}"
        )
    result, import_timings = _execute_import(
        path,
        data_dir,
        assessment,
        mode=mode,
        generation_id=generation_id,
        strategy=strategy,
    )
    if maintain_derived:
        derived, derived_timings = _run_derived(path, result["change_set"])
    else:
        derived, derived_timings = {}, {}
    timings = {
        "staging_and_plan_ms": staging_ms,
        **import_timings,
        **derived_timings,
        "end_to_end_ms": round((time.perf_counter() - started) * 1000, 3),
    }
    return result, derived, timings


def _raw_bundle_manifest(streaming_dir: Path) -> tuple[tuple[str, int, int], ...]:
    files = sorted(streaming_dir.glob("Streaming_History_Audio_*.json"))
    files.extend(sorted(streaming_dir.glob("Streaming_History_Video_*.json")))
    if not files:
        raise AcceptanceError("real streaming directory contains no supported export files")
    return tuple((path.name, path.stat().st_size, path.stat().st_mtime_ns) for path in files)


def _run_real_source_baseline(
    workdir: Path,
    *,
    streaming_dir: Path,
    account_dir: Path,
    expected_record_count: int,
) -> dict[str, Any]:
    """Exercise the real export through facts and every deterministic consumer."""
    run_started = time.perf_counter()
    streaming = streaming_dir.expanduser().resolve(strict=True)
    account = account_dir.expanduser().resolve(strict=True)
    manifest_before = _raw_bundle_manifest(streaming)
    target = workdir / "real-source-baseline.db"
    assessment, staging_ms = _timed(lambda: _assess(target, streaming, account))
    if assessment.plan.relation.value != "baseline_required":
        if assessment.staging is not None:
            assessment.staging.close()
        raise AcceptanceError("empty real-source target did not request a baseline")
    result, import_timings = _execute_import(
        target,
        streaming,
        assessment,
        mode="replace",
        generation_id="acceptance-real-source-baseline",
        strategy="full",
    )
    derived, derived_timings = _run_derived(target, result["change_set"])

    from backend.core.cache_manager import invalidate_all
    from backend.domains.billboard.chart_compute import compute_billboard_data
    from backend.domains.home.overview import build_home_overview
    from backend.services.yearly_review_service import build_default_yearly_review_context

    _set_database(target)
    invalidate_all()
    billboard, billboard_payload_ms = _timed(lambda: compute_billboard_data(dynamic_threshold=True))
    conn = db_mod.get_db(readonly=True)
    try:
        home, home_first_response_ms = _timed(
            lambda: build_home_overview(conn, build_default_yearly_review_context())
        )
    finally:
        conn.close()
    before_identical = target.stat()
    identical, identical_ms = _timed(lambda: _assess(target, streaming, account))
    try:
        relation = identical.plan.relation.value
        incoming_count = identical.plan.incoming_count
    finally:
        if identical.staging is not None:
            identical.staging.close()
    after_identical = target.stat()
    manifest_unchanged = manifest_before == _raw_bundle_manifest(streaming)
    passed = bool(
        relation == "identical"
        and result["active_records"] == incoming_count == expected_record_count
        and result["dataset_digest"] == result["input_dataset_digest"]
        and before_identical.st_size == after_identical.st_size
        and before_identical.st_mtime_ns == after_identical.st_mtime_ns
        and manifest_unchanged
        and derived["search"]["ready_count"] == 4
        and derived["search"]["failed_count"] == 0
        and bool(billboard["meta"]["all_weeks_asc"])
        and home["state"] in {"ready", "empty"}
    )
    return {
        "status": "passed" if passed else "failed",
        "passed": passed,
        "validates_source_fingerprints": True,
        "source_files": len(manifest_before),
        "active_records": result["active_records"],
        "identical_relation": relation,
        "identical_no_write": bool(
            before_identical.st_size == after_identical.st_size
            and before_identical.st_mtime_ns == after_identical.st_mtime_ns
        ),
        "raw_bundle_unchanged": manifest_unchanged,
        "derived": derived,
        "consumer_checks": {
            "billboard_week_count": len(billboard["meta"]["all_weeks_asc"]),
            "search_ready_variants": derived["search"]["ready_count"],
            "home_state": home["state"],
        },
        "timings": {
            "baseline_staging_and_plan_ms": staging_ms,
            **import_timings,
            **derived_timings,
            "billboard_payload_ms": billboard_payload_ms,
            "home_first_response_ms": home_first_response_ms,
            "identical_staging_and_plan_ms": identical_ms,
            "end_to_end_ms": round((time.perf_counter() - run_started) * 1000, 3),
        },
    }


def run_acceptance(
    source_db: Path,
    workdir: Path,
    *,
    real_streaming_dir: Path | None = None,
    real_account_dir: Path | None = None,
) -> dict[str, Any]:
    guard = _source_guard(source_db)
    baseline_records, append_records, same_week_records, final_records = synthetic_datasets()
    account_dir = workdir / "account"
    baseline_dir = workdir / "bundle-baseline"
    append_dir = workdir / "bundle-append"
    same_week_dir = workdir / "bundle-same-week-append"
    final_dir = workdir / "bundle-final"
    _write_account(account_dir)
    _write_bundle(baseline_dir, baseline_records)
    _write_bundle(append_dir, append_records)
    _write_bundle(same_week_dir, same_week_records)
    _write_bundle(final_dir, final_records)

    baseline_db = workdir / "baseline.db"
    baseline_result, baseline_derived, baseline_timings = _phase(
        baseline_db,
        baseline_dir,
        account_dir,
        expected_relation="baseline_required",
        mode="replace",
        generation_id=BASE_GENERATION,
        strategy="full",
        maintain_derived=False,
    )
    _seed_synthetic_metadata(baseline_db)
    # Metadata is a deterministic fixture dependency of Album Project L2/L3.
    # Re-run the derived baseline after it is populated, then clone this exact base.
    baseline_derived, baseline_derived_timings = _run_derived(
        baseline_db, baseline_result["change_set"]
    )
    baseline_timings.update(
        {f"metadata_ready_{key}": value for key, value in baseline_derived_timings.items()}
    )
    yearly_before_identical = _yearly_invalidation_state(baseline_db)

    state_before = sqlite3.connect(baseline_db)
    try:
        before_digest = str(
            state_before.execute(
                "SELECT dataset_digest FROM playback_import_state WHERE state_id=1"
            ).fetchone()[0]
        )
        before_counts = tuple(
            int(state_before.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ("plays", *AGGREGATE_TABLES)
        )
    finally:
        state_before.close()
    identical, identical_ms = _timed(lambda: _assess(baseline_db, baseline_dir, account_dir))
    try:
        identical_relation = identical.plan.relation.value
    finally:
        if identical.staging is not None:
            identical.staging.close()
    yearly_after_identical = _yearly_invalidation_state(baseline_db)
    state_after = sqlite3.connect(baseline_db)
    try:
        after_digest = str(
            state_after.execute(
                "SELECT dataset_digest FROM playback_import_state WHERE state_id=1"
            ).fetchone()[0]
        )
        after_counts = tuple(
            int(state_after.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ("plays", *AGGREGATE_TABLES)
        )
    finally:
        state_after.close()
    identical_no_write = bool(
        identical_relation == "identical"
        and before_digest == after_digest
        and before_counts == after_counts
    )

    incremental_db = workdir / "incremental.db"
    replacement_db = workdir / "replacement.db"
    _online_backup(baseline_db, incremental_db)

    append_result, append_derived, append_timings = _phase(
        incremental_db,
        append_dir,
        account_dir,
        expected_relation="snapshot_superset",
        mode="append",
        generation_id=APPEND_GENERATION,
        strategy="incremental",
    )
    yearly_after_append = _yearly_invalidation_state(incremental_db)
    append_change = append_result["change_set"]
    previous_open = append_change.previous_open_week
    current_open = append_change.current_open_week
    published_weeks = _published_billboard_weeks(incremental_db)
    complete_week_gate = bool(
        previous_open
        and current_open
        and str(previous_open) in published_weeks
        and str(current_open) not in published_weeks
    )

    second_append_result, second_append_derived, second_append_timings = _phase(
        incremental_db,
        same_week_dir,
        account_dir,
        expected_relation="snapshot_superset",
        mode="append",
        generation_id=SECOND_APPEND_GENERATION,
        strategy="incremental",
    )
    yearly_after_second_append = _yearly_invalidation_state(incremental_db)

    reconcile_result, reconcile_derived, reconcile_timings = _phase(
        incremental_db,
        final_dir,
        account_dir,
        expected_relation="reconciled_snapshot",
        mode="reconcile",
        generation_id=RECONCILE_GENERATION,
        strategy="reconcile",
    )
    yearly_after_reconcile = _yearly_invalidation_state(incremental_db)
    replace_result, _unused_replace_derived, replace_timings = _phase(
        replacement_db,
        final_dir,
        account_dir,
        expected_relation="baseline_required",
        mode="replace",
        generation_id=REPLACE_GENERATION,
        strategy="full",
        requested_mode="replace",
        maintain_derived=False,
    )
    _seed_synthetic_metadata(replacement_db)
    replace_derived, replace_derived_timings = _run_derived(
        replacement_db, replace_result["change_set"]
    )
    replace_timings.update(replace_derived_timings)
    replace_timings["end_to_end_ms"] = round(
        replace_timings["end_to_end_ms"] + sum(replace_derived_timings.values()), 3
    )

    incremental_snapshot = _semantic_snapshot(incremental_db, reconcile_derived)
    replacement_snapshot = _semantic_snapshot(replacement_db, replace_derived)
    equivalence = _equivalence(incremental_snapshot, replacement_snapshot)
    real_source = None
    if real_streaming_dir is not None:
        if real_account_dir is None:
            raise AcceptanceError("real account directory is required with real source baseline")
        real_source = _run_real_source_baseline(
            workdir,
            streaming_dir=real_streaming_dir,
            account_dir=real_account_dir,
            expected_record_count=int(guard["profile"]["play_count"]),
        )
    source_unchanged = _verify_source_guard(guard)
    if not source_unchanged:
        raise AcceptanceError("source database changed during read-only acceptance")

    strategy_gates = {
        "append_billboard_partition": append_derived["aggregation"]["strategy"] == "partition",
        "first_append_search_bounded_fallback": append_derived["search"]["strategy"]
        == "shared_full_snapshot_rebuild",
        "second_append_search_delta": second_append_derived["search"]["strategy"]
        == "incremental_snapshot_delta",
        "reconcile_billboard_partition": reconcile_derived["aggregation"]["strategy"]
        == "historical_partition",
        "reconcile_album_project_safe_fallback": reconcile_derived["album_project"]["strategy"]
        == "full",
        "replace_full_billboard": replace_derived["aggregation"]["strategy"] == "full",
    }
    yearly_artifact_contract = {
        "fact_partition_equal": equivalence["checks"]["year_partition_facts"],
        "identical_fact_partition_unchanged": yearly_before_identical["direct_digest"]
        == yearly_after_identical["direct_digest"],
        "identical_impact_revision_unchanged": yearly_before_identical["impact_revision"]
        == yearly_after_identical["impact_revision"],
        "identical_cache_key_unchanged": yearly_before_identical["cache_key"]
        == yearly_after_identical["cache_key"],
        "append_invalidated_impacted_year": _accepted_change_invalidated(
            yearly_after_identical, yearly_after_append
        ),
        "same_week_append_invalidated_impacted_year": _accepted_change_invalidated(
            yearly_after_append, yearly_after_second_append
        ),
        "reconcile_invalidated_impacted_year": _accepted_change_invalidated(
            yearly_after_second_append, yearly_after_reconcile
        ),
    }
    yearly_artifact_contract["passed"] = all(yearly_artifact_contract.values())
    passed = bool(
        guard["profile"]["quick_check"] == "ok"
        and source_unchanged
        and identical_no_write
        and complete_week_gate
        and all(strategy_gates.values())
        and yearly_artifact_contract["passed"]
        and equivalence["passed"]
        and (real_source is None or real_source["passed"])
    )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "passed" if passed else "failed",
        "passed": passed,
        "privacy": {
            "writes_confined_to_disposable_workdir": True,
            "source_database_opened_readonly": True,
            "source_path_emitted": False,
            "synthetic_entity_names_only": True,
        },
        "source_database": {
            **guard["profile"],
            "unchanged": source_unchanged,
        },
        "real_source_baseline": real_source,
        "fixture": {
            "baseline_records": len(baseline_records),
            "append_records": len(append_records),
            "same_week_append_records": len(same_week_records),
            "final_records": len(final_records),
            "baseline_weeks": 12,
            "historical_corrections": 1,
        },
        "identical": {
            "detected_relation": identical_relation,
            "no_write_proven": identical_no_write,
            "staging_and_plan_ms": identical_ms,
        },
        "append": {
            "detected_relation": "snapshot_superset",
            "inserted_records": append_result["inserted_records"],
            "unchanged_records": append_result["unchanged_records"],
            "change_set": append_change.to_dict(),
            "derived": append_derived,
            "complete_week_gate": complete_week_gate,
            "timings": append_timings,
        },
        "reconcile": {
            "detected_relation": "reconciled_snapshot",
            "inserted_records": reconcile_result["inserted_records"],
            "unchanged_records": reconcile_result["unchanged_records"],
            "change_set": reconcile_result["change_set"].to_dict(),
            "derived": reconcile_derived,
            "timings": reconcile_timings,
        },
        "second_append": {
            "detected_relation": "snapshot_superset",
            "inserted_records": second_append_result["inserted_records"],
            "unchanged_records": second_append_result["unchanged_records"],
            "change_set": second_append_result["change_set"].to_dict(),
            "derived": second_append_derived,
            "timings": second_append_timings,
        },
        "replacement_reference": {
            "active_records": replace_result["active_records"],
            "derived": replace_derived,
            "timings": replace_timings,
        },
        "baseline": {
            "active_records": baseline_result["active_records"],
            "derived": baseline_derived,
            "timings": baseline_timings,
        },
        "strategy_gates": strategy_gates,
        "yearly_artifact_contract": yearly_artifact_contract,
        "equivalence": equivalence,
        "final_incremental": _public_projection(incremental_snapshot),
        "final_replacement": _public_projection(replacement_snapshot),
        "yearly_key_interpretation": {
            "fact_partition_equal": equivalence["checks"]["year_partition_facts"],
            "artifact_keys_equal": incremental_snapshot["yearly_artifact"]["cache_key"]
            == replacement_snapshot["yearly_artifact"]["cache_key"],
            "note": (
                "Cross-path artifact-key equality is intentionally not a gate. "
                "impact_revision records accepted mutation history; factual partitions "
                "must be equal, every accepted impacted-year change must invalidate its "
                "key, and an identical import must preserve it."
            ),
        },
    }


def _emit(report: dict[str, Any], args: argparse.Namespace) -> None:
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.json_output:
        output = args.json_output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    if args.json:
        print(payload, end="")
    else:
        print(
            f"status={report['status']} "
            f"append_ms={report['append']['timings']['end_to_end_ms']} "
            f"reconcile_ms={report['reconcile']['timings']['end_to_end_ms']} "
            f"equivalent={report['equivalence']['passed']}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    source_db = args.source_db.expanduser().resolve(strict=True)
    with managed_workdir(
        args.workdir,
        source_db=source_db,
        keep=args.keep_workdir,
    ) as workdir:
        report = run_acceptance(
            source_db,
            workdir,
            real_streaming_dir=(args.real_streaming_dir if args.real_source_baseline else None),
            real_account_dir=(args.real_account_dir if args.real_source_baseline else None),
        )
        _emit(report, args)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
