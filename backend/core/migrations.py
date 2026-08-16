"""Schema migration system with version tracking and idempotent apply.

Replaces the ad-hoc try/except ALTER TABLE pattern in ensure_schema()
with a versioned migration runner.

Usage:
    from backend.core.migrations import run_migrations
    run_migrations()  # safe to call repeatedly, only applies pending
"""

from __future__ import annotations

import logging
import os
import sqlite3
from collections.abc import Callable

from backend.core.db import SCHEMA

logger = logging.getLogger(__name__)

MIGRATIONS: list[tuple[int, str, Callable[[sqlite3.Connection], None]]] = []

_IDEMPOTENT_OPERATIONAL_ERRORS = (
    "already exists",
    "duplicate column name",
    "duplicate index name",
)


def migration(version: int, name: str):
    """Decorator to register a migration function."""

    def decorator(fn: Callable[[sqlite3.Connection], None]):
        MIGRATIONS.append((version, name, fn))
        return fn

    return decorator


# ── Migration definitions ────────────────────────────────────────────────


@migration(1, "initial_schema")
def migrate_001(conn: sqlite3.Connection):
    """Baseline: create all tables and indexes with IF NOT EXISTS."""
    existing_tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    if "plays" in existing_tables:
        play_columns = {
            row["name"] if isinstance(row, sqlite3.Row) else row[1]
            for row in conn.execute("PRAGMA table_info(plays)").fetchall()
        }
        if "spotify_track_id_at_play" not in play_columns:
            conn.execute("ALTER TABLE plays ADD COLUMN spotify_track_id_at_play TEXT")
        if "spotify_album_id_at_play" not in play_columns:
            conn.execute("ALTER TABLE plays ADD COLUMN spotify_album_id_at_play TEXT")
    conn.executescript(SCHEMA)


@migration(2, "plays_content_type")
def migrate_002(conn: sqlite3.Connection):
    conn.execute("ALTER TABLE plays ADD COLUMN content_type TEXT NOT NULL DEFAULT 'audio'")


@migration(3, "spotify_album_meta_album_artists")
def migrate_003(conn: sqlite3.Connection):
    conn.execute("ALTER TABLE spotify_album_meta ADD COLUMN album_artists TEXT")


@migration(4, "spotify_album_meta_total_tracks_track_list")
def migrate_004(conn: sqlite3.Connection):
    conn.execute("ALTER TABLE spotify_album_meta ADD COLUMN total_tracks INTEGER")
    conn.execute("ALTER TABLE spotify_album_meta ADD COLUMN track_list TEXT")


@migration(5, "albums_image_url_path")
def migrate_005(conn: sqlite3.Connection):
    conn.execute("ALTER TABLE albums ADD COLUMN image_url TEXT")
    conn.execute("ALTER TABLE albums ADD COLUMN image_path TEXT")


@migration(6, "artists_image_url_path")
def migrate_006(conn: sqlite3.Connection):
    conn.execute("ALTER TABLE artists ADD COLUMN image_url TEXT")
    conn.execute("ALTER TABLE artists ADD COLUMN image_path TEXT")


@migration(7, "unique_index_tracks_artist_name")
def migrate_007(conn: sqlite3.Connection):
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_tracks_artist_name ON tracks(artist_id, track_name)"
    )


@migration(8, "unique_index_albums_name_artist")
def migrate_008(conn: sqlite3.Connection):
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_albums_name_artist ON albums(album_name, artist_id)"
    )


@migration(9, "index_plays_content_type")
def migrate_009(conn: sqlite3.Connection):
    conn.execute("CREATE INDEX IF NOT EXISTS idx_plays_content_type ON plays(content_type)")


@migration(10, "background_jobs_table")
def migrate_010(conn: sqlite3.Connection):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS background_jobs (
            job_id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            payload_json TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT,
            updated_at TEXT,
            attempts INTEGER DEFAULT 0,
            error TEXT
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bg_jobs_status ON background_jobs(status)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_bg_jobs_entity ON background_jobs(job_type, entity_id)"
    )


@migration(11, "track_artists_junction")
def migrate_011(conn: sqlite3.Connection):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS track_artists (
            track_id INTEGER NOT NULL REFERENCES tracks(track_id),
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
            role TEXT NOT NULL DEFAULT 'primary',
            UNIQUE(track_id, artist_id)
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_track_artists_track ON track_artists(track_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_track_artists_artist ON track_artists(artist_id)")


@migration(12, "track_artists_backfill_primary")
def migrate_012(conn: sqlite3.Connection):
    conn.execute(
        "INSERT OR IGNORE INTO track_artists (track_id, artist_id, role) "
        "SELECT track_id, artist_id, 'primary' FROM tracks"
    )


@migration(13, "plays_source_album_id")
def migrate_013(conn: sqlite3.Connection):
    conn.execute("ALTER TABLE plays ADD COLUMN source_album_id INTEGER REFERENCES albums(album_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_plays_source_album ON plays(source_album_id)")
    # Backfill: use tracks.album_id for historical data where track_id is not null
    conn.execute(
        "UPDATE plays SET source_album_id = ("
        "SELECT album_id FROM tracks WHERE tracks.track_id = plays.track_id"
        ") WHERE source_album_id IS NULL AND track_id IS NOT NULL"
    )


@migration(14, "release_groups_scope_parent")
def migrate_014(conn: sqlite3.Connection):
    """Rebuild release_groups with scope and parent_group_id columns.

    SQLite cannot alter UNIQUE constraints in place, so we rebuild the table.
    """
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS release_groups_new (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name TEXT NOT NULL,
            artist_id INTEGER REFERENCES artists(artist_id),
            primary_album_id INTEGER REFERENCES albums(album_id),
            scope TEXT NOT NULL DEFAULT 'release' CHECK(scope IN ('release', 'composition')),
            parent_group_id INTEGER REFERENCES release_groups_new(group_id),
            is_manual BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(canonical_name, artist_id, scope)
        )"""
    )
    conn.execute(
        """INSERT OR IGNORE INTO release_groups_new
           (group_id, canonical_name, artist_id, primary_album_id, scope, parent_group_id, is_manual, created_at)
           SELECT group_id, canonical_name, artist_id, primary_album_id, 'release', NULL, is_manual, created_at
           FROM release_groups"""
    )
    conn.execute("DROP TABLE release_groups")
    conn.execute("ALTER TABLE release_groups_new RENAME TO release_groups")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rg_artist ON release_groups(artist_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rg_scope ON release_groups(scope)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rg_parent ON release_groups(parent_group_id)")
    conn.execute("PRAGMA foreign_keys=ON")


@migration(15, "track_groups")
def migrate_015(conn: sqlite3.Connection):
    """Create track_groups and track_group_members tables for L1/L2/L3 merge."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS track_groups (
            group_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name    TEXT NOT NULL,
            primary_track_id  INTEGER REFERENCES tracks(track_id),
            scope             TEXT NOT NULL DEFAULT 'recording' CHECK(scope IN ('recording', 'composition')),
            parent_group_id   INTEGER REFERENCES track_groups(group_id),
            is_manual         INTEGER NOT NULL DEFAULT 0,
            created_at        TEXT DEFAULT (datetime('now')),
            UNIQUE(canonical_name, scope)
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS track_group_members (
            group_id   INTEGER REFERENCES track_groups(group_id),
            track_id   INTEGER REFERENCES tracks(track_id),
            UNIQUE(group_id, track_id)
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_track_groups_scope ON track_groups(scope)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_track_groups_parent ON track_groups(parent_group_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_track_group_members_track ON track_group_members(track_id)"
    )


@migration(16, "album_projects")
def migrate_016(conn: sqlite3.Connection):
    """Create album project tables for statistics-level album membership."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS album_projects (
            project_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name    TEXT NOT NULL,
            artist_id         INTEGER REFERENCES artists(artist_id),
            primary_album_id  INTEGER REFERENCES albums(album_id),
            release_date      TEXT,
            scope             TEXT NOT NULL DEFAULT 'release',
            project_type      TEXT NOT NULL DEFAULT 'album',
            include_in_charts INTEGER NOT NULL DEFAULT 1,
            is_manual         INTEGER NOT NULL DEFAULT 0,
            created_at        TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(canonical_name, artist_id, scope)
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS album_project_albums (
            project_id    INTEGER NOT NULL REFERENCES album_projects(project_id),
            album_id      INTEGER NOT NULL REFERENCES albums(album_id),
            role          TEXT NOT NULL DEFAULT 'member',
            source_bucket TEXT NOT NULL DEFAULT 'other',
            inferred      INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(project_id, album_id)
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS album_project_tracks (
            project_id       INTEGER NOT NULL REFERENCES album_projects(project_id),
            track_id         INTEGER NOT NULL REFERENCES tracks(track_id),
            membership_role  TEXT NOT NULL DEFAULT 'standard',
            min_merge_level  INTEGER NOT NULL DEFAULT 2,
            source_album_id  INTEGER REFERENCES albums(album_id),
            is_exclusive     INTEGER NOT NULL DEFAULT 0,
            inferred         INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(project_id, track_id, min_merge_level)
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_album_projects_artist ON album_projects(artist_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_album_projects_primary_album ON album_projects(primary_album_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_album_project_albums_album ON album_project_albums(album_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_album_project_tracks_track ON album_project_tracks(track_id)"
    )


@migration(17, "agg_weekly_track_sources")
def migrate_017(conn: sqlite3.Connection):
    """Create track-source weekly aggregation for album project charts."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS agg_weekly_track_sources (
            billboard_week TEXT NOT NULL,
            play_date TEXT NOT NULL,
            track_id INTEGER NOT NULL,
            source_album_id INTEGER NOT NULL DEFAULT 0,
            play_count INTEGER NOT NULL,
            total_ms INTEGER NOT NULL,
            PRIMARY KEY (billboard_week, play_date, track_id, source_album_id)
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_agg_wts_week ON agg_weekly_track_sources(billboard_week)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_agg_wts_track ON agg_weekly_track_sources(track_id)"
    )


@migration(18, "tracks_spotify_track_id")
def migrate_018(conn: sqlite3.Connection):
    """Add spotify_track_id column to tracks for index-friendly JOINs.

    The existing pattern REPLACE(t.spotify_track_uri, 'spotify:track:', '')
    prevents SQLite from using any index on the JOIN to spotify_track_meta.
    A dedicated column with an index allows direct indexed lookups.
    """
    conn.execute("ALTER TABLE tracks ADD COLUMN spotify_track_id TEXT")
    conn.execute(
        "UPDATE tracks SET spotify_track_id = "
        "REPLACE(spotify_track_uri, 'spotify:track:', '') "
        "WHERE spotify_track_uri IS NOT NULL AND spotify_track_id IS NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tracks_spotify_track_id ON tracks(spotify_track_id)"
    )


@migration(19, "spotify_meta_indexes")
def migrate_019(conn: sqlite3.Connection):
    """Add missing indexes on Spotify meta tables for frequent queries."""
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_spotify_track_meta_album "
        "ON spotify_track_meta(spotify_album_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_spotify_album_meta_name ON spotify_album_meta(album_name)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_spotify_artist_meta_name "
        "ON spotify_artist_meta(artist_name)"
    )


@migration(20, "saved_tracks_spotify_track_id")
def migrate_020(conn: sqlite3.Connection):
    """Add spotify_track_id column to saved_tracks, matching tracks table fix (migration 18).

    saved_tracks stores the full ``spotify:track:xxx`` URI as its primary key.
    JOINs with spotify_track_meta currently use
    ``REPLACE(st.track_uri, 'spotify:track:', '') = stm.spotify_track_id``,
    which prevents index usage on spotify_track_meta.spotify_track_id.

    This migration adds a dedicated column with an index so those JOINs can
    use direct indexed lookups.
    """
    conn.execute("ALTER TABLE saved_tracks ADD COLUMN spotify_track_id TEXT")
    conn.execute(
        "UPDATE saved_tracks SET spotify_track_id = "
        "REPLACE(track_uri, 'spotify:track:', '') "
        "WHERE track_uri IS NOT NULL AND spotify_track_id IS NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_saved_tracks_spotify_track_id "
        "ON saved_tracks(spotify_track_id)"
    )


@migration(21, "import_maintenance_play_spotify_ids")
def migrate_021(conn: sqlite3.Connection):
    """Persist play-time Spotify ids and local album to Spotify album evidence."""
    play_columns = {
        row["name"] if isinstance(row, sqlite3.Row) else row[1]
        for row in conn.execute("PRAGMA table_info(plays)").fetchall()
    }
    if "spotify_track_id_at_play" not in play_columns:
        conn.execute("ALTER TABLE plays ADD COLUMN spotify_track_id_at_play TEXT")
    if "spotify_album_id_at_play" not in play_columns:
        conn.execute("ALTER TABLE plays ADD COLUMN spotify_album_id_at_play TEXT")
    conn.execute(
        "UPDATE plays SET spotify_track_id_at_play = ("
        "SELECT tracks.spotify_track_id FROM tracks WHERE tracks.track_id = plays.track_id"
        ") WHERE spotify_track_id_at_play IS NULL AND track_id IS NOT NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_plays_spotify_track_at_play "
        "ON plays(spotify_track_id_at_play)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_plays_spotify_album_at_play "
        "ON plays(spotify_album_id_at_play)"
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS album_spotify_links (
            album_id INTEGER NOT NULL REFERENCES albums(album_id),
            spotify_album_id TEXT NOT NULL REFERENCES spotify_album_meta(spotify_album_id),
            evidence TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.0,
            play_count INTEGER NOT NULL DEFAULT 0,
            track_count INTEGER NOT NULL DEFAULT 0,
            first_seen TEXT,
            last_seen TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(album_id, spotify_album_id, evidence)
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_album_spotify_links_album ON album_spotify_links(album_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_album_spotify_links_spotify_album "
        "ON album_spotify_links(spotify_album_id)"
    )


@migration(22, "ai_task_runs_events_tool_calls")
def migrate_022(conn: sqlite3.Connection):
    """Persist AI task progress, event history, and read-only tool traces."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS ai_task_runs (
            task_id TEXT PRIMARY KEY,
            task_type TEXT NOT NULL,
            status TEXT NOT NULL,
            stage TEXT NOT NULL,
            progress_pct REAL NOT NULL DEFAULT 0,
            message TEXT NOT NULL DEFAULT '',
            request_json TEXT,
            result_json TEXT,
            error TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_task_runs_status ON ai_task_runs(status)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_task_runs_type_created "
        "ON ai_task_runs(task_type, created_at)"
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS ai_task_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL REFERENCES ai_task_runs(task_id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            stage TEXT NOT NULL,
            message TEXT NOT NULL DEFAULT '',
            payload_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_task_events_task ON ai_task_events(task_id, event_id)"
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS ai_tool_calls (
            tool_call_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL REFERENCES ai_task_runs(task_id) ON DELETE CASCADE,
            tool_name TEXT NOT NULL,
            status TEXT NOT NULL,
            params_summary TEXT NOT NULL DEFAULT '',
            result_summary TEXT NOT NULL DEFAULT '',
            source_range TEXT NOT NULL DEFAULT '',
            error TEXT,
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_tool_calls_task ON ai_tool_calls(task_id, tool_call_id)"
    )


@migration(23, "artist_genre_resolution")
def migrate_023(conn: sqlite3.Connection):
    """Persist local artist genre sources, overrides, and review queue."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS artist_genre_sources (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_name TEXT NOT NULL,
            spotify_artist_id TEXT,
            source TEXT NOT NULL,
            source_key TEXT NOT NULL,
            raw_genres_json TEXT,
            normalized_genres_json TEXT NOT NULL,
            primary_genre TEXT,
            language TEXT,
            region TEXT,
            confidence REAL NOT NULL DEFAULT 0.0,
            evidence_url TEXT,
            evidence_summary TEXT,
            status TEXT NOT NULL DEFAULT 'approved',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(artist_name, source, source_key)
        )"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_artist_genre_sources_artist "
        "ON artist_genre_sources(artist_name, status, confidence)"
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS artist_genre_overrides (
            artist_name TEXT PRIMARY KEY,
            normalized_genres_json TEXT NOT NULL,
            primary_genre TEXT,
            language TEXT,
            region TEXT,
            confidence REAL NOT NULL DEFAULT 1.0,
            note TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS artist_genre_review_queue (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_name TEXT NOT NULL,
            play_hours REAL NOT NULL DEFAULT 0,
            reason TEXT NOT NULL,
            suggested_source_id INTEGER REFERENCES artist_genre_sources(source_id),
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )


@migration(24, "artist_language_resolution")
def migrate_024(conn: sqlite3.Connection):
    """Persist artist language facts, evidence, and review decisions."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS artist_language_sources (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
            classification TEXT NOT NULL,
            primary_language_code TEXT,
            language_variant TEXT,
            raw_language TEXT,
            origin TEXT NOT NULL,
            source_key TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'suggested',
            replaces_source_id INTEGER REFERENCES artist_language_sources(source_id),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(artist_id, origin, source_key),
            CHECK (classification IN ('single_language', 'multilingual', 'instrumental')),
            CHECK (
                (classification = 'single_language' AND primary_language_code IS NOT NULL) OR
                (classification IN ('multilingual', 'instrumental') AND primary_language_code IS NULL)
            ),
            CHECK (classification = 'single_language' OR language_variant IS NULL),
            CHECK (origin IN ('manual', 'curated_seed', 'legacy_import')),
            CHECK (status IN ('suggested', 'approved', 'rejected', 'superseded')),
            CHECK (replaces_source_id IS NULL OR replaces_source_id != source_id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_artist_language_one_approved
            ON artist_language_sources(artist_id) WHERE status = 'approved';
        CREATE INDEX IF NOT EXISTS idx_artist_language_sources_artist
            ON artist_language_sources(artist_id, status);

        CREATE TABLE IF NOT EXISTS artist_language_evidence (
            evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL REFERENCES artist_language_sources(source_id),
            local_track_id INTEGER REFERENCES tracks(track_id),
            claimed_language_code TEXT,
            claimed_language_variant TEXT,
            evidence_kind TEXT NOT NULL,
            performer_attribution TEXT NOT NULL,
            evidence_url TEXT NOT NULL,
            evidence_title TEXT NOT NULL,
            evidence_accessed_at TEXT NOT NULL,
            evidence_summary TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            CHECK (evidence_kind IN (
                'artist_profile', 'artist_repertoire', 'editorial_source',
                'track_credit', 'track_language'
            )),
            CHECK (performer_attribution IN (
                'artist_vocal_confirmed', 'artist_instrumental_confirmed',
                'track_language_only', 'not_applicable'
            )),
            CHECK (claimed_language_variant IS NULL OR claimed_language_code IS NOT NULL),
            CHECK (evidence_url LIKE 'https://%'),
            CHECK (length(trim(evidence_title)) > 0),
            CHECK (length(trim(evidence_accessed_at)) > 0),
            CHECK (length(trim(evidence_summary)) > 0)
        );
        CREATE INDEX IF NOT EXISTS idx_artist_language_evidence_source
            ON artist_language_evidence(source_id, local_track_id);

        CREATE TABLE IF NOT EXISTS artist_language_review_queue (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
            suggested_source_id INTEGER REFERENCES artist_language_sources(source_id),
            play_hours_snapshot REAL NOT NULL DEFAULT 0,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            pre_review_recommendation TEXT,
            pre_review_confidence REAL,
            pre_review_note TEXT,
            pre_reviewed_by TEXT,
            pre_reviewed_at TEXT,
            resolution_note TEXT,
            reviewed_by TEXT,
            reviewed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            CHECK (play_hours_snapshot >= 0),
            CHECK (length(trim(reason)) > 0),
            CHECK (status IN ('open', 'approved', 'rejected', 'insufficient_evidence')),
            CHECK (
                status = 'open' OR (
                    reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL AND
                    resolution_note IS NOT NULL AND length(trim(reviewed_by)) > 0 AND
                    length(trim(reviewed_at)) > 0 AND length(trim(resolution_note)) > 0
                )
            ),
            CHECK (status NOT IN ('approved', 'rejected') OR suggested_source_id IS NOT NULL)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_artist_language_one_open_review
            ON artist_language_review_queue(artist_id) WHERE status = 'open';
        CREATE UNIQUE INDEX IF NOT EXISTS uq_artist_language_source_review
            ON artist_language_review_queue(suggested_source_id)
            WHERE suggested_source_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_artist_language_reviews_status
            ON artist_language_review_queue(status, play_hours_snapshot DESC);
        """
    )


@migration(25, "artist_genre_review_audit_fields")
def migrate_025(conn: sqlite3.Connection):
    """Add a minimal decision audit trail to the existing genre review queue."""
    columns = {
        row["name"] if isinstance(row, sqlite3.Row) else row[1]
        for row in conn.execute("PRAGMA table_info(artist_genre_review_queue)").fetchall()
    }
    additions = {
        "reviewed_by": "TEXT",
        "reviewed_at": "TEXT",
        "resolution_note": "TEXT",
    }
    for name, column_type in additions.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE artist_genre_review_queue ADD COLUMN {name} {column_type}")
    conn.execute(
        """UPDATE artist_genre_review_queue
           SET reviewed_by = COALESCE(reviewed_by, 'legacy_local_review'),
               reviewed_at = COALESCE(reviewed_at, updated_at),
               resolution_note = COALESCE(
                   resolution_note,
                   '迁移前完成的审核；原始结论说明未记录。'
               )
           WHERE status IN ('approved', 'rejected')"""
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_artist_genre_reviews_status_updated "
        "ON artist_genre_review_queue(status, updated_at DESC)"
    )


@migration(26, "artist_metadata_identity_overrides")
def migrate_026(conn: sqlite3.Connection):
    """Add narrow identity aliases and explicit invalid primary-artist attributions."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS artist_identity_aliases (
            alias_artist_id INTEGER PRIMARY KEY REFERENCES artists(artist_id),
            canonical_artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            CHECK (alias_artist_id != canonical_artist_id)
        );
        CREATE INDEX IF NOT EXISTS idx_artist_identity_aliases_canonical
            ON artist_identity_aliases(canonical_artist_id);

        CREATE TABLE IF NOT EXISTS artist_metadata_attribution_overrides (
            track_id INTEGER PRIMARY KEY REFERENCES tracks(track_id),
            artist_id INTEGER REFERENCES artists(artist_id),
            reason TEXT NOT NULL,
            evidence_url TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    alias_pairs = (
        ("JOLIN", "Jolin Tsai", "同一艺人的发行名称变体"),
        ("孫燕姿", "Stefanie Sun", "同一艺人的中英文名称变体"),
        ("鄧紫棋", "G.E.M.", "同一艺人的中英文名称变体"),
    )
    for alias_name, canonical_name, reason in alias_pairs:
        conn.execute(
            """INSERT OR IGNORE INTO artist_identity_aliases(
                   alias_artist_id, canonical_artist_id, reason
               )
               SELECT alias.artist_id, canonical.artist_id, ?
               FROM artists alias, artists canonical
               WHERE alias.artist_name=? AND canonical.artist_name=?
                 AND alias.artist_id != canonical.artist_id""",
            (reason, alias_name, canonical_name),
        )
    conn.execute(
        """INSERT OR IGNORE INTO artist_metadata_attribution_overrides(
               track_id, artist_id, reason, evidence_url
           )
           SELECT t.track_id, NULL,
                  'Wicked cast recording is attributed to the composer instead of the vocal performer',
                  'https://wickedthemusical.com/cast-creative'
           FROM tracks t
           JOIN artists a ON a.artist_id=t.artist_id
           WHERE a.artist_name='Stephen Schwartz'"""
    )


@migration(27, "metadata_pre_review_fields")
def migrate_027(conn: sqlite3.Connection):
    """Store non-terminal Codex recommendations separately from user decisions."""
    additions = {
        "pre_review_recommendation": "TEXT",
        "pre_review_confidence": "REAL",
        "pre_review_note": "TEXT",
        "pre_reviewed_by": "TEXT",
        "pre_reviewed_at": "TEXT",
    }
    for table in ("artist_genre_review_queue", "artist_language_review_queue"):
        columns = {
            row["name"] if isinstance(row, sqlite3.Row) else row[1]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for name, column_type in additions.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_artist_genre_pre_review "
        "ON artist_genre_review_queue(status, pre_review_recommendation, play_hours DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_artist_language_pre_review "
        "ON artist_language_review_queue(status, pre_review_recommendation, "
        "play_hours_snapshot DESC)"
    )


@migration(28, "artist_identity_management")
def migrate_028(conn: sqlite3.Connection):
    """Promote narrow artist aliases into auditable, reversible identity groups."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS artist_identity_groups (
            identity_id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
            display_artist_id INTEGER REFERENCES artists(artist_id),
            display_name TEXT NOT NULL,
            display_source TEXT NOT NULL DEFAULT 'canonical_artist',
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
            revision INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_artist_identity_groups_status
            ON artist_identity_groups(status, identity_id);

        CREATE TABLE IF NOT EXISTS artist_identity_members (
            membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
            identity_id INTEGER NOT NULL REFERENCES artist_identity_groups(identity_id),
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
            role TEXT NOT NULL DEFAULT 'alias' CHECK (role IN ('canonical', 'alias')),
            evidence_type TEXT NOT NULL DEFAULT 'legacy_alias',
            evidence_json TEXT NOT NULL DEFAULT '{}',
            confidence REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            removed_at TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_artist_identity_member_active
            ON artist_identity_members(artist_id) WHERE active = 1;
        CREATE INDEX IF NOT EXISTS idx_artist_identity_members_group
            ON artist_identity_members(identity_id, active);

        CREATE TABLE IF NOT EXISTS artist_identity_external_ids (
            link_id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
            provider TEXT NOT NULL,
            external_id TEXT NOT NULL,
            evidence_type TEXT NOT NULL,
            evidence_source TEXT,
            confidence REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
            verified INTEGER NOT NULL DEFAULT 0 CHECK (verified IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(artist_id, provider, external_id)
        );
        CREATE INDEX IF NOT EXISTS idx_artist_identity_external_lookup
            ON artist_identity_external_ids(provider, external_id);

        CREATE TABLE IF NOT EXISTS artist_identity_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            identity_id INTEGER REFERENCES artist_identity_groups(identity_id),
            action TEXT NOT NULL,
            before_json TEXT NOT NULL DEFAULT '{}',
            after_json TEXT NOT NULL DEFAULT '{}',
            actor TEXT NOT NULL,
            reason TEXT NOT NULL,
            revision INTEGER NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            undo_of_event_id INTEGER REFERENCES artist_identity_events(event_id),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_artist_identity_events_group
            ON artist_identity_events(identity_id, event_id DESC);

        CREATE TABLE IF NOT EXISTS artist_identity_state (
            state_id INTEGER PRIMARY KEY CHECK (state_id = 1),
            current_revision INTEGER NOT NULL DEFAULT 0,
            active_aggregate_revision INTEGER NOT NULL DEFAULT 0,
            rebuild_status TEXT NOT NULL DEFAULT 'ready'
                CHECK (rebuild_status IN ('ready', 'pending', 'running', 'failed')),
            last_error TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT OR IGNORE INTO artist_identity_state(
            state_id, current_revision, active_aggregate_revision, rebuild_status
        ) VALUES (1, 0, 0, 'ready');
        """
    )

    spotify_column = {row[1] for row in conn.execute("PRAGMA table_info(artists)").fetchall()}
    if "spotify_artist_id" in spotify_column:
        conn.execute(
            """INSERT OR IGNORE INTO artist_identity_external_ids(
                   artist_id, provider, external_id, evidence_type,
                   evidence_source, confidence, verified
               )
               SELECT artist_id, 'spotify', spotify_artist_id, 'artist_metadata',
                      'artists.spotify_artist_id', 1.0, 1
               FROM artists
               WHERE COALESCE(spotify_artist_id, '') != ''"""
        )

    canonical_rows = conn.execute(
        """SELECT DISTINCT canonical_artist_id
           FROM artist_identity_aliases
           ORDER BY canonical_artist_id"""
    ).fetchall()
    migrated = False
    for (canonical_artist_id,) in canonical_rows:
        canonical = conn.execute(
            "SELECT artist_name FROM artists WHERE artist_id=?", (canonical_artist_id,)
        ).fetchone()
        if canonical is None:
            continue
        existing = conn.execute(
            """SELECT identity_id FROM artist_identity_groups
               WHERE canonical_artist_id=? AND status='active'""",
            (canonical_artist_id,),
        ).fetchone()
        if existing:
            identity_id = int(existing[0])
        else:
            cursor = conn.execute(
                """INSERT INTO artist_identity_groups(
                       canonical_artist_id, display_artist_id, display_name,
                       display_source, revision
                   ) VALUES (?, ?, ?, 'canonical_artist', 1)""",
                (canonical_artist_id, canonical_artist_id, canonical[0]),
            )
            identity_id = int(cursor.lastrowid)
        conn.execute(
            """INSERT OR IGNORE INTO artist_identity_members(
                   identity_id, artist_id, role, evidence_type, evidence_json, confidence
               ) VALUES (?, ?, 'canonical', 'legacy_alias', '{}', 1.0)""",
            (identity_id, canonical_artist_id),
        )
        aliases = conn.execute(
            """SELECT alias_artist_id, reason FROM artist_identity_aliases
               WHERE canonical_artist_id=?""",
            (canonical_artist_id,),
        ).fetchall()
        for alias_artist_id, reason in aliases:
            conn.execute(
                """INSERT OR IGNORE INTO artist_identity_members(
                       identity_id, artist_id, role, evidence_type, evidence_json, confidence
                   ) VALUES (?, ?, 'alias', 'legacy_alias', json_object('reason', ?), 1.0)""",
                (identity_id, alias_artist_id, reason),
            )
        migrated = migrated or bool(aliases)
    if migrated:
        conn.execute(
            """UPDATE artist_identity_state
               SET current_revision=MAX(current_revision, 1),
                   active_aggregate_revision=0,
                   rebuild_status='pending', updated_at=datetime('now')
               WHERE state_id=1"""
        )


@migration(29, "artist_identity_provider_metadata_selection")
def migrate_029(conn: sqlite3.Connection):
    """Persist an explicit provider-metadata member for confirmed ID conflicts."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(artist_identity_groups)")}
    if "provider_metadata_artist_id" not in columns:
        conn.execute(
            "ALTER TABLE artist_identity_groups ADD COLUMN provider_metadata_artist_id INTEGER REFERENCES artists(artist_id)"
        )


@migration(30, "track_credit_metadata_management")
def migrate_030(conn: sqlite3.Connection):
    """Add an auditable overlay for effective track credits without rewriting raw facts."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS track_credit_overrides (
            override_id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id INTEGER NOT NULL REFERENCES tracks(track_id),
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
            action TEXT NOT NULL CHECK (action IN ('add', 'remove', 'set_role')),
            role TEXT CHECK (role IN ('primary', 'featured')),
            evidence_type TEXT NOT NULL DEFAULT 'user_confirmed',
            evidence_source TEXT,
            reason TEXT NOT NULL,
            actor TEXT NOT NULL DEFAULT 'local-user',
            revision INTEGER NOT NULL,
            active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
            supersedes_override_id INTEGER REFERENCES track_credit_overrides(override_id),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            deactivated_at TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_track_credit_override_active
            ON track_credit_overrides(track_id, artist_id) WHERE active = 1;
        CREATE INDEX IF NOT EXISTS idx_track_credit_overrides_track
            ON track_credit_overrides(track_id, active);

        CREATE TABLE IF NOT EXISTS track_credit_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id INTEGER NOT NULL REFERENCES tracks(track_id),
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
            action TEXT NOT NULL,
            before_json TEXT NOT NULL DEFAULT '{}',
            after_json TEXT NOT NULL DEFAULT '{}',
            actor TEXT NOT NULL,
            reason TEXT NOT NULL,
            revision INTEGER NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            undo_of_event_id INTEGER REFERENCES track_credit_events(event_id),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_track_credit_events_track
            ON track_credit_events(track_id, event_id DESC);

        CREATE TABLE IF NOT EXISTS track_credit_state (
            state_id INTEGER PRIMARY KEY CHECK (state_id = 1),
            current_revision INTEGER NOT NULL DEFAULT 0,
            active_aggregate_revision INTEGER NOT NULL DEFAULT 0,
            rebuild_status TEXT NOT NULL DEFAULT 'ready'
                CHECK (rebuild_status IN ('ready', 'pending', 'running', 'failed')),
            last_error TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT OR IGNORE INTO track_credit_state(
            state_id, current_revision, active_aggregate_revision, rebuild_status
        ) VALUES (1, 0, 0, 'ready');
        """
    )


@migration(31, "account_archive_provenance")
def migrate_031(conn: sqlite3.Connection):
    """Preserve collection-date provenance and revision account archive inputs."""
    saved_track_columns = {
        row["name"] if isinstance(row, sqlite3.Row) else row[1]
        for row in conn.execute("PRAGMA table_info(saved_tracks)").fetchall()
    }
    if "added_date_source" not in saved_track_columns:
        conn.execute(
            "ALTER TABLE saved_tracks ADD COLUMN added_date_source TEXT "
            "CHECK(added_date_source IN ('oauth', 'manual', 'legacy'))"
        )
    conn.execute(
        "UPDATE saved_tracks SET added_date_source = 'legacy' "
        "WHERE added_date IS NOT NULL AND TRIM(added_date) != '' "
        "AND added_date_source IS NULL"
    )
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS account_archive_state (
            state_id INTEGER PRIMARY KEY CHECK (state_id = 1),
            account_import_revision INTEGER NOT NULL DEFAULT 0,
            collection_date_revision INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT OR IGNORE INTO account_archive_state(
            state_id, account_import_revision, collection_date_revision
        ) VALUES (1, 0, 0);
        """
    )


@migration(32, "music_search_derived_index_and_context")
def migrate_032(conn: sqlite3.Connection):
    """Create rebuildable search documents and exact-context snapshot tables."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS music_search_index_state (
            state_id INTEGER PRIMARY KEY CHECK (state_id = 1),
            active_generation_id TEXT,
            previous_generation_id TEXT,
            status TEXT NOT NULL DEFAULT 'missing'
                CHECK (status IN ('missing', 'building', 'ready', 'degraded', 'failed')),
            tokenizer TEXT,
            normalization_version TEXT NOT NULL,
            source_revision TEXT,
            document_count INTEGER NOT NULL DEFAULT 0,
            built_at TEXT,
            last_error TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS music_search_documents (
            generation_id TEXT NOT NULL,
            entity_key TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('track', 'album', 'album_project', 'artist')),
            merge_level INTEGER NOT NULL DEFAULT 0 CHECK (merge_level BETWEEN 0 AND 3),
            label TEXT NOT NULL,
            normalized_label TEXT NOT NULL,
            secondary TEXT,
            normalized_secondary TEXT NOT NULL DEFAULT '',
            alias_text TEXT NOT NULL DEFAULT '',
            normalized_alias TEXT NOT NULL DEFAULT '',
            search_text TEXT NOT NULL,
            popularity_tiebreaker INTEGER NOT NULL DEFAULT 0,
            href TEXT NOT NULL,
            cover_url TEXT,
            track_id INTEGER,
            album_id INTEGER,
            album_project_id INTEGER,
            artist_id INTEGER,
            album_name TEXT,
            artist_name TEXT,
            PRIMARY KEY(generation_id, entity_key, merge_level)
        );
        CREATE INDEX IF NOT EXISTS idx_music_search_documents_generation_kind
            ON music_search_documents(
                generation_id, kind, merge_level, normalized_label, entity_key
            );
        CREATE INDEX IF NOT EXISTS idx_music_search_documents_generation_secondary
            ON music_search_documents(
                generation_id, kind, merge_level, normalized_secondary, entity_key
            );
        CREATE INDEX IF NOT EXISTS idx_music_search_documents_entity_key
            ON music_search_documents(entity_key, generation_id, merge_level);

        CREATE TABLE IF NOT EXISTS music_search_snapshot_meta (
            snapshot_key TEXT PRIMARY KEY,
            filter_fingerprint TEXT NOT NULL UNIQUE,
            source_revision TEXT NOT NULL,
            status TEXT NOT NULL
                CHECK (status IN ('pending', 'running', 'ready', 'failed', 'stale')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            activated_at TEXT,
            last_accessed_at TEXT,
            last_error TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_music_search_snapshot_meta_status
            ON music_search_snapshot_meta(status, activated_at DESC);

        CREATE TABLE IF NOT EXISTS music_search_entity_context (
            snapshot_key TEXT NOT NULL REFERENCES music_search_snapshot_meta(snapshot_key)
                ON DELETE CASCADE,
            entity_key TEXT NOT NULL,
            play_events INTEGER NOT NULL DEFAULT 0,
            total_ms INTEGER NOT NULL DEFAULT 0,
            peak_position INTEGER,
            peak_weeks INTEGER,
            weeks_on_chart INTEGER,
            weeks_at_no1 INTEGER,
            power_score INTEGER,
            power_rank INTEGER,
            first_week TEXT,
            latest_week TEXT,
            first_peak_week TEXT,
            PRIMARY KEY(snapshot_key, entity_key)
        );
        CREATE INDEX IF NOT EXISTS idx_music_search_context_entity
            ON music_search_entity_context(entity_key, snapshot_key);
        """
    )
    conn.execute(
        """INSERT OR IGNORE INTO music_search_index_state(
               state_id, normalization_version
           ) VALUES (1, 'nfkc_casefold_ws_punctuation_v1')"""
    )
    # FTS is an acceleration layer, not a migration prerequisite. A runtime
    # without FTS5/trigram remains usable through the bounded SQL fallback.
    try:
        conn.execute(
            """CREATE VIRTUAL TABLE IF NOT EXISTS music_search_documents_fts
               USING fts5(
                   generation_id UNINDEXED,
                   entity_key UNINDEXED,
                   merge_level UNINDEXED,
                   search_text,
                   tokenize='trigram'
               )"""
        )
    except sqlite3.OperationalError:
        conn.execute(
            """UPDATE music_search_index_state
               SET status='degraded', tokenizer='fallback', updated_at=datetime('now')
               WHERE state_id=1 AND active_generation_id IS NOT NULL"""
        )


@migration(33, "music_search_merge_level_documents")
def migrate_033(conn: sqlite3.Connection):
    """Invalidate the rebuildable v1 index and add per-level track documents."""
    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(music_search_documents)")}
    if "merge_level" in columns:
        return
    conn.execute("DROP TABLE IF EXISTS music_search_documents_fts")
    conn.execute("DROP TABLE IF EXISTS music_search_documents")
    conn.executescript(
        """
        CREATE TABLE music_search_documents (
            generation_id TEXT NOT NULL,
            entity_key TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('track', 'album', 'album_project', 'artist')),
            merge_level INTEGER NOT NULL DEFAULT 0 CHECK (merge_level BETWEEN 0 AND 3),
            label TEXT NOT NULL,
            normalized_label TEXT NOT NULL,
            secondary TEXT,
            normalized_secondary TEXT NOT NULL DEFAULT '',
            alias_text TEXT NOT NULL DEFAULT '',
            normalized_alias TEXT NOT NULL DEFAULT '',
            search_text TEXT NOT NULL,
            popularity_tiebreaker INTEGER NOT NULL DEFAULT 0,
            href TEXT NOT NULL,
            cover_url TEXT,
            track_id INTEGER,
            album_id INTEGER,
            album_project_id INTEGER,
            artist_id INTEGER,
            album_name TEXT,
            artist_name TEXT,
            PRIMARY KEY(generation_id, entity_key, merge_level)
        );
        CREATE INDEX idx_music_search_documents_generation_kind
            ON music_search_documents(
                generation_id, kind, merge_level, normalized_label, entity_key
            );
        CREATE INDEX idx_music_search_documents_generation_secondary
            ON music_search_documents(
                generation_id, kind, merge_level, normalized_secondary, entity_key
            );
        CREATE INDEX idx_music_search_documents_entity_key
            ON music_search_documents(entity_key, generation_id, merge_level);
        """
    )
    try:
        conn.execute(
            """CREATE VIRTUAL TABLE music_search_documents_fts
               USING fts5(
                   generation_id UNINDEXED,
                   entity_key UNINDEXED,
                   merge_level UNINDEXED,
                   search_text,
                   tokenize='trigram'
               )"""
        )
    except sqlite3.OperationalError:
        pass
    conn.execute(
        """UPDATE music_search_index_state
           SET active_generation_id=NULL, previous_generation_id=NULL,
               status='missing', source_revision=NULL, document_count=0,
               built_at=NULL, last_error=NULL, updated_at=datetime('now')
           WHERE state_id=1"""
    )
    conn.execute(
        """UPDATE music_search_snapshot_meta
           SET status='stale', last_error='search index schema upgraded'
           WHERE status IN ('ready', 'pending')"""
    )


@migration(34, "music_search_revision_state_and_snapshot_variants")
def migrate_034(conn: sqlite3.Connection):
    """Persist search revisions and make snapshot variants diagnosable.

    Existing snapshots were fingerprinted from table scans and did not encode
    their merge-level / dynamic-threshold variant explicitly.  They therefore
    cannot be proven compatible with the v2 reader and must fail closed until
    the six-variant snapshot set has been rebuilt.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS music_search_revision_state (
            state_id INTEGER PRIMARY KEY CHECK (state_id = 1),
            playback_revision INTEGER NOT NULL DEFAULT 0,
            billboard_revision INTEGER NOT NULL DEFAULT 0,
            metadata_revision INTEGER NOT NULL DEFAULT 0,
            settings_revision INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT OR IGNORE INTO music_search_revision_state(
            state_id, playback_revision, billboard_revision,
            metadata_revision, settings_revision
        ) VALUES (1, 0, 0, 0, 0);
        """
    )

    snapshot_columns = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(music_search_snapshot_meta)")
    }
    additions = (
        ("semantic_base_key", "TEXT"),
        ("merge_level", "INTEGER"),
        ("dynamic_threshold", "INTEGER"),
        ("builder_version", "TEXT"),
    )
    for column, column_type in additions:
        if column not in snapshot_columns:
            conn.execute(
                f"ALTER TABLE music_search_snapshot_meta ADD COLUMN {column} {column_type}"
            )

    conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_music_search_snapshot_meta_variant
           ON music_search_snapshot_meta(
               semantic_base_key, status, merge_level, dynamic_threshold
           )"""
    )
    conn.execute(
        """UPDATE music_search_snapshot_meta
           SET status='stale', last_error='music search snapshot schema upgraded'
           WHERE status IN ('ready', 'pending', 'running')
             AND (
                 semantic_base_key IS NULL
                 OR merge_level IS NULL
                 OR dynamic_threshold IS NULL
                 OR builder_version IS NULL
             )"""
    )


@migration(35, "music_search_candidate_statistics_identity_split")
def migrate_035(conn: sqlite3.Connection):
    """Version candidate documents independently from statistics snapshots.

    Generation ids remain an atomic-publication detail.  The deterministic
    candidate version is populated by the next index revalidation/rebuild;
    existing statistics rows are deliberately preserved for compatibility
    adoption by the maintenance path instead of being discarded here.
    """
    revision_columns = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(music_search_revision_state)")
    }
    if "candidate_revision" not in revision_columns:
        conn.execute(
            "ALTER TABLE music_search_revision_state "
            "ADD COLUMN candidate_revision INTEGER NOT NULL DEFAULT 0"
        )

    index_columns = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(music_search_index_state)")
    }
    if "candidate_index_version" not in index_columns:
        conn.execute("ALTER TABLE music_search_index_state ADD COLUMN candidate_index_version TEXT")
    if "content_digest" not in index_columns:
        conn.execute("ALTER TABLE music_search_index_state ADD COLUMN content_digest TEXT")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS music_search_document_ngrams (
            generation_id TEXT NOT NULL,
            entity_key TEXT NOT NULL,
            merge_level INTEGER NOT NULL,
            field TEXT NOT NULL CHECK (field IN ('label', 'secondary', 'alias')),
            ngram TEXT NOT NULL,
            PRIMARY KEY(generation_id, entity_key, merge_level, field, ngram)
        );
        CREATE INDEX IF NOT EXISTS idx_music_search_document_ngrams_lookup
            ON music_search_document_ngrams(
                generation_id, ngram, merge_level, entity_key, field
            );
        """
    )


@migration(36, "music_search_candidate_ngram_index")
def migrate_036(conn: sqlite3.Connection):
    """Ensure the bounded CJK/fuzzy candidate recall index exists."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS music_search_document_ngrams (
            generation_id TEXT NOT NULL,
            entity_key TEXT NOT NULL,
            merge_level INTEGER NOT NULL,
            field TEXT NOT NULL CHECK (field IN ('label', 'secondary', 'alias')),
            ngram TEXT NOT NULL,
            PRIMARY KEY(generation_id, entity_key, merge_level, field, ngram)
        );
        CREATE INDEX IF NOT EXISTS idx_music_search_document_ngrams_lookup
            ON music_search_document_ngrams(
                generation_id, ngram, merge_level, entity_key, field
            );
        """
    )
    # The previous candidate generation may predate the n-gram side index.
    # Invalidate only candidate identity so the next maintenance pass rebuilds
    # documents; statistics snapshots remain reusable by their own fingerprint.
    conn.execute(
        """UPDATE music_search_index_state
           SET candidate_index_version=NULL, content_digest=NULL,
               status=CASE WHEN status='ready' THEN 'missing' ELSE status END,
               updated_at=datetime('now')
           WHERE state_id=1"""
    )


# ── Runner ────────────────────────────────────────────────────────────────


def _ensure_migrations_table(conn: sqlite3.Connection):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""
    )


def _applied_versions(conn: sqlite3.Connection) -> set[int]:
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {r[0] for r in rows}


def run_migrations() -> None:
    """Apply any pending migrations in version order. Idempotent."""
    from backend.core import db as db_mod

    if not os.path.exists(db_mod.DB_PATH):
        return

    conn = db_mod.get_db(readonly=False)
    try:
        _ensure_migrations_table(conn)
        applied = _applied_versions(conn)

        sorted_migrations = sorted(MIGRATIONS, key=lambda m: m[0])
        for version, name, fn in sorted_migrations:
            if version in applied:
                continue
            try:
                fn(conn)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                    (version, name),
                )
                conn.commit()
                logger.info("Migration %d (%s) applied.", version, name)
            except sqlite3.OperationalError as e:
                message = str(e).lower()
                if not any(fragment in message for fragment in _IDEMPOTENT_OPERATIONAL_ERRORS):
                    raise
                # Column/index already exists — record as applied and continue
                logger.debug("Migration %d (%s) skipped: %s", version, name, e)
                conn.execute(
                    "INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (?, ?)",
                    (version, name),
                )
                conn.commit()
    finally:
        conn.close()
