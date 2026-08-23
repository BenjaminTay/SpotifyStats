"""ETL pipeline: import Spotify Extended Streaming History JSON into SQLite."""

from __future__ import annotations

import glob
import json
import os
import re
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from backend.domains.imports.incremental import (
    FINGERPRINT_VERSION,
    FingerprintRecord,
    RecordIdentity,
    dataset_digest,
)
from backend.domains.imports.source_inspector import record_fingerprint
from backend.domains.imports.streaming_staging import StreamingImportStaging

from .db import build_aggregations, ensure_schema, get_db, init_db
from .utils import classify_platform, convert_to_local_time

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "streaming",
)

_PLAY_INSERT_SQL = """INSERT INTO plays(
   ts, ts_year, ts_month, ts_week, ts_dow, ts_hour,
   ts_date, platform, ms_played, conn_country, track_id,
   reason_start, reason_end, shuffle, skipped, offline, incognito_mode,
   content_type, source_album_id, spotify_track_id_at_play,
   source_fingerprint, source_fingerprint_version, import_generation_id)
   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
_PLAY_BATCH_SIZE = 5000


def _replace_schema_is_transaction_ready(conn: sqlite3.Connection) -> bool:
    """Return whether replace can start without an in-transaction migration.

    Historical replace upgraded duplicate dimensions only after deleting and
    committing playback facts.  That sequence cannot be made rollback-safe.
    Current versioned databases already have the fingerprint columns and the
    uniqueness constraints required by the importer; non-empty older schemas
    must therefore fail before any destructive statement.
    """

    play_columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(plays)")}
    required_columns = {
        "source_fingerprint",
        "source_fingerprint_version",
        "import_generation_id",
    }
    indexes = {
        str(row[0]): bool(row[2])
        for row in conn.execute(
            """SELECT name, sql, CASE WHEN sql LIKE 'CREATE UNIQUE INDEX%' THEN 1 ELSE 0 END
               FROM sqlite_master WHERE type='index'"""
        ).fetchall()
    }
    return required_columns.issubset(play_columns) and all(
        indexes.get(name, False)
        for name in (
            "idx_tracks_artist_name",
            "idx_albums_name_artist",
            "uq_plays_source_fingerprint",
        )
    )


def _prepare_replace_schema() -> None:
    """Upgrade empty/current databases, but fail closed on populated legacy ones."""

    probe = get_db(readonly=False)
    try:
        ready = _replace_schema_is_transaction_ready(probe)
        has_facts = bool(probe.execute("SELECT 1 FROM plays LIMIT 1").fetchone())
    finally:
        probe.close()
    if not ready and has_facts:
        raise RuntimeError(
            "non-empty legacy playback schema cannot be upgraded inside an atomic replace; "
            "migrate or restore it before importing"
        )
    # Empty legacy databases and already-versioned databases can be brought to
    # the latest schema before the playback write transaction starts.
    ensure_schema()


# ── Featured artist parsing ──────────────────────────────────────────────

# Patterns that should NOT be treated as featured artists
_NON_ARTIST = re.compile(
    r"(?:re)?mix|live|version|edit|acoustic|instrumental|demo|"
    r"remaster(?:ed)?|radio\s*edit|single\s*edit|"
    r"Taylor's\s*Version|From\s*The\s*Vault|bonus\s*track|"
    r"deluxe|extended|original\s*mix|club\s*mix|"
    r"cover|tribute|reprise|interlude|intro|outro|"
    r"solo|stripped|acapella|a\s*cappella|"
    r"orchestral|symphonic|unplugged",
    re.IGNORECASE,
)

# Patterns to extract featured/with artists from track names
_FEAT_PATTERNS = [
    re.compile(r"\(feat\.?\s+([^)]+)\)", re.IGNORECASE),
    re.compile(r"\(ft\.?\s+([^)]+)\)", re.IGNORECASE),
    re.compile(r"\(with\s+([^)]+)\)", re.IGNORECASE),
    re.compile(r"\[feat\.?\s+([^\]]+)\]", re.IGNORECASE),
    re.compile(r"\[ft\.?\s+([^\]]+)\]", re.IGNORECASE),
    re.compile(r"\[with\s+([^\]]+)\]", re.IGNORECASE),
]


def _parse_featured_artists(track_name: str) -> list[str]:
    """Extract featured artist names from track name patterns like '(feat. X)'.

    Returns empty list if no featured artists are found.
    Handles multiple artists separated by ',' or '&'.
    """
    if not track_name:
        return []

    featured: list[str] = []
    for pattern in _FEAT_PATTERNS:
        for match in pattern.findall(track_name):
            for part in re.split(r"\s*[,&]\s*", match):
                part = part.strip()
                if part and not _NON_ARTIST.fullmatch(part):
                    featured.append(part)

    seen: set[str] = set()
    result: list[str] = []
    for name in featured:
        if name.lower() not in seen:
            seen.add(name.lower())
            result.append(name)
    return result


def _spotify_track_id_from_uri(uri: str | None) -> str | None:
    if not uri or not uri.startswith("spotify:track:"):
        return None
    return uri.rsplit(":", 1)[-1] or None


def _cache_artist(conn, name: str, cache: dict[str, int]) -> int:
    if name in cache:
        return cache[name]
    row = conn.execute("SELECT artist_id FROM artists WHERE artist_name = ?", (name,)).fetchone()
    if row:
        cache[name] = row[0]
    else:
        cur = conn.execute("INSERT INTO artists(artist_name) VALUES (?)", (name,))
        cache[name] = cur.lastrowid
    return cache[name]


def _cache_album(conn, album_name: str, artist_id: int, cache: dict[tuple, int]) -> int:
    key = (album_name, artist_id)
    if key in cache:
        return cache[key]
    row = conn.execute(
        "SELECT album_id FROM albums WHERE album_name = ? AND artist_id = ?",
        (album_name, artist_id),
    ).fetchone()
    if row:
        cache[key] = row[0]
    else:
        cur = conn.execute(
            "INSERT INTO albums(album_name, artist_id) VALUES (?, ?)",
            (album_name, artist_id),
        )
        cache[key] = cur.lastrowid
    return cache[key]


def _cache_track(
    conn,
    track_name: str,
    artist_id: int,
    album_id: int | None,
    spotify_uri: str | None,
    cache: dict[tuple, int],
) -> int:
    # Use (artist_id, track_name) as canonical key to merge duplicate versions
    key = (artist_id, track_name)
    if key in cache:
        tid = cache[key]
    else:
        row = conn.execute(
            "SELECT track_id FROM tracks WHERE track_name = ? AND artist_id = ?",
            (track_name, artist_id),
        ).fetchone()
        if row:
            tid = row[0]
        else:
            # Check by spotify_track_id before inserting — catches duplicates
            # with different punctuation in the track name (e.g. half-width
            # vs full-width comma).
            spotify_tid = _spotify_track_id_from_uri(spotify_uri)
            if spotify_tid:
                existing = conn.execute(
                    "SELECT track_id FROM tracks WHERE spotify_track_id = ? AND artist_id = ?",
                    (spotify_tid, artist_id),
                ).fetchone()
                if existing:
                    row = existing
            if row:
                tid = row[0]
            else:
                cur = conn.execute(
                    """INSERT INTO tracks(track_name, artist_id, album_id, spotify_track_uri, spotify_track_id)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        track_name,
                        artist_id,
                        album_id,
                        spotify_uri,
                        spotify_tid,
                    ),
                )
                tid = cur.lastrowid
        cache[key] = tid

    # If track already existed and current play has a different album, record the association
    if album_id is not None:
        conn.execute(
            "INSERT OR IGNORE INTO track_albums(track_id, album_id) VALUES (?, ?)",
            (tid, album_id),
        )

    return tid


def _load_append_fingerprints(conn) -> set[tuple[str, str]]:
    """Load a complete active fingerprint baseline or reject append mode."""

    total = int(conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0])
    rows = conn.execute(
        """SELECT content_type, source_fingerprint
           FROM plays
           WHERE source_fingerprint IS NOT NULL
             AND source_fingerprint_version = ?""",
        (FINGERPRINT_VERSION,),
    ).fetchall()
    if len(rows) != total:
        raise ValueError(
            "append mode requires every active play to have a compatible source fingerprint"
        )
    keys = {(str(row[0]), str(row[1])) for row in rows}
    if len(keys) != total:
        raise ValueError("append mode requires a unique active source fingerprint baseline")
    return keys


def _active_dataset_summary(conn) -> tuple[int, str | None, str | None, str]:
    """Return the active fingerprint count, date range, and stable digest."""

    rows = conn.execute(
        """SELECT content_type, source_fingerprint, ts
           FROM plays
           WHERE source_fingerprint IS NOT NULL
             AND source_fingerprint_version = ?
           ORDER BY content_type, source_fingerprint""",
        (FINGERPRINT_VERSION,),
    ).fetchall()
    active_count = int(conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0])
    if len(rows) != active_count:
        raise RuntimeError(
            "active playback dataset contains records without compatible fingerprints"
        )
    date_row = conn.execute("SELECT MIN(ts), MAX(ts) FROM plays").fetchone()
    records = [FingerprintRecord(source_type=str(row[0]), fingerprint=str(row[1])) for row in rows]
    return (
        active_count,
        str(date_row[0]) if date_row and date_row[0] else None,
        str(date_row[1]) if date_row and date_row[1] else None,
        dataset_digest(records),
    )


def _stage_reconcile_removals(
    conn: sqlite3.Connection,
    removed_identities: frozenset[RecordIdentity],
) -> list[dict[str, Any]]:
    """Validate and stage exact removals, returning compact pre-delete evidence."""

    conn.execute(
        """CREATE TEMP TABLE reconcile_removed_identity(
               content_type TEXT NOT NULL,
               source_fingerprint TEXT NOT NULL,
               PRIMARY KEY(content_type, source_fingerprint)
           ) WITHOUT ROWID"""
    )
    conn.executemany(
        "INSERT INTO reconcile_removed_identity VALUES (?, ?)",
        ((item.source_type, item.fingerprint) for item in removed_identities),
    )
    rows = conn.execute(
        """SELECT p.play_id, p.ts, p.ts_date, p.ts_year, p.ts_month,
                  p.track_id, p.source_album_id, p.ms_played,
                  p.spotify_track_id_at_play, p.spotify_album_id_at_play
           FROM plays p
           JOIN reconcile_removed_identity r
             ON r.content_type=p.content_type
            AND r.source_fingerprint=p.source_fingerprint
           WHERE p.source_fingerprint_version=?
           ORDER BY p.ts, p.play_id""",
        (FINGERPRINT_VERSION,),
    ).fetchall()
    if len(rows) != len(removed_identities):
        raise RuntimeError(
            "reconcile removal scope does not exactly match the active fingerprint baseline"
        )
    # Fingerprints and raw source records deliberately do not cross this
    # boundary.  This compact fact-impact evidence is safe to persist as part
    # of the downstream ChangeSet.
    return [dict(row) for row in rows]


def _delete_staged_reconcile_rows(conn: sqlite3.Connection, expected_count: int) -> None:
    cursor = conn.execute(
        """DELETE FROM plays
           WHERE source_fingerprint_version=?
             AND EXISTS (
                 SELECT 1 FROM reconcile_removed_identity r
                 WHERE r.content_type=plays.content_type
                   AND r.source_fingerprint=plays.source_fingerprint
             )""",
        (FINGERPRINT_VERSION,),
    )
    if cursor.rowcount != expected_count:
        raise RuntimeError("reconcile deletion count changed after the removal scope was validated")


def _synchronize_active_track_album_observations(
    conn: sqlite3.Connection,
    affected_track_ids: set[int] | None = None,
) -> None:
    """Make automatic track/album observations match the active fact set.

    ``track_albums`` has no manual provenance and is populated from streaming
    imports.  Treating it as an append-only catalog leaks removed reconcile
    observations into every consumer that joins through ``track_id``.  Rebuild
    the small distinct projection inside the same transaction that publishes
    ``plays`` so readers can never observe facts and relationships from
    different generations.  Reconcile supplies an exact affected-track scope;
    replace rebuilds the full active projection.

    ``tracks.album_id`` remains the stable primary container while it is still
    supported by an active play.  If that relationship disappeared, select the
    most recently observed active album deterministically.  Manual Album
    Project membership lives in separate ``album_project_*`` tables and is not
    touched here.
    """

    conn.execute("DROP TABLE IF EXISTS temp.active_track_album_scope")
    conn.execute("DROP TABLE IF EXISTS temp.active_track_album_observation")
    conn.execute(
        """CREATE TEMP TABLE active_track_album_scope(
               track_id INTEGER PRIMARY KEY
           ) WITHOUT ROWID"""
    )
    if affected_track_ids is None:
        conn.execute(
            """INSERT INTO active_track_album_scope(track_id)
               SELECT track_id FROM tracks"""
        )
    else:
        conn.executemany(
            "INSERT INTO active_track_album_scope(track_id) VALUES (?)",
            ((track_id,) for track_id in sorted(affected_track_ids)),
        )
    conn.execute(
        """CREATE TEMP TABLE active_track_album_observation(
               track_id INTEGER NOT NULL,
               album_id INTEGER NOT NULL,
               last_ts TEXT NOT NULL,
               PRIMARY KEY(track_id, album_id)
           ) WITHOUT ROWID"""
    )
    conn.execute(
        """INSERT INTO active_track_album_observation(track_id, album_id, last_ts)
           SELECT p.track_id, p.source_album_id, MAX(p.ts)
           FROM plays p
           JOIN active_track_album_scope scope ON scope.track_id=p.track_id
           WHERE p.source_album_id IS NOT NULL
           GROUP BY p.track_id, p.source_album_id"""
    )
    conn.execute(
        """DELETE FROM track_albums
           WHERE EXISTS (
               SELECT 1 FROM active_track_album_scope scope
               WHERE scope.track_id=track_albums.track_id
           )
             AND NOT EXISTS (
               SELECT 1
               FROM active_track_album_observation active
               WHERE active.track_id=track_albums.track_id
                 AND active.album_id=track_albums.album_id
           )"""
    )
    conn.execute(
        """INSERT OR IGNORE INTO track_albums(track_id, album_id)
           SELECT track_id, album_id FROM active_track_album_observation"""
    )
    conn.execute(
        """UPDATE tracks
           SET album_id=(
               SELECT active.album_id
               FROM active_track_album_observation active
               WHERE active.track_id=tracks.track_id
               ORDER BY active.last_ts DESC, active.album_id ASC
               LIMIT 1
           )
           WHERE EXISTS (
               SELECT 1 FROM active_track_album_scope scope
               WHERE scope.track_id=tracks.track_id
           )
             AND EXISTS (
               SELECT 1 FROM active_track_album_observation active
               WHERE active.track_id=tracks.track_id
             )
             AND NOT EXISTS (
               SELECT 1 FROM active_track_album_observation active
               WHERE active.track_id=tracks.track_id
                 AND active.album_id=tracks.album_id
           )"""
    )
    conn.execute(
        """UPDATE tracks
           SET album_id=NULL
           WHERE EXISTS (
               SELECT 1 FROM active_track_album_scope scope
               WHERE scope.track_id=tracks.track_id
           )
             AND NOT EXISTS (
               SELECT 1 FROM plays p WHERE p.track_id=tracks.track_id
           )"""
    )
    conn.execute("DROP TABLE active_track_album_observation")
    conn.execute("DROP TABLE active_track_album_scope")


def import_data(
    data_dir: str | None = None,
    progress_callback=None,
    agg_min_ms: int = 30000,
    agg_music_only: bool = True,
    agg_week_start_dow: int = 4,
    agg_week_start_hour: int = 0,
    agg_dynamic_threshold: bool = True,
    agg_max_merge_gap_minutes: int | None = 5,
    build_preaggregations: bool = True,
    mode: Literal["replace", "append", "reconcile"] = "replace",
    generation_id: str | None = None,
    expected_previous_digest: str | None = None,
    removed_identities: frozenset[RecordIdentity] | None = None,
    before_final_commit: Callable[[sqlite3.Connection, dict[str, Any]], None] | None = None,
    staging: StreamingImportStaging | None = None,
) -> dict[str, Any]:
    """Run the ETL with deterministic rollback and connection cleanup."""
    connection_holder: list[sqlite3.Connection] = []
    try:
        return _import_data_impl(
            data_dir=data_dir,
            progress_callback=progress_callback,
            agg_min_ms=agg_min_ms,
            agg_music_only=agg_music_only,
            agg_week_start_dow=agg_week_start_dow,
            agg_week_start_hour=agg_week_start_hour,
            agg_dynamic_threshold=agg_dynamic_threshold,
            agg_max_merge_gap_minutes=agg_max_merge_gap_minutes,
            build_preaggregations=build_preaggregations,
            mode=mode,
            generation_id=generation_id,
            expected_previous_digest=expected_previous_digest,
            removed_identities=removed_identities,
            before_final_commit=before_final_commit,
            staging=staging,
            connection_holder=connection_holder,
        )
    except Exception:
        if connection_holder:
            connection_holder[0].rollback()
        raise
    finally:
        if connection_holder:
            connection_holder[0].close()


def _import_data_impl(
    data_dir: str | None = None,
    progress_callback=None,
    agg_min_ms: int = 30000,
    agg_music_only: bool = True,
    agg_week_start_dow: int = 4,
    agg_week_start_hour: int = 0,
    agg_dynamic_threshold: bool = True,
    agg_max_merge_gap_minutes: int | None = 5,
    build_preaggregations: bool = True,
    mode: Literal["replace", "append", "reconcile"] = "replace",
    generation_id: str | None = None,
    expected_previous_digest: str | None = None,
    removed_identities: frozenset[RecordIdentity] | None = None,
    before_final_commit: Callable[[sqlite3.Connection, dict[str, Any]], None] | None = None,
    staging: StreamingImportStaging | None = None,
    connection_holder: list[sqlite3.Connection] | None = None,
) -> dict[str, Any]:
    """Import all JSON streaming history files into the SQLite database.

    Args:
        data_dir: Path to the folder containing JSON files.
        progress_callback: Optional callable(step: str, pct: float) for progress.
        agg_*: Parameters for building pre-aggregated Billboard tables after import.
        mode: ``replace`` preserves the historical overwrite behavior;
            ``append`` inserts only fingerprints absent from the active dataset;
            ``reconcile`` atomically deletes and inserts the identities proven
            by a confirmed authoritative snapshot plan.
        generation_id: Import generation attached to newly inserted plays. A
            UUID is generated when the caller does not provide one.
        before_final_commit: Optional validator/publisher invoked on the import
            connection after all facts are visible but before the final commit.

    Returns:
        Dict with summary stats.
    """
    if mode not in {"replace", "append", "reconcile"}:
        raise ValueError("mode must be 'replace', 'append' or 'reconcile'")
    if mode in {"append", "reconcile"} and (
        not expected_previous_digest or before_final_commit is None
    ):
        raise ValueError(
            f"{mode} mode requires an expected previous digest and transactional finalizer"
        )
    if mode == "reconcile" and not removed_identities:
        raise ValueError("reconcile mode requires a non-empty exact removal scope")
    if mode != "reconcile" and removed_identities:
        raise ValueError("removed identities are only valid in reconcile mode")
    if generation_id is None:
        generation_id = str(uuid4())
    elif not isinstance(generation_id, str) or not generation_id.strip():
        raise ValueError("generation_id must be a non-empty string")
    else:
        generation_id = generation_id.strip()

    if data_dir is None:
        data_dir = DATA_DIR

    if staging is not None:
        if staging.source_dir != Path(data_dir).resolve():
            raise ValueError("staging source directory does not match data_dir")
        staging.verify_source_manifest()
        json_files = staging.file_names("audio")
        video_files = staging.file_names("video")
    else:
        json_files = sorted(glob.glob(os.path.join(data_dir, "Streaming_History_Audio_*.json")))
        video_files = sorted(glob.glob(os.path.join(data_dir, "Streaming_History_Video_*.json")))

    if not json_files:
        raise FileNotFoundError(f"No Streaming_History_Audio_*.json files found in {data_dir}")

    # A staged request already has exact counts from its single JSON parse.
    if progress_callback:
        progress_callback("计算总记录数...", 0.0)
    if staging is not None:
        total_records_est = staging.record_count()
    else:
        total_records_est = 0
        for filepath in [*json_files, *video_files]:
            with open(filepath, encoding="utf-8") as f:
                total_records_est += len(json.load(f))

    # Ensure tables exist
    init_db()

    # Append needs the migration-provided fingerprint columns before it can
    # verify the active baseline. Replace may upgrade an empty database here;
    # a populated legacy database fails before any facts are cleared because
    # its former delete/commit/deduplicate migration sequence was not atomic.
    if mode in {"append", "reconcile"}:
        ensure_schema()
    else:
        _prepare_replace_schema()

    # Clear old play data and pre-aggregations only for the historical replace
    # strategy. Append must preserve plays, aggregates and track associations.
    conn = get_db(readonly=False)
    if connection_holder is not None:
        connection_holder.append(conn)
    if mode in {"append", "reconcile"}:
        # Acquire the write reservation before reading the active fingerprint
        # baseline so an external writer cannot swap facts between validation
        # and the first append DML statement.
        conn.execute("BEGIN IMMEDIATE")
    else:
        # Keep clearing, every inserted batch, the transactional finalizer, and
        # the active fact publication under one rollback boundary.
        conn.execute("BEGIN IMMEDIATE")
    if mode == "replace":
        conn.execute("DELETE FROM plays")
        conn.execute("DELETE FROM agg_weekly_tracks")
        conn.execute("DELETE FROM agg_weekly_albums")
        conn.execute("DELETE FROM agg_weekly_track_sources")
        conn.execute("DELETE FROM agg_weekly_artists")
        conn.execute("DELETE FROM agg_config")
        conn.execute("DELETE FROM track_albums")

    existing_fingerprints = (
        _load_append_fingerprints(conn) if mode in {"append", "reconcile"} else set()
    )
    previous_dataset_digest = dataset_digest(
        FingerprintRecord(source_type=source_type, fingerprint=fingerprint)
        for source_type, fingerprint in existing_fingerprints
    )
    if mode in {"append", "reconcile"} and (previous_dataset_digest != expected_previous_digest):
        raise RuntimeError("active playback baseline changed after import planning")
    removed_impact_rows: list[dict[str, Any]] = []
    if mode == "reconcile":
        exact_removals = frozenset(removed_identities or ())
        active_identities = {
            RecordIdentity(source_type=source_type, fingerprint=fingerprint)
            for source_type, fingerprint in existing_fingerprints
        }
        if not exact_removals.issubset(active_identities):
            raise RuntimeError("reconcile removal scope is not a subset of the active baseline")
        removed_impact_rows = _stage_reconcile_removals(conn, exact_removals)

    artist_cache: dict[str, int] = {}
    album_cache: dict[tuple, int] = {}
    track_cache: dict[str, int] = {}

    total_files = len(json_files)
    total_records = 0
    total_skipped = 0
    duplicate_records_skipped = 0
    unchanged_records = 0
    source_records_processed = 0
    seen_audio_records: set[str] = set()
    seen_video_records: set[str] = set()
    inserted_audio_records: set[str] = set()
    inserted_video_records: set[str] = set()

    for file_idx, filepath in enumerate(json_files):
        if staging is not None:
            records = staging.records_for_file(filepath)
        else:
            with open(filepath, encoding="utf-8") as f:
                records = json.load(f)

        plays_batch: list[tuple] = []

        for rec_idx, rec in enumerate(records):
            source_records_processed += 1
            fingerprint = record_fingerprint(rec)
            if fingerprint in seen_audio_records:
                duplicate_records_skipped += 1
                continue
            seen_audio_records.add(fingerprint)
            if ("audio", fingerprint) in existing_fingerprints:
                unchanged_records += 1
                continue
            inserted_audio_records.add(fingerprint)
            ts_raw = rec.get("ts", "")
            country = rec.get("conn_country", "CN")
            time_info = convert_to_local_time(ts_raw, country)

            platform = classify_platform(rec.get("platform", ""))
            ms_played = rec.get("ms_played", 0)
            skipped = 1 if rec.get("skipped") else 0
            if skipped:
                total_skipped += 1

            track_name = rec.get("master_metadata_track_name")
            artist_name = rec.get("master_metadata_album_artist_name")
            album_name = rec.get("master_metadata_album_album_name")
            spotify_uri = rec.get("spotify_track_uri")
            spotify_track_id_at_play = _spotify_track_id_from_uri(spotify_uri)

            # Resolve or create dimension rows
            track_id = None
            album_id = None
            if track_name and artist_name:
                artist_id = _cache_artist(conn, artist_name, artist_cache)
                if album_name:
                    album_id = _cache_album(conn, album_name, artist_id, album_cache)
                track_id = _cache_track(
                    conn, track_name, artist_id, album_id, spotify_uri, track_cache
                )

                # Insert track_artists junction: primary + featured artists
                conn.execute(
                    "INSERT OR IGNORE INTO track_artists(track_id, artist_id, role) VALUES (?, ?, 'primary')",
                    (track_id, artist_id),
                )
                for feat_name in _parse_featured_artists(track_name):
                    feat_id = _cache_artist(conn, feat_name, artist_cache)
                    conn.execute(
                        "INSERT OR IGNORE INTO track_artists(track_id, artist_id, role) VALUES (?, ?, 'featured')",
                        (track_id, feat_id),
                    )

            plays_batch.append(
                (
                    time_info["ts"],
                    time_info["ts_year"],
                    time_info["ts_month"],
                    time_info["ts_week"],
                    time_info["ts_dow"],
                    time_info["ts_hour"],
                    time_info["ts_date"],
                    platform,
                    ms_played,
                    country,
                    track_id,
                    rec.get("reason_start"),
                    rec.get("reason_end"),
                    1 if rec.get("shuffle") else 0,
                    skipped,
                    1 if rec.get("offline") else 0,
                    1 if rec.get("incognito_mode") else 0,
                    "audio",
                    album_id,  # source_album_id from playback-time album
                    spotify_track_id_at_play,
                    fingerprint,
                    FINGERPRINT_VERSION,
                    generation_id,
                )
            )

            # Batch insert every 5000 rows to keep memory in check
            if len(plays_batch) >= _PLAY_BATCH_SIZE:
                conn.executemany(_PLAY_INSERT_SQL, plays_batch)
                total_records += len(plays_batch)
                plays_batch.clear()

            # Progress: per-file granularity
            if progress_callback and total_records_est > 0:
                processed = source_records_processed
                pct = min(0.95, processed / total_records_est)
                if processed % 5000 == 0:
                    progress_callback(
                        f"导入中... {processed:,} / {total_records_est:,} ({pct:.0%})",
                        pct,
                    )

        # Insert remaining batch
        if plays_batch:
            conn.executemany(_PLAY_INSERT_SQL, plays_batch)
            total_records += len(plays_batch)

    # ── Import video records ────────────────────────────────────────────
    video_total = 0
    if video_files:
        for file_idx, filepath in enumerate(video_files):
            if staging is not None:
                records = staging.records_for_file(filepath)
            else:
                with open(filepath, encoding="utf-8") as f:
                    records = json.load(f)

            plays_batch: list[tuple] = []
            for rec in records:
                source_records_processed += 1
                fingerprint = record_fingerprint(rec)
                if fingerprint in seen_video_records:
                    duplicate_records_skipped += 1
                    continue
                seen_video_records.add(fingerprint)
                if ("video", fingerprint) in existing_fingerprints:
                    unchanged_records += 1
                    continue
                inserted_video_records.add(fingerprint)
                ts_raw = rec.get("ts", "")
                country = rec.get("conn_country", "CN")
                time_info = convert_to_local_time(ts_raw, country)

                platform = classify_platform(rec.get("platform", ""))
                ms_played = rec.get("ms_played", 0)
                skipped = 1 if rec.get("skipped") else 0

                track_name = rec.get("master_metadata_track_name")
                artist_name = rec.get("master_metadata_album_artist_name")
                album_name = rec.get("master_metadata_album_album_name")
                spotify_uri = rec.get("spotify_track_uri")
                spotify_track_id_at_play = _spotify_track_id_from_uri(spotify_uri)

                track_id = None
                album_id = None
                if track_name and artist_name:
                    artist_id = _cache_artist(conn, artist_name, artist_cache)
                    if album_name:
                        album_id = _cache_album(conn, album_name, artist_id, album_cache)
                    track_id = _cache_track(
                        conn, track_name, artist_id, album_id, spotify_uri, track_cache
                    )

                    conn.execute(
                        "INSERT OR IGNORE INTO track_artists(track_id, artist_id, role) VALUES (?, ?, 'primary')",
                        (track_id, artist_id),
                    )
                    for feat_name in _parse_featured_artists(track_name):
                        feat_id = _cache_artist(conn, feat_name, artist_cache)
                        conn.execute(
                            "INSERT OR IGNORE INTO track_artists(track_id, artist_id, role) VALUES (?, ?, 'featured')",
                            (track_id, feat_id),
                        )

                plays_batch.append(
                    (
                        time_info["ts"],
                        time_info["ts_year"],
                        time_info["ts_month"],
                        time_info["ts_week"],
                        time_info["ts_dow"],
                        time_info["ts_hour"],
                        time_info["ts_date"],
                        platform,
                        ms_played,
                        country,
                        track_id,
                        rec.get("reason_start"),
                        rec.get("reason_end"),
                        1 if rec.get("shuffle") else 0,
                        skipped,
                        1 if rec.get("offline") else 0,
                        1 if rec.get("incognito_mode") else 0,
                        "video",
                        album_id,
                        spotify_track_id_at_play,
                        fingerprint,
                        FINGERPRINT_VERSION,
                        generation_id,
                    )
                )

                if len(plays_batch) >= _PLAY_BATCH_SIZE:
                    conn.executemany(_PLAY_INSERT_SQL, plays_batch)
                    video_total += len(plays_batch)
                    plays_batch.clear()

                if progress_callback and total_records_est > 0:
                    processed = source_records_processed
                    pct = min(0.95, processed / total_records_est)
                    if processed % 5000 == 0:
                        progress_callback(
                            f"导入视频... {processed:,} / {total_records_est:,} ({pct:.0%})",
                            pct,
                        )

            if plays_batch:
                conn.executemany(_PLAY_INSERT_SQL, plays_batch)
                video_total += len(plays_batch)

    if mode == "reconcile":
        _delete_staged_reconcile_rows(conn, len(removed_impact_rows))

    if mode == "replace":
        _synchronize_active_track_album_observations(conn)
    elif mode == "reconcile":
        affected_track_ids = {
            int(track_id)
            for track_id in [
                *(row.get("track_id") for row in removed_impact_rows),
                *track_cache.values(),
            ]
            if track_id is not None
        }
        _synchronize_active_track_album_observations(conn, affected_track_ids)

    active_records, first_ts, latest_ts, active_digest = _active_dataset_summary(conn)
    inserted_records = total_records + video_total
    input_dataset_digest = dataset_digest(
        [
            *(
                FingerprintRecord(source_type="audio", fingerprint=value)
                for value in seen_audio_records
            ),
            *(
                FingerprintRecord(source_type="video", fingerprint=value)
                for value in seen_video_records
            ),
        ]
    )
    inserted_dataset_digest = dataset_digest(
        [
            *(
                FingerprintRecord(source_type="audio", fingerprint=value)
                for value in inserted_audio_records
            ),
            *(
                FingerprintRecord(source_type="video", fingerprint=value)
                for value in inserted_video_records
            ),
        ]
    )
    if mode == "reconcile":
        incoming_unique_count = len(seen_audio_records) + len(seen_video_records)
        if active_records != incoming_unique_count or active_digest != input_dataset_digest:
            raise RuntimeError(
                "reconcile result does not exactly match the confirmed incoming dataset"
            )
    result = {
        "total_records": inserted_records,
        "audio_records": total_records,
        "video_records": video_total,
        "inserted_records": inserted_records,
        "unchanged_records": unchanged_records,
        "active_records": active_records,
        "dataset_digest": active_digest,
        "input_dataset_digest": input_dataset_digest,
        "inserted_dataset_digest": inserted_dataset_digest,
        "previous_dataset_digest": previous_dataset_digest,
        "first_ts": first_ts,
        "latest_ts": latest_ts,
        "generation_id": generation_id,
        "strategy": mode,
        "total_skipped": total_skipped,
        "duplicate_records_skipped": duplicate_records_skipped,
        "unique_artists": len(artist_cache),
        "unique_albums": len(album_cache),
        "unique_tracks": len(track_cache),
        "files_imported": total_files + len(video_files),
        "agg_track_wks": 0,
        "agg_album_wks": 0,
        "agg_artist_wks": 0,
        "finalized_in_transaction": False,
    }
    if mode == "reconcile":
        result["_removed_impact_rows"] = removed_impact_rows
    if staging is not None:
        # Recheck at the transaction boundary as well as before DB setup. If a
        # confirmed source file changed during ETL, rollback all playback DML.
        staging.verify_source_manifest()
    if before_final_commit is not None:
        before_final_commit(conn, result)
        result["finalized_in_transaction"] = True
    conn.commit()

    # Facts and their active generation are now visible. Drop every runtime
    # playback payload before derived maintenance starts so requests cannot
    # serve a cached response from the previous generation during the rebuild.
    from backend.core.cache_manager import invalidate_playback_caches

    invalidate_playback_caches()

    if build_preaggregations:
        # Build pre-aggregated weekly Billboard tables
        if progress_callback:
            progress_callback("构建预聚合表...", 0.96)
        try:
            agg_results = build_aggregations(
                min_ms=agg_min_ms,
                music_only=agg_music_only,
                week_start_dow=agg_week_start_dow,
                week_start_hour=agg_week_start_hour,
                dynamic_threshold=agg_dynamic_threshold,
                max_merge_gap_minutes=agg_max_merge_gap_minutes,
                progress_callback=progress_callback,
            )
        except Exception as e:
            import logging
            import traceback

            logger = logging.getLogger(__name__)
            logger.warning("预聚合表构建失败（Billboard 页面将使用实时计算）: %s", e)
            traceback.print_exc()
            agg_results = {}
    else:
        agg_results = {}

    result.update(
        agg_track_wks=agg_results.get("tracks", 0),
        agg_album_wks=agg_results.get("albums", 0),
        agg_artist_wks=agg_results.get("artists", 0),
    )

    if progress_callback:
        progress_callback("导入完成", 1.0)

    return result
