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
LATEST_SCHEMA_VERSION = 65

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
    the four public L2/L3 snapshot variants have been rebuilt.
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


@migration(37, "playback_import_identity_baseline")
def migrate_037(conn: sqlite3.Connection):
    """Persist playback record identity and import-generation state.

    Legacy rows deliberately remain without fingerprints: the historical
    database does not retain every source JSON field needed to reproduce the
    canonical source fingerprint.  The next baseline import will populate the
    new columns instead.
    """
    play_columns = {
        row["name"] if isinstance(row, sqlite3.Row) else row[1]
        for row in conn.execute("PRAGMA table_info(plays)").fetchall()
    }
    additions = (
        ("source_fingerprint", "TEXT"),
        ("source_fingerprint_version", "INTEGER"),
        ("import_generation_id", "TEXT"),
    )
    for column, column_type in additions:
        if column not in play_columns:
            conn.execute(f"ALTER TABLE plays ADD COLUMN {column} {column_type}")

    conn.executescript(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_plays_source_fingerprint
            ON plays(content_type, source_fingerprint_version, source_fingerprint)
            WHERE source_fingerprint IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_plays_import_generation
            ON plays(import_generation_id);

        CREATE TABLE IF NOT EXISTS playback_import_state (
            state_id INTEGER PRIMARY KEY CHECK (state_id = 1),
            active_generation_id TEXT,
            account_identity_hash TEXT,
            fingerprint_version INTEGER,
            dataset_digest TEXT,
            record_count INTEGER NOT NULL DEFAULT 0 CHECK (record_count >= 0),
            first_ts TEXT,
            latest_ts TEXT,
            last_relation TEXT,
            last_strategy TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT OR IGNORE INTO playback_import_state(state_id, record_count)
            VALUES (1, 0);

        CREATE TABLE IF NOT EXISTS playback_import_runs (
            run_id TEXT PRIMARY KEY,
            requested_mode TEXT NOT NULL,
            detected_relation TEXT,
            status TEXT NOT NULL,
            incoming_digest TEXT,
            previous_digest TEXT,
            incoming_count INTEGER NOT NULL DEFAULT 0 CHECK (incoming_count >= 0),
            unchanged_count INTEGER NOT NULL DEFAULT 0 CHECK (unchanged_count >= 0),
            added_count INTEGER NOT NULL DEFAULT 0 CHECK (added_count >= 0),
            removed_count INTEGER NOT NULL DEFAULT 0 CHECK (removed_count >= 0),
            first_ts TEXT,
            latest_ts TEXT,
            earliest_changed_ts TEXT,
            latest_changed_ts TEXT,
            plan_json TEXT,
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT,
            error_code TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_playback_import_runs_status_started
            ON playback_import_runs(status, started_at DESC);
        """
    )


@migration(38, "playback_import_change_set_scope")
def migrate_038(conn: sqlite3.Connection):
    """Persist compact downstream impact scope for completed imports."""
    columns = {
        row["name"] if isinstance(row, sqlite3.Row) else row[1]
        for row in conn.execute("PRAGMA table_info(playback_import_runs)").fetchall()
    }
    if "change_set_json" not in columns:
        conn.execute("ALTER TABLE playback_import_runs ADD COLUMN change_set_json TEXT")


@migration(39, "cover_cache_source_state")
def migrate_039(conn: sqlite3.Connection):
    """Track the CDN source represented by each local cover file."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS cover_cache_state (
            entity_type TEXT NOT NULL CHECK (entity_type IN ('albums', 'artists')),
            entity_id INTEGER NOT NULL,
            source_url_hash TEXT NOT NULL,
            cached_source_url_hash TEXT,
            status TEXT NOT NULL CHECK (status IN ('pending', 'ready', 'failed')),
            last_error TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY(entity_type, entity_id)
        );
        CREATE INDEX IF NOT EXISTS idx_cover_cache_state_status
            ON cover_cache_state(status, updated_at);
        """
    )


@migration(40, "playback_year_partition_state")
def migrate_040(conn: sqlite3.Connection):
    """Persist exact annual and prefix digests for scoped yearly caches."""
    state_columns = {
        row["name"] if isinstance(row, sqlite3.Row) else row[1]
        for row in conn.execute("PRAGMA table_info(playback_import_state)").fetchall()
    }
    if "playback_revision" not in state_columns:
        conn.execute(
            "ALTER TABLE playback_import_state "
            "ADD COLUMN playback_revision INTEGER NOT NULL DEFAULT 0"
        )
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS playback_year_partition_state (
            report_year INTEGER PRIMARY KEY,
            direct_digest TEXT NOT NULL,
            prefix_digest TEXT NOT NULL,
            digest_version TEXT NOT NULL DEFAULT 'year-prefix-v2',
            impact_revision INTEGER NOT NULL DEFAULT 0,
            record_count INTEGER NOT NULL CHECK (record_count >= 0),
            first_ts TEXT,
            latest_ts TEXT,
            source_generation_id TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    partition_columns = {
        row["name"] if isinstance(row, sqlite3.Row) else row[1]
        for row in conn.execute("PRAGMA table_info(playback_year_partition_state)").fetchall()
    }
    if "digest_version" not in partition_columns:
        conn.execute(
            "ALTER TABLE playback_year_partition_state "
            "ADD COLUMN digest_version TEXT NOT NULL DEFAULT 'year-prefix-v2'"
        )
    if "impact_revision" not in partition_columns:
        conn.execute(
            "ALTER TABLE playback_year_partition_state "
            "ADD COLUMN impact_revision INTEGER NOT NULL DEFAULT 0"
        )


@migration(41, "playback_year_partition_digest_v2")
def migrate_041(conn: sqlite3.Connection):
    """Upgrade databases that applied the first Phase C partition schema."""
    columns = {
        row["name"] if isinstance(row, sqlite3.Row) else row[1]
        for row in conn.execute("PRAGMA table_info(playback_year_partition_state)").fetchall()
    }
    if not columns:
        migrate_040(conn)
        return
    upgraded = False
    if "digest_version" not in columns:
        conn.execute(
            "ALTER TABLE playback_year_partition_state "
            "ADD COLUMN digest_version TEXT NOT NULL DEFAULT 'year-prefix-v2'"
        )
        upgraded = True
    if "impact_revision" not in columns:
        conn.execute(
            "ALTER TABLE playback_year_partition_state "
            "ADD COLUMN impact_revision INTEGER NOT NULL DEFAULT 0"
        )
        upgraded = True
    if upgraded:
        # V1 prefix rows do not carry logical-impact revisions and cannot be
        # relabelled as V2. An empty state fails safely to the global database
        # revision and bootstraps exact prefixes on the next import.
        conn.execute("DELETE FROM playback_year_partition_state")


@migration(42, "music_search_incremental_snapshot_lineage")
def migrate_042(conn: sqlite3.Connection):
    """Persist the proof and compact weekly ledger required by snapshot delta.

    Existing snapshots remain readable.  Their nullable lineage fields and
    absent weekly rows make them ineligible as incremental bases without
    forcing a cold rebuild during migration.
    """
    snapshot_columns = {
        row["name"] if isinstance(row, sqlite3.Row) else row[1]
        for row in conn.execute("PRAGMA table_info(music_search_snapshot_meta)").fetchall()
    }
    additions = (
        ("policy_key", "TEXT"),
        ("source_generation_id", "TEXT"),
        ("source_dataset_digest", "TEXT"),
        (
            "base_snapshot_key",
            "TEXT REFERENCES music_search_snapshot_meta(snapshot_key) ON DELETE SET NULL",
        ),
        ("build_strategy", "TEXT"),
        ("dependency_digest", "TEXT"),
        ("change_set_digest", "TEXT"),
    )
    for column, column_type in additions:
        if column not in snapshot_columns:
            conn.execute(
                f"ALTER TABLE music_search_snapshot_meta ADD COLUMN {column} {column_type}"
            )

    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_music_search_snapshot_meta_lineage
            ON music_search_snapshot_meta(
                policy_key, dependency_digest, status, activated_at DESC
            );
        CREATE INDEX IF NOT EXISTS idx_music_search_snapshot_meta_base
            ON music_search_snapshot_meta(base_snapshot_key);

        CREATE TABLE IF NOT EXISTS music_search_weekly_chart_context (
            snapshot_key TEXT NOT NULL REFERENCES music_search_snapshot_meta(snapshot_key)
                ON DELETE CASCADE,
            family TEXT NOT NULL CHECK (family IN ('track', 'album', 'artist')),
            week TEXT NOT NULL,
            entity_key TEXT NOT NULL,
            rank INTEGER NOT NULL CHECK (rank > 0),
            play_count INTEGER NOT NULL CHECK (play_count >= 0),
            total_ms INTEGER NOT NULL CHECK (total_ms >= 0),
            stable_sort_key TEXT NOT NULL,
            PRIMARY KEY(snapshot_key, family, week, entity_key),
            UNIQUE(snapshot_key, family, week, rank)
        );
        CREATE INDEX IF NOT EXISTS idx_music_search_weekly_chart_context_entity
            ON music_search_weekly_chart_context(
                snapshot_key, family, entity_key, week
            );
        """
    )


@migration(43, "track_group_automatic_identity")
def migrate_043(conn: sqlite3.Connection):
    """Give automatic recording groups a provider identity independent of names.

    The original ``UNIQUE(canonical_name, scope)`` constraint made two Spotify
    recordings with the same display name compete for one row, even when their
    artists differed.  Rebuild the table so manual groups retain their
    name/scope uniqueness while automatic groups are keyed by
    ``(scope, spotify_track_id, artist_id)``.
    """
    columns = {
        row["name"] if isinstance(row, sqlite3.Row) else row[1]
        for row in conn.execute("PRAGMA table_info(track_groups)").fetchall()
    }
    if {"automatic_spotify_track_id", "automatic_artist_id"} <= columns:
        conn.executescript(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_track_groups_manual_name_scope
                ON track_groups(canonical_name, scope)
                WHERE is_manual = 1;
            CREATE UNIQUE INDEX IF NOT EXISTS idx_track_groups_automatic_identity
                ON track_groups(scope, automatic_spotify_track_id, automatic_artist_id)
                WHERE is_manual = 0
                  AND automatic_spotify_track_id IS NOT NULL
                  AND automatic_artist_id IS NOT NULL;
            """
        )
        return

    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("DROP TABLE IF EXISTS track_groups_new")
        conn.execute(
            """CREATE TABLE track_groups_new (
                group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_name TEXT NOT NULL,
                primary_track_id INTEGER REFERENCES tracks(track_id),
                scope TEXT NOT NULL DEFAULT 'recording'
                    CHECK(scope IN ('recording', 'composition')),
                parent_group_id INTEGER REFERENCES track_groups(group_id),
                is_manual INTEGER NOT NULL DEFAULT 0,
                automatic_spotify_track_id TEXT,
                automatic_artist_id INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                CHECK(
                    is_manual = 1
                    OR (automatic_spotify_track_id IS NULL) =
                       (automatic_artist_id IS NULL)
                )
            )"""
        )
        conn.execute(
            """INSERT INTO track_groups_new (
                   group_id, canonical_name, primary_track_id, scope,
                   parent_group_id, is_manual, automatic_spotify_track_id,
                   automatic_artist_id, created_at
               )
               SELECT
                   tg.group_id,
                   tg.canonical_name,
                   tg.primary_track_id,
                   tg.scope,
                   tg.parent_group_id,
                   tg.is_manual,
                   CASE WHEN tg.is_manual=0 AND tg.scope='recording'
                        THEN NULLIF(t.spotify_track_id, '') END,
                   CASE WHEN tg.is_manual=0 AND tg.scope='recording'
                                  AND NULLIF(t.spotify_track_id, '') IS NOT NULL
                        THEN t.artist_id END,
                   tg.created_at
               FROM track_groups tg
               LEFT JOIN tracks t ON t.track_id=tg.primary_track_id"""
        )

        duplicate_identities = conn.execute(
            """SELECT automatic_spotify_track_id, automatic_artist_id,
                      MIN(group_id) AS owner_id
               FROM track_groups_new
               WHERE is_manual=0 AND scope='recording'
                 AND automatic_spotify_track_id IS NOT NULL
                 AND automatic_artist_id IS NOT NULL
               GROUP BY automatic_spotify_track_id, automatic_artist_id
               HAVING COUNT(*) > 1"""
        ).fetchall()
        for spotify_track_id, artist_id, owner_id in duplicate_identities:
            duplicate_ids = [
                int(row[0])
                for row in conn.execute(
                    """SELECT group_id FROM track_groups_new
                       WHERE is_manual=0 AND scope='recording'
                         AND automatic_spotify_track_id=?
                         AND automatic_artist_id=? AND group_id<>?""",
                    (spotify_track_id, artist_id, owner_id),
                ).fetchall()
            ]
            for duplicate_id in duplicate_ids:
                conn.execute(
                    """INSERT OR IGNORE INTO track_group_members(group_id, track_id)
                       SELECT ?, track_id FROM track_group_members WHERE group_id=?""",
                    (owner_id, duplicate_id),
                )
                conn.execute("DELETE FROM track_group_members WHERE group_id=?", (duplicate_id,))
                conn.execute(
                    "UPDATE track_groups_new SET parent_group_id=? WHERE parent_group_id=?",
                    (owner_id, duplicate_id),
                )
                conn.execute("DELETE FROM track_groups_new WHERE group_id=?", (duplicate_id,))

        conn.execute("DROP TABLE track_groups")
        conn.execute("ALTER TABLE track_groups_new RENAME TO track_groups")
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_track_groups_scope
                ON track_groups(scope);
            CREATE INDEX IF NOT EXISTS idx_track_groups_parent
                ON track_groups(parent_group_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_track_groups_manual_name_scope
                ON track_groups(canonical_name, scope)
                WHERE is_manual = 1;
            CREATE UNIQUE INDEX IF NOT EXISTS idx_track_groups_automatic_identity
                ON track_groups(scope, automatic_spotify_track_id, automatic_artist_id)
                WHERE is_manual = 0
                  AND automatic_spotify_track_id IS NOT NULL
                  AND automatic_artist_id IS NOT NULL;
            """
        )
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


@migration(44, "track_group_parent_fk_repair")
def migrate_044(conn: sqlite3.Connection):
    """Repair the self-reference produced by the first v43 table rebuild.

    A short-lived v43 implementation declared the temporary table's parent FK
    against ``track_groups_new``.  SQLite preserved that literal target after
    rename.  Databases created from the corrected schema are already valid;
    this migration is a no-op for them and repairs only the malformed target.
    """
    foreign_keys = conn.execute("PRAGMA foreign_key_list(track_groups)").fetchall()
    parent_targets = {str(row[2]) for row in foreign_keys if str(row[3]) == "parent_group_id"}
    if parent_targets == {"track_groups"}:
        return

    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("DROP TABLE IF EXISTS track_groups_repaired")
        conn.execute(
            """CREATE TABLE track_groups_repaired (
                group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_name TEXT NOT NULL,
                primary_track_id INTEGER REFERENCES tracks(track_id),
                scope TEXT NOT NULL DEFAULT 'recording'
                    CHECK(scope IN ('recording', 'composition')),
                parent_group_id INTEGER REFERENCES track_groups(group_id),
                is_manual INTEGER NOT NULL DEFAULT 0,
                automatic_spotify_track_id TEXT,
                automatic_artist_id INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                CHECK(
                    is_manual = 1
                    OR (automatic_spotify_track_id IS NULL) =
                       (automatic_artist_id IS NULL)
                )
            )"""
        )
        conn.execute(
            """INSERT INTO track_groups_repaired (
                   group_id, canonical_name, primary_track_id, scope,
                   parent_group_id, is_manual, automatic_spotify_track_id,
                   automatic_artist_id, created_at
               )
               SELECT group_id, canonical_name, primary_track_id, scope,
                      parent_group_id, is_manual, automatic_spotify_track_id,
                      automatic_artist_id, created_at
               FROM track_groups"""
        )
        conn.execute("DROP TABLE track_groups")
        conn.execute("ALTER TABLE track_groups_repaired RENAME TO track_groups")
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_track_groups_scope
                ON track_groups(scope);
            CREATE INDEX IF NOT EXISTS idx_track_groups_parent
                ON track_groups(parent_group_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_track_groups_manual_name_scope
                ON track_groups(canonical_name, scope)
                WHERE is_manual = 1;
            CREATE UNIQUE INDEX IF NOT EXISTS idx_track_groups_automatic_identity
                ON track_groups(scope, automatic_spotify_track_id, automatic_artist_id)
                WHERE is_manual = 0
                  AND automatic_spotify_track_id IS NOT NULL
                  AND automatic_artist_id IS NOT NULL;
            """
        )
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


@migration(45, "track_group_automatic_artist_fk_repair")
def migrate_045(conn: sqlite3.Connection):
    """Remove the overly strict FK from the automatic artist identity column.

    Historical track rows may preserve a provider artist id that is not present
    in the local ``artists`` dimension.  The id remains part of the stable
    automatic identity, but must not create a new referential-integrity failure.
    """
    foreign_keys = conn.execute("PRAGMA foreign_key_list(track_groups)").fetchall()
    if not any(str(row[3]) == "automatic_artist_id" for row in foreign_keys):
        return

    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("DROP TABLE IF EXISTS track_groups_artist_repaired")
        conn.execute(
            """CREATE TABLE track_groups_artist_repaired (
                group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_name TEXT NOT NULL,
                primary_track_id INTEGER REFERENCES tracks(track_id),
                scope TEXT NOT NULL DEFAULT 'recording'
                    CHECK(scope IN ('recording', 'composition')),
                parent_group_id INTEGER REFERENCES track_groups(group_id),
                is_manual INTEGER NOT NULL DEFAULT 0,
                automatic_spotify_track_id TEXT,
                automatic_artist_id INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                CHECK(
                    is_manual = 1
                    OR (automatic_spotify_track_id IS NULL) =
                       (automatic_artist_id IS NULL)
                )
            )"""
        )
        conn.execute(
            """INSERT INTO track_groups_artist_repaired (
                   group_id, canonical_name, primary_track_id, scope,
                   parent_group_id, is_manual, automatic_spotify_track_id,
                   automatic_artist_id, created_at
               )
               SELECT group_id, canonical_name, primary_track_id, scope,
                      parent_group_id, is_manual, automatic_spotify_track_id,
                      automatic_artist_id, created_at
               FROM track_groups"""
        )
        conn.execute("DROP TABLE track_groups")
        conn.execute("ALTER TABLE track_groups_artist_repaired RENAME TO track_groups")
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_track_groups_scope
                ON track_groups(scope);
            CREATE INDEX IF NOT EXISTS idx_track_groups_parent
                ON track_groups(parent_group_id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_track_groups_manual_name_scope
                ON track_groups(canonical_name, scope)
                WHERE is_manual = 1;
            CREATE UNIQUE INDEX IF NOT EXISTS idx_track_groups_automatic_identity
                ON track_groups(scope, automatic_spotify_track_id, automatic_artist_id)
                WHERE is_manual = 0
                  AND automatic_spotify_track_id IS NOT NULL
                  AND automatic_artist_id IS NOT NULL;
            """
        )
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


@migration(46, "music_search_year_end_projection")
def migrate_046(conn: sqlite3.Connection):
    """Persist lightweight Year-End facts alongside exact search snapshots.

    The projection has an independent lifecycle: an existing search snapshot
    remains readable while its annual rows are absent, warming, or failed.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS music_search_year_end_projection_state (
            snapshot_key TEXT PRIMARY KEY
                REFERENCES music_search_snapshot_meta(snapshot_key) ON DELETE CASCADE,
            builder_version TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'ready', 'failed')),
            built_at TEXT,
            last_error TEXT
        );

        CREATE TABLE IF NOT EXISTS music_search_year_end_meta (
            snapshot_key TEXT NOT NULL
                REFERENCES music_search_snapshot_meta(snapshot_key) ON DELETE CASCADE,
            year INTEGER NOT NULL CHECK (year >= 1900 AND year <= 9999),
            coverage_status TEXT NOT NULL
                CHECK (coverage_status IN (
                    'complete', 'incomplete', 'partial_start',
                    'year_to_date', 'partial_range', 'empty'
                )),
            is_complete_year INTEGER NOT NULL CHECK (is_complete_year IN (0, 1)),
            observed_weeks INTEGER NOT NULL CHECK (observed_weeks >= 0),
            expected_weeks INTEGER NOT NULL CHECK (expected_weeks >= 0),
            first_billboard_week TEXT,
            last_billboard_week TEXT,
            PRIMARY KEY(snapshot_key, year)
        );

        CREATE TABLE IF NOT EXISTS music_search_entity_year_end (
            snapshot_key TEXT NOT NULL,
            family TEXT NOT NULL CHECK (family IN ('track', 'album', 'artist')),
            entity_key TEXT NOT NULL,
            year INTEGER NOT NULL,
            year_end_rank INTEGER NOT NULL CHECK (year_end_rank > 0),
            year_end_score INTEGER NOT NULL CHECK (year_end_score >= 0),
            peak_position INTEGER NOT NULL CHECK (peak_position > 0),
            weeks_on_chart INTEGER NOT NULL CHECK (weeks_on_chart > 0),
            weeks_at_peak INTEGER NOT NULL CHECK (weeks_at_peak > 0),
            weeks_at_no1 INTEGER NOT NULL CHECK (weeks_at_no1 >= 0),
            weeks_top5 INTEGER NOT NULL CHECK (weeks_top5 >= 0),
            weeks_top10 INTEGER NOT NULL CHECK (weeks_top10 >= 0),
            chart_plays INTEGER NOT NULL CHECK (chart_plays > 0),
            first_week TEXT,
            last_week TEXT,
            PRIMARY KEY(snapshot_key, family, entity_key, year),
            FOREIGN KEY(snapshot_key, year)
                REFERENCES music_search_year_end_meta(snapshot_key, year) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_music_search_entity_year_end_lookup
            ON music_search_entity_year_end(snapshot_key, family, entity_key, year DESC);
        """
    )


@migration(47, "music_search_year_end_coverage_constraint_repair")
def migrate_047(conn: sqlite3.Connection):
    """Repair the short-lived v46 coverage CHECK on already-migrated databases."""
    row = conn.execute(
        """SELECT sql FROM sqlite_master
           WHERE type='table' AND name='music_search_year_end_meta'"""
    ).fetchone()
    if row is None or "partial_start" in str(row[0] or ""):
        return

    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("DROP TABLE IF EXISTS music_search_year_end_meta_v47")
        conn.execute(
            """CREATE TABLE music_search_year_end_meta_v47 (
                snapshot_key TEXT NOT NULL
                    REFERENCES music_search_snapshot_meta(snapshot_key) ON DELETE CASCADE,
                year INTEGER NOT NULL CHECK (year >= 1900 AND year <= 9999),
                coverage_status TEXT NOT NULL
                    CHECK (coverage_status IN (
                        'complete', 'incomplete', 'partial_start',
                        'year_to_date', 'partial_range', 'empty'
                    )),
                is_complete_year INTEGER NOT NULL CHECK (is_complete_year IN (0, 1)),
                observed_weeks INTEGER NOT NULL CHECK (observed_weeks >= 0),
                expected_weeks INTEGER NOT NULL CHECK (expected_weeks >= 0),
                first_billboard_week TEXT,
                last_billboard_week TEXT,
                PRIMARY KEY(snapshot_key, year)
            )"""
        )
        conn.execute(
            """INSERT INTO music_search_year_end_meta_v47(
                   snapshot_key, year, coverage_status, is_complete_year,
                   observed_weeks, expected_weeks,
                   first_billboard_week, last_billboard_week
               )
               SELECT snapshot_key, year,
                      CASE WHEN coverage_status='partial'
                           THEN 'partial_range' ELSE coverage_status END,
                      is_complete_year, observed_weeks, expected_weeks,
                      first_billboard_week, last_billboard_week
               FROM music_search_year_end_meta"""
        )
        conn.execute("DROP TABLE music_search_year_end_meta")
        conn.execute(
            "ALTER TABLE music_search_year_end_meta_v47 RENAME TO music_search_year_end_meta"
        )
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


@migration(48, "canonical_track_identity")
def migrate_048(conn: sqlite3.Connection):
    """Create and backfill local canonical track identities.

    Historical ``track_id`` values are import dimension rows and can be both
    split across one Spotify id and shared by several play-time Spotify ids.
    A provider id gets one deterministic local owner, while the schema allows
    several verified provider ids to belong to the same local identity.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS track_l1_identities (
            l1_id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            provider                TEXT NOT NULL DEFAULT 'local',
            external_track_id       TEXT,
            fallback_track_id       INTEGER REFERENCES tracks(track_id),
            identity_status         TEXT NOT NULL DEFAULT 'active'
                                    CHECK(identity_status IN ('active', 'unresolved', 'superseded')),
            representative_track_id INTEGER REFERENCES tracks(track_id),
            created_at              TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at              TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_track_l1_local_identity
            ON track_l1_identities(fallback_track_id)
            WHERE fallback_track_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_track_l1_representative
            ON track_l1_identities(representative_track_id);

        CREATE TABLE IF NOT EXISTS track_l1_external_ids (
            provider          TEXT NOT NULL,
            external_track_id TEXT NOT NULL,
            l1_id             INTEGER NOT NULL REFERENCES track_l1_identities(l1_id),
            evidence_type     TEXT NOT NULL DEFAULT 'provider_observed'
                              CHECK(evidence_type IN (
                                  'provider_observed', 'provider_relink',
                                  'manual_confirmed', 'migration'
                              )),
            is_primary        INTEGER NOT NULL DEFAULT 0 CHECK(is_primary IN (0, 1)),
            first_seen_at     TEXT,
            last_seen_at      TEXT,
            created_at        TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY(provider, external_track_id)
        );
        CREATE INDEX IF NOT EXISTS idx_track_l1_external_owner
            ON track_l1_external_ids(l1_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_track_l1_primary_external
            ON track_l1_external_ids(l1_id, provider)
            WHERE is_primary=1;

        CREATE TABLE IF NOT EXISTS track_l1_source_links (
            l1_id          INTEGER NOT NULL REFERENCES track_l1_identities(l1_id),
            track_id       INTEGER NOT NULL REFERENCES tracks(track_id),
            evidence_type  TEXT NOT NULL
                           CHECK(evidence_type IN ('play_at_time', 'track_projection', 'manual')),
            observed_plays INTEGER NOT NULL DEFAULT 0 CHECK(observed_plays >= 0),
            first_seen_at  TEXT,
            last_seen_at   TEXT,
            PRIMARY KEY(l1_id, track_id, evidence_type)
        );
        CREATE INDEX IF NOT EXISTS idx_track_l1_source_track
            ON track_l1_source_links(track_id);

        CREATE TABLE IF NOT EXISTS track_identity_events (
            event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            action          TEXT NOT NULL
                            CHECK(action IN ('merge', 'split', 'attach_external_id')),
            survivor_l1_id  INTEGER REFERENCES track_l1_identities(l1_id),
            affected_l1_ids TEXT NOT NULL DEFAULT '[]',
            before_json     TEXT NOT NULL DEFAULT '{}',
            after_json      TEXT NOT NULL DEFAULT '{}',
            reason          TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_track_identity_events_survivor
            ON track_identity_events(survivor_l1_id, event_id);

        CREATE TABLE IF NOT EXISTS track_identity_state (
            state_id         INTEGER PRIMARY KEY CHECK(state_id = 1),
            current_revision INTEGER NOT NULL DEFAULT 0,
            policy_version   TEXT NOT NULL DEFAULT 'canonical_track_v2',
            updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT OR IGNORE INTO track_identity_state(
            state_id, current_revision, policy_version
        ) VALUES (1, 0, 'canonical_track_v2');

        CREATE TEMP TABLE _spotify_identity_seed AS
        SELECT spotify_track_id,
               MIN(representative_track_id) AS representative_track_id,
               (SELECT COALESCE(MAX(l1_id), 0) FROM track_l1_identities)
                   + ROW_NUMBER() OVER (ORDER BY spotify_track_id) AS l1_id
          FROM (
                SELECT spotify_track_id_at_play AS spotify_track_id,
                       MIN(track_id) AS representative_track_id
                  FROM plays
                 WHERE spotify_track_id_at_play IS NOT NULL
                   AND spotify_track_id_at_play != ''
                 GROUP BY spotify_track_id_at_play
                UNION ALL
                SELECT spotify_track_id, MIN(track_id)
                  FROM tracks
                 WHERE spotify_track_id IS NOT NULL AND spotify_track_id != ''
                 GROUP BY spotify_track_id
               )
         GROUP BY spotify_track_id;

        INSERT INTO track_l1_identities(
            l1_id, provider, external_track_id,
            identity_status, representative_track_id
        )
        SELECT l1_id, 'spotify', spotify_track_id,
               'active', representative_track_id
          FROM _spotify_identity_seed
         ORDER BY spotify_track_id;

        INSERT INTO track_l1_external_ids(
            provider, external_track_id, l1_id, evidence_type, is_primary
        )
        SELECT 'spotify', seed.spotify_track_id, seed.l1_id,
               'migration', 1
          FROM _spotify_identity_seed seed
         WHERE NOT EXISTS (
               SELECT 1 FROM track_l1_external_ids existing
                WHERE existing.provider='spotify'
                  AND existing.external_track_id=seed.spotify_track_id
         );
        DROP TABLE _spotify_identity_seed;

        INSERT OR IGNORE INTO track_l1_identities(
            provider, fallback_track_id, identity_status,
            representative_track_id
        )
        SELECT 'local', t.track_id, 'unresolved', t.track_id
          FROM tracks t
         WHERE (t.spotify_track_id IS NULL OR t.spotify_track_id = '')
           AND (
                EXISTS (SELECT 1 FROM plays p WHERE p.track_id=t.track_id)
                OR EXISTS (
                    SELECT 1 FROM track_group_members tgm
                     WHERE tgm.track_id=t.track_id
                )
           );

        INSERT OR REPLACE INTO track_l1_source_links(
            l1_id, track_id, evidence_type, observed_plays,
            first_seen_at, last_seen_at
        )
        SELECT li.l1_id, p.track_id, 'play_at_time', COUNT(*), MIN(p.ts), MAX(p.ts)
          FROM plays p
          JOIN track_l1_external_ids external
            ON external.provider='spotify'
           AND external.external_track_id=p.spotify_track_id_at_play
          JOIN track_l1_identities li ON li.l1_id=external.l1_id
         WHERE p.track_id IS NOT NULL
           AND p.spotify_track_id_at_play IS NOT NULL
           AND p.spotify_track_id_at_play != ''
         GROUP BY li.l1_id, p.track_id;

        INSERT OR IGNORE INTO track_l1_source_links(
            l1_id, track_id, evidence_type, observed_plays
        )
        SELECT li.l1_id, t.track_id, 'track_projection', 0
          FROM tracks t
          JOIN track_l1_external_ids external
            ON external.provider='spotify'
           AND external.external_track_id=t.spotify_track_id
          JOIN track_l1_identities li ON li.l1_id=external.l1_id
         WHERE t.spotify_track_id IS NOT NULL AND t.spotify_track_id != '';

        INSERT OR IGNORE INTO track_l1_source_links(
            l1_id, track_id, evidence_type, observed_plays
        )
        SELECT li.l1_id, li.fallback_track_id, 'track_projection', 0
          FROM track_l1_identities li
         WHERE li.fallback_track_id IS NOT NULL;
        """
    )

    spotify_rows = conn.execute(
        """SELECT identities.l1_id, external.external_track_id
             FROM track_l1_identities identities
             JOIN track_l1_external_ids external ON external.l1_id=identities.l1_id
            WHERE external.provider='spotify'
              AND identities.representative_track_id IS NULL"""
    ).fetchall()
    for l1_id, spotify_track_id in spotify_rows:
        representative = conn.execute(
            """SELECT links.track_id
                 FROM (
                       SELECT track_id, observed_plays
                         FROM track_l1_source_links
                        WHERE l1_id=? AND evidence_type='play_at_time'
                       UNION ALL
                       SELECT track_id, 0
                         FROM track_l1_source_links
                        WHERE l1_id=? AND evidence_type='track_projection'
                      ) links
                 JOIN tracks t ON t.track_id=links.track_id
                 LEFT JOIN artists a ON a.artist_id=t.artist_id
                GROUP BY links.track_id
                ORDER BY MAX(links.observed_plays) DESC,
                         CASE WHEN a.artist_id IS NULL THEN 1 ELSE 0 END,
                         links.track_id
                LIMIT 1""",
            (l1_id, l1_id),
        ).fetchone()
        if representative is not None:
            conn.execute(
                """UPDATE track_l1_identities
                      SET representative_track_id=?, updated_at=datetime('now')
                    WHERE l1_id=?""",
                (int(representative[0]), int(l1_id)),
            )

    conn.execute(
        """UPDATE track_identity_state
              SET current_revision=CASE WHEN current_revision < 1 THEN 1
                                        ELSE current_revision END,
                  policy_version='canonical_track_v2',
                  updated_at=datetime('now')
            WHERE state_id=1"""
    )


@migration(49, "remove_track_name_artist_uniqueness")
def migrate_049(conn: sqlite3.Connection):
    """Allow distinct Spotify L1 rows to share the same title and artist.

    The former index encoded mutable metadata as identity and forced different
    Spotify ids into one local ``track_id``. Fresh databases no longer declare
    the equivalent inline UNIQUE constraint in ``SCHEMA``.
    """
    conn.execute("DROP INDEX IF EXISTS idx_tracks_artist_name")


@migration(50, "billboard_track_l1_grain")
def migrate_050(conn: sqlite3.Connection):
    """Invalidate legacy track aggregates and make L1 their unique grain."""
    conn.executescript(
        """
        DROP TABLE IF EXISTS agg_weekly_tracks_l1_new;
        CREATE TABLE agg_weekly_tracks_l1_new (
            billboard_week TEXT NOT NULL,
            l1_id INTEGER NOT NULL REFERENCES track_l1_identities(l1_id),
            track_id INTEGER NOT NULL REFERENCES tracks(track_id),
            play_count INTEGER NOT NULL,
            total_ms INTEGER NOT NULL,
            PRIMARY KEY (billboard_week, l1_id)
        );
        DROP TABLE agg_weekly_tracks;
        ALTER TABLE agg_weekly_tracks_l1_new RENAME TO agg_weekly_tracks;
        CREATE INDEX idx_agg_wt_week ON agg_weekly_tracks(billboard_week);
        CREATE INDEX idx_agg_wt_track ON agg_weekly_tracks(track_id);

        DROP TABLE IF EXISTS agg_weekly_track_sources_l1_new;
        CREATE TABLE agg_weekly_track_sources_l1_new (
            billboard_week TEXT NOT NULL,
            play_date TEXT NOT NULL,
            l1_id INTEGER NOT NULL REFERENCES track_l1_identities(l1_id),
            track_id INTEGER NOT NULL REFERENCES tracks(track_id),
            source_album_id INTEGER NOT NULL DEFAULT 0,
            play_count INTEGER NOT NULL,
            total_ms INTEGER NOT NULL,
            PRIMARY KEY (billboard_week, play_date, l1_id, source_album_id)
        );
        DROP TABLE agg_weekly_track_sources;
        ALTER TABLE agg_weekly_track_sources_l1_new RENAME TO agg_weekly_track_sources;
        CREATE INDEX idx_agg_wts_week ON agg_weekly_track_sources(billboard_week);
        CREATE INDEX idx_agg_wts_track ON agg_weekly_track_sources(track_id);
        CREATE INDEX idx_agg_wts_l1 ON agg_weekly_track_sources(l1_id);

        DELETE FROM agg_weekly_albums;
        DELETE FROM agg_weekly_artists;
        DELETE FROM agg_config;
        """
    )


@migration(51, "track_groups_l1_membership")
def migrate_051(conn: sqlite3.Connection):
    """Move L2/L3 membership from historical track rows to L1 identities."""
    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(track_groups)")}
    if "primary_l1_id" not in columns:
        conn.execute(
            "ALTER TABLE track_groups ADD COLUMN primary_l1_id INTEGER REFERENCES track_l1_identities(l1_id)"
        )
    if "group_status" not in columns:
        conn.execute(
            "ALTER TABLE track_groups ADD COLUMN group_status TEXT NOT NULL DEFAULT 'active' "
            "CHECK(group_status IN ('active', 'archived', 'conflict'))"
        )
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS track_group_l1_members (
            group_id INTEGER NOT NULL REFERENCES track_groups(group_id),
            l1_id INTEGER NOT NULL REFERENCES track_l1_identities(l1_id),
            PRIMARY KEY(group_id, l1_id)
        );
        CREATE INDEX IF NOT EXISTS idx_track_group_l1_member
            ON track_group_l1_members(l1_id);

        CREATE TABLE IF NOT EXISTS track_group_migration_audit (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            distinct_l1_count INTEGER NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS track_group_candidates (
            candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL CHECK(scope IN ('recording', 'composition')),
            original_l1_id INTEGER NOT NULL REFERENCES track_l1_identities(l1_id),
            candidate_l1_id INTEGER NOT NULL REFERENCES track_l1_identities(l1_id),
            confidence REAL,
            evidence_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending', 'accepted', 'rejected')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            CHECK(original_l1_id != candidate_l1_id),
            UNIQUE(scope, original_l1_id, candidate_l1_id)
        );

        DELETE FROM track_group_l1_members;
        INSERT OR IGNORE INTO track_group_l1_members(group_id, l1_id)
        SELECT tgm.group_id, links.l1_id
          FROM track_group_members tgm
          JOIN track_l1_source_links links ON links.track_id=tgm.track_id;
        """
    )

    groups = conn.execute(
        "SELECT group_id, scope, is_manual, primary_track_id FROM track_groups ORDER BY group_id"
    ).fetchall()
    for group_id, scope, is_manual, primary_track_id in groups:
        l1_rows = conn.execute(
            "SELECT l1_id FROM track_group_l1_members WHERE group_id=? ORDER BY l1_id",
            (int(group_id),),
        ).fetchall()
        l1_ids = [int(row[0]) for row in l1_rows]
        if len(l1_ids) <= 1:
            conn.execute(
                "UPDATE track_groups SET group_status='archived', primary_l1_id=? WHERE group_id=?",
                (l1_ids[0] if l1_ids else None, int(group_id)),
            )
            action = "collapsed_same_l1" if l1_ids else "no_resolved_l1"
        else:
            primary = None
            if primary_track_id is not None:
                row = conn.execute(
                    """SELECT links.l1_id
                         FROM track_l1_source_links links
                         JOIN track_group_l1_members members
                           ON members.group_id=? AND members.l1_id=links.l1_id
                        WHERE links.track_id=?
                        ORDER BY links.observed_plays DESC, links.l1_id
                        LIMIT 1""",
                    (int(group_id), int(primary_track_id)),
                ).fetchone()
                primary = int(row[0]) if row is not None else None
            primary = primary or l1_ids[0]
            if int(is_manual):
                conn.execute(
                    "UPDATE track_groups SET group_status='active', primary_l1_id=? WHERE group_id=?",
                    (primary, int(group_id)),
                )
                action = "migrated_cross_l1_manual"
            else:
                # Legacy automatic groups were committed under the invalid
                # track-row identity model. Preserve them as review candidates,
                # never as accepted L2/L3 facts.
                conn.execute(
                    "UPDATE track_groups SET group_status='archived', primary_l1_id=? WHERE group_id=?",
                    (primary, int(group_id)),
                )
                for candidate in l1_ids:
                    if candidate == primary:
                        continue
                    original_l1_id, candidate_l1_id = sorted((primary, candidate))
                    conn.execute(
                        """INSERT OR IGNORE INTO track_group_candidates(
                               scope, original_l1_id, candidate_l1_id,
                               evidence_json, status
                           ) VALUES (?, ?, ?, ?, 'pending')""",
                        (
                            str(scope),
                            original_l1_id,
                            candidate_l1_id,
                            f'{{"source":"legacy_auto_group","group_id":{int(group_id)}}}',
                        ),
                    )
                action = "archived_auto_candidate"
        conn.execute(
            """INSERT INTO track_group_migration_audit(
                   group_id, action, distinct_l1_count, details
               ) VALUES (?, ?, ?, ?)""",
            (int(group_id), action, len(l1_ids), f"scope={scope}"),
        )

    # One L1 may not belong to multiple active groups at the same scope. Keep
    # manual groups first, then the oldest deterministic group; quarantine the rest.
    conflicts = conn.execute(
        """SELECT members.l1_id, groups.scope
             FROM track_group_l1_members members
             JOIN track_groups groups ON groups.group_id=members.group_id
            WHERE groups.group_status='active'
            GROUP BY members.l1_id, groups.scope
           HAVING COUNT(*) > 1"""
    ).fetchall()
    for l1_id, scope in conflicts:
        memberships = conn.execute(
            """SELECT groups.group_id
                 FROM track_groups groups
                 JOIN track_group_l1_members members ON members.group_id=groups.group_id
                WHERE members.l1_id=? AND groups.scope=? AND groups.group_status='active'
                ORDER BY groups.is_manual DESC, groups.group_id""",
            (int(l1_id), str(scope)),
        ).fetchall()
        for (group_id,) in memberships[1:]:
            conn.execute(
                "UPDATE track_groups SET group_status='conflict' WHERE group_id=?",
                (int(group_id),),
            )
            count = conn.execute(
                "SELECT COUNT(*) FROM track_group_l1_members WHERE group_id=?",
                (int(group_id),),
            ).fetchone()[0]
            conn.execute(
                """INSERT INTO track_group_migration_audit(
                       group_id, action, distinct_l1_count, details
                   ) VALUES (?, 'quarantined_overlap', ?, ?)""",
                (int(group_id), int(count), f"l1_id={int(l1_id)};scope={scope}"),
            )


@migration(52, "archive_post_v51_automatic_cross_l1_groups")
def migrate_052(conn: sqlite3.Connection):
    """Repair databases migrated by the short-lived permissive v51.

    Automatic groups inferred from raw track rows are not accepted L2/L3
    facts once L1 is provider identity.  Preserve their evidence as pending
    candidates and archive the accepted relation.  Manual groups remain active.
    """
    groups = conn.execute(
        """SELECT groups.group_id, groups.scope, groups.primary_l1_id
             FROM track_groups groups
             JOIN track_group_l1_members members ON members.group_id=groups.group_id
            WHERE groups.group_status='active' AND groups.is_manual=0
            GROUP BY groups.group_id
           HAVING COUNT(DISTINCT members.l1_id)>1
            ORDER BY groups.group_id"""
    ).fetchall()
    for group_id, scope, primary_l1_id in groups:
        l1_ids = [
            int(row[0])
            for row in conn.execute(
                "SELECT l1_id FROM track_group_l1_members WHERE group_id=? ORDER BY l1_id",
                (int(group_id),),
            ).fetchall()
        ]
        primary = int(primary_l1_id) if primary_l1_id in l1_ids else l1_ids[0]
        conn.execute(
            "UPDATE track_groups SET group_status='archived', primary_l1_id=? WHERE group_id=?",
            (primary, int(group_id)),
        )
        for candidate in l1_ids:
            if candidate == primary:
                continue
            original_l1_id, candidate_l1_id = sorted((primary, candidate))
            conn.execute(
                """INSERT OR IGNORE INTO track_group_candidates(
                       scope, original_l1_id, candidate_l1_id,
                       evidence_json, status
                   ) VALUES (?, ?, ?, ?, 'pending')""",
                (
                    str(scope),
                    original_l1_id,
                    candidate_l1_id,
                    f'{{"source":"post_v51_auto_group_repair","group_id":{int(group_id)}}}',
                ),
            )
        conn.execute(
            """INSERT INTO track_group_migration_audit(
                   group_id, action, distinct_l1_count, details
               ) VALUES (?, 'post_v51_archived_auto_candidate', ?, ?)""",
            (int(group_id), len(l1_ids), f"scope={scope}"),
        )
    if (
        groups
        and conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='music_search_revision_state'"
        ).fetchone()
    ):
        conn.execute(
            """UPDATE music_search_revision_state
                  SET metadata_revision=metadata_revision+1,
                      candidate_revision=candidate_revision+1,
                      updated_at=datetime('now')
                WHERE state_id=1"""
        )


@migration(53, "canonical_track_external_ownership")
def migrate_053(conn: sqlite3.Connection):
    """Upgrade the short-lived provider-per-L1 model to local ownership.

    Development databases may already contain migrations 48-52 from the
    earlier implementation. Keep their stable ids, materialise the authoritative
    provider ownership table, and stop reading the legacy scalar columns.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS track_l1_external_ids (
            provider          TEXT NOT NULL,
            external_track_id TEXT NOT NULL,
            l1_id             INTEGER NOT NULL REFERENCES track_l1_identities(l1_id),
            evidence_type     TEXT NOT NULL DEFAULT 'provider_observed'
                              CHECK(evidence_type IN (
                                  'provider_observed', 'provider_relink',
                                  'manual_confirmed', 'migration'
                              )),
            is_primary        INTEGER NOT NULL DEFAULT 0 CHECK(is_primary IN (0, 1)),
            first_seen_at     TEXT,
            last_seen_at      TEXT,
            created_at        TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY(provider, external_track_id)
        );
        CREATE INDEX IF NOT EXISTS idx_track_l1_external_owner
            ON track_l1_external_ids(l1_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_track_l1_primary_external
            ON track_l1_external_ids(l1_id, provider)
            WHERE is_primary=1;

        CREATE TABLE IF NOT EXISTS track_identity_events (
            event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            action          TEXT NOT NULL
                            CHECK(action IN ('merge', 'split', 'attach_external_id')),
            survivor_l1_id  INTEGER REFERENCES track_l1_identities(l1_id),
            affected_l1_ids TEXT NOT NULL DEFAULT '[]',
            before_json     TEXT NOT NULL DEFAULT '{}',
            after_json      TEXT NOT NULL DEFAULT '{}',
            reason          TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_track_identity_events_survivor
            ON track_identity_events(survivor_l1_id, event_id);
        """
    )
    identity_columns = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(track_l1_identities)")
    }
    if {"provider", "external_track_id"}.issubset(identity_columns):
        conn.execute(
            """INSERT OR IGNORE INTO track_l1_external_ids(
                   provider, external_track_id, l1_id, evidence_type, is_primary
               )
               SELECT provider, external_track_id, l1_id, 'migration', 1
                 FROM track_l1_identities
                WHERE provider!='local'
                  AND external_track_id IS NOT NULL
                  AND external_track_id!=''"""
        )
    conn.execute(
        """UPDATE track_identity_state
              SET current_revision=current_revision+1,
                  policy_version='canonical_track_v2',
                  updated_at=datetime('now')
            WHERE state_id=1"""
    )


@migration(54, "canonical_track_group_invariants")
def migrate_054(conn: sqlite3.Connection):
    """Enforce one active L2/L3 group per canonical member and scope."""
    conn.execute(
        """DELETE FROM track_group_candidates
            WHERE candidate_id NOT IN (
                SELECT MIN(candidate_id)
                  FROM track_group_candidates
                 GROUP BY scope,
                          MIN(original_l1_id, candidate_l1_id),
                          MAX(original_l1_id, candidate_l1_id)
            )"""
    )

    overlaps = conn.execute(
        """SELECT members.l1_id, groups.scope
             FROM track_group_l1_members members
             JOIN track_groups groups ON groups.group_id=members.group_id
            WHERE groups.group_status='active'
            GROUP BY members.l1_id, groups.scope
           HAVING COUNT(DISTINCT groups.group_id)>1"""
    ).fetchall()
    for l1_id, scope in overlaps:
        groups = conn.execute(
            """SELECT groups.group_id
                 FROM track_groups groups
                 JOIN track_group_l1_members members ON members.group_id=groups.group_id
                WHERE members.l1_id=? AND groups.scope=?
                  AND groups.group_status='active'
                ORDER BY groups.is_manual DESC, groups.group_id""",
            (int(l1_id), str(scope)),
        ).fetchall()
        for (group_id,) in groups[1:]:
            conn.execute(
                "UPDATE track_groups SET group_status='conflict' WHERE group_id=?",
                (int(group_id),),
            )
            if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='track_group_migration_audit'"
            ).fetchone():
                member_count = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM track_group_l1_members WHERE group_id=?",
                        (int(group_id),),
                    ).fetchone()[0]
                )
                conn.execute(
                    """INSERT INTO track_group_migration_audit(
                           group_id, action, distinct_l1_count, details
                       ) VALUES (?, 'v54_quarantined_overlap', ?, ?)""",
                    (
                        int(group_id),
                        member_count,
                        f"canonical_track_id={int(l1_id)};scope={scope}",
                    ),
                )
    conn.executescript(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_track_group_candidate_unordered_pair
            ON track_group_candidates(
                scope,
                MIN(original_l1_id, candidate_l1_id),
                MAX(original_l1_id, candidate_l1_id)
            );

        CREATE TRIGGER IF NOT EXISTS trg_track_group_l1_single_active_scope_insert
        BEFORE INSERT ON track_group_l1_members
        WHEN EXISTS (
            SELECT 1 FROM track_groups incoming
             WHERE incoming.group_id=NEW.group_id AND incoming.group_status='active'
        ) AND EXISTS (
            SELECT 1
              FROM track_group_l1_members existing
              JOIN track_groups existing_group ON existing_group.group_id=existing.group_id
              JOIN track_groups incoming ON incoming.group_id=NEW.group_id
             WHERE existing.l1_id=NEW.l1_id
               AND existing.group_id!=NEW.group_id
               AND existing_group.group_status='active'
               AND existing_group.scope=incoming.scope
        )
        BEGIN
            SELECT RAISE(ABORT, 'canonical track already belongs to an active group at this scope');
        END;

        CREATE TRIGGER IF NOT EXISTS trg_track_group_single_active_scope_update
        BEFORE UPDATE OF group_status, scope ON track_groups
        WHEN NEW.group_status='active' AND EXISTS (
            SELECT 1
              FROM track_group_l1_members incoming_member
              JOIN track_group_l1_members existing_member
                ON existing_member.l1_id=incoming_member.l1_id
               AND existing_member.group_id!=incoming_member.group_id
              JOIN track_groups existing_group
                ON existing_group.group_id=existing_member.group_id
             WHERE incoming_member.group_id=NEW.group_id
               AND existing_group.group_status='active'
               AND existing_group.scope=NEW.scope
        )
        BEGIN
            SELECT RAISE(ABORT, 'activating group would overlap another active group at this scope');
        END;
        """
    )


@migration(55, "retire_public_l1_search_snapshots")
def migrate_055(conn: sqlite3.Connection):
    """Keep legacy evidence but prevent retired L1 snapshots from appearing ready."""
    conn.execute(
        """UPDATE music_search_snapshot_meta
              SET status='stale', last_error='retired public search snapshot'
            WHERE status IN ('pending', 'running', 'ready')
              AND (
                  merge_level=1
                  OR COALESCE(builder_version, '')!='music_search_snapshot_v8_canonical_track'
              )"""
    )


@migration(56, "repair_canonical_aggregate_readiness")
def migrate_056(conn: sqlite3.Connection):
    """Invalidate derivatives when the canonical aggregate publish is incomplete.

    Artist/credit revision state describes whether the current mapping is baked
    into any published artist aggregate; it is not the general four-table
    readiness flag. General readiness is represented by ``agg_config`` and
    raw-path fallback, so this migration must not turn metadata dependencies
    pending and deadlock the maintenance queue.
    """
    has_plays = int(conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0]) > 0
    aggregate_tables = (
        "agg_weekly_tracks",
        "agg_weekly_track_sources",
        "agg_weekly_albums",
        "agg_weekly_artists",
    )
    aggregate_missing = has_plays and any(
        int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]) == 0
        for table in aggregate_tables
    )
    if not aggregate_missing:
        return

    conn.execute("DELETE FROM agg_config")
    conn.execute(
        """UPDATE music_search_snapshot_meta
              SET status='stale', last_error='canonical aggregate rebuild required'
            WHERE status IN ('pending', 'running', 'ready')"""
    )


@migration(57, "spotify_track_owner_track_id_restore")
def migrate_057(conn: sqlite3.Connection):
    """Restore the existing track_id as the only application track identity.

    Migrations 48-56 briefly introduced one synthetic identity per Spotify id.
    That split historical track rows which intentionally owned several Spotify
    ids (for example album editions of the same recording).  Keep the old L1
    tables only as an internal compatibility projection where ``l1_id`` is
    exactly ``tracks.track_id`` and make provider ownership directional.

    Raw plays, tracks and credits are never rewritten by this migration.
    """
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS spotify_track_owners (
                spotify_track_id TEXT PRIMARY KEY,
                track_id         INTEGER NOT NULL REFERENCES tracks(track_id),
                evidence_type    TEXT NOT NULL DEFAULT 'import_match'
                                 CHECK(evidence_type IN (
                                     'import_match', 'play_majority',
                                     'catalog_projection', 'manual_override'
                                 )),
                first_seen_at    TEXT,
                last_seen_at     TEXT,
                created_at       TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_spotify_track_owners_track
                ON spotify_track_owners(track_id);

            DROP TABLE IF EXISTS _spotify_owner_candidates_v57;
            CREATE TEMP TABLE _spotify_owner_candidates_v57 AS
            WITH candidates AS (
                SELECT p.spotify_track_id_at_play AS spotify_track_id,
                       p.track_id,
                       COUNT(*) AS play_count,
                       MIN(p.ts) AS first_seen_at,
                       MAX(p.ts) AS last_seen_at,
                       MAX(CASE WHEN t.artist_id IS NOT NULL
                                     AND COALESCE(TRIM(a.artist_name), '') != ''
                                THEN 1 ELSE 0 END) AS has_artist,
                       MAX(CASE WHEN t.album_id IS NOT NULL OR p.source_album_id IS NOT NULL
                                THEN 1 ELSE 0 END) AS has_album
                  FROM plays p
                  JOIN tracks t ON t.track_id=p.track_id
                  LEFT JOIN artists a ON a.artist_id=t.artist_id
                 WHERE p.spotify_track_id_at_play IS NOT NULL
                   AND p.spotify_track_id_at_play != ''
                 GROUP BY p.spotify_track_id_at_play, p.track_id
                UNION ALL
                SELECT t.spotify_track_id, t.track_id, 0, NULL, NULL,
                       CASE WHEN t.artist_id IS NOT NULL
                                  AND COALESCE(TRIM(a.artist_name), '') != ''
                            THEN 1 ELSE 0 END,
                       CASE WHEN t.album_id IS NOT NULL THEN 1 ELSE 0 END
                  FROM tracks t
                  LEFT JOIN artists a ON a.artist_id=t.artist_id
                 WHERE t.spotify_track_id IS NOT NULL
                   AND t.spotify_track_id != ''
            ), combined AS (
                SELECT spotify_track_id, track_id,
                       SUM(play_count) AS play_count,
                       MIN(first_seen_at) AS first_seen_at,
                       MAX(last_seen_at) AS last_seen_at,
                       MAX(has_artist) AS has_artist,
                       MAX(has_album) AS has_album
                  FROM candidates
                 GROUP BY spotify_track_id, track_id
            )
            SELECT spotify_track_id, track_id, play_count,
                   first_seen_at, last_seen_at, has_artist, has_album,
                   ROW_NUMBER() OVER (
                       PARTITION BY spotify_track_id
                       ORDER BY CASE WHEN play_count > 0 THEN 0 ELSE 1 END,
                                play_count DESC,
                                has_artist DESC,
                                has_album DESC,
                                track_id
                   ) AS owner_rank
              FROM combined;

            INSERT INTO spotify_track_owners(
                spotify_track_id, track_id, evidence_type,
                first_seen_at, last_seen_at
            )
            SELECT spotify_track_id, track_id,
                   CASE WHEN play_count > 0
                        THEN 'play_majority' ELSE 'catalog_projection' END,
                   first_seen_at, last_seen_at
              FROM _spotify_owner_candidates_v57
             WHERE owner_rank=1
            ON CONFLICT(spotify_track_id) DO NOTHING;

            DROP TABLE IF EXISTS _old_l1_to_track_v57;
            CREATE TEMP TABLE _old_l1_to_track_v57 AS
            SELECT l1_id,
                   COALESCE(representative_track_id, fallback_track_id) AS track_id
              FROM track_l1_identities;

            DROP TABLE IF EXISTS _track_candidates_v57;
            CREATE TEMP TABLE _track_candidates_v57 AS
            SELECT c.scope,
                   left_map.track_id AS original_track_id,
                   right_map.track_id AS candidate_track_id,
                   MAX(c.confidence) AS confidence,
                   MIN(c.evidence_json) AS evidence_json,
                   CASE MIN(CASE c.status
                                  WHEN 'accepted' THEN 0
                                  WHEN 'pending' THEN 1 ELSE 2 END)
                        WHEN 0 THEN 'accepted'
                        WHEN 1 THEN 'pending' ELSE 'rejected' END AS status,
                   MIN(c.created_at) AS created_at
              FROM track_group_candidates c
              JOIN _old_l1_to_track_v57 left_map
                ON left_map.l1_id=c.original_l1_id
              JOIN _old_l1_to_track_v57 right_map
                ON right_map.l1_id=c.candidate_l1_id
             WHERE left_map.track_id IS NOT NULL
               AND right_map.track_id IS NOT NULL
               AND left_map.track_id != right_map.track_id
             GROUP BY c.scope,
                      MIN(left_map.track_id, right_map.track_id),
                      MAX(left_map.track_id, right_map.track_id);

            UPDATE track_identity_events
               SET survivor_l1_id=(
                   SELECT track_id FROM _old_l1_to_track_v57 old
                    WHERE old.l1_id=track_identity_events.survivor_l1_id
               )
             WHERE survivor_l1_id IS NOT NULL;

            DELETE FROM agg_weekly_tracks;
            DELETE FROM agg_weekly_track_sources;
            DELETE FROM agg_weekly_albums;
            DELETE FROM agg_weekly_artists;
            DELETE FROM agg_config;
            DELETE FROM track_group_candidates;
            DELETE FROM track_group_l1_members;
            DELETE FROM track_l1_source_links;
            DELETE FROM track_l1_external_ids;
            DELETE FROM track_l1_identities;

            INSERT INTO track_l1_identities(
                l1_id, provider, external_track_id, fallback_track_id,
                identity_status, representative_track_id
            )
            SELECT track_id, 'local', NULL, track_id, 'active', track_id
              FROM tracks
             ORDER BY track_id;

            INSERT INTO track_l1_external_ids(
                provider, external_track_id, l1_id, evidence_type,
                is_primary, first_seen_at, last_seen_at
            )
            SELECT 'spotify', owners.spotify_track_id, owners.track_id,
                   'migration',
                   CASE WHEN owners.spotify_track_id=(
                       SELECT MIN(peer.spotify_track_id)
                         FROM spotify_track_owners peer
                        WHERE peer.track_id=owners.track_id
                   ) THEN 1 ELSE 0 END,
                   owners.first_seen_at, owners.last_seen_at
              FROM spotify_track_owners owners;

            INSERT INTO track_l1_source_links(
                l1_id, track_id, evidence_type, observed_plays,
                first_seen_at, last_seen_at
            )
            SELECT owners.track_id, p.track_id, 'play_at_time', COUNT(*),
                   MIN(p.ts), MAX(p.ts)
              FROM plays p
              JOIN spotify_track_owners owners
                ON owners.spotify_track_id=p.spotify_track_id_at_play
             WHERE p.track_id IS NOT NULL
             GROUP BY owners.track_id, p.track_id;

            INSERT OR IGNORE INTO track_l1_source_links(
                l1_id, track_id, evidence_type, observed_plays
            )
            SELECT COALESCE(owners.track_id, t.track_id), t.track_id,
                   'track_projection', 0
              FROM tracks t
              LEFT JOIN spotify_track_owners owners
                ON owners.spotify_track_id=t.spotify_track_id;

            INSERT OR IGNORE INTO track_group_candidates(
                scope, original_l1_id, candidate_l1_id,
                confidence, evidence_json, status, created_at
            )
            SELECT scope,
                   MIN(original_track_id, candidate_track_id),
                   MAX(original_track_id, candidate_track_id),
                   confidence, evidence_json, status, created_at
              FROM _track_candidates_v57;

            UPDATE track_groups SET group_status='archived';
            DELETE FROM track_group_l1_members;

            INSERT OR IGNORE INTO track_group_l1_members(group_id, l1_id)
            SELECT members.group_id, owners.track_id
              FROM track_group_members members
              JOIN tracks source ON source.track_id=members.track_id
              JOIN spotify_track_owners owners
                ON owners.spotify_track_id=source.spotify_track_id
            UNION
            SELECT members.group_id, owners.track_id
              FROM track_group_members members
              JOIN plays p ON p.track_id=members.track_id
              JOIN spotify_track_owners owners
                ON owners.spotify_track_id=p.spotify_track_id_at_play
            UNION
            SELECT members.group_id, members.track_id
              FROM track_group_members members
             WHERE NOT EXISTS (
                 SELECT 1
                   FROM tracks source
                   JOIN spotify_track_owners owners
                     ON owners.spotify_track_id=source.spotify_track_id
                  WHERE source.track_id=members.track_id
             )
               AND NOT EXISTS (
                 SELECT 1
                   FROM plays p
                   JOIN spotify_track_owners owners
                     ON owners.spotify_track_id=p.spotify_track_id_at_play
                  WHERE p.track_id=members.track_id
             );

            UPDATE track_groups
               SET primary_l1_id=COALESCE(
                   (SELECT owners.track_id
                      FROM tracks source
                      JOIN spotify_track_owners owners
                        ON owners.spotify_track_id=source.spotify_track_id
                     WHERE source.track_id=track_groups.primary_track_id
                     LIMIT 1),
                   primary_track_id,
                   (SELECT MIN(l1_id) FROM track_group_l1_members members
                     WHERE members.group_id=track_groups.group_id)
               );

            UPDATE track_identity_state
               SET current_revision=current_revision+1,
                   policy_version='spotify_owner_track_v1',
                   updated_at=datetime('now')
             WHERE state_id=1;

            UPDATE music_search_snapshot_meta
               SET status='stale',
                   last_error='track_id ownership repair requires rebuild'
             WHERE status IN ('pending', 'running', 'ready');
            """
        )

        groups = conn.execute(
            """SELECT groups.group_id
                 FROM track_groups groups
                 JOIN track_group_l1_members members
                   ON members.group_id=groups.group_id
                GROUP BY groups.group_id
               HAVING COUNT(DISTINCT members.l1_id)>1
                ORDER BY groups.is_manual DESC, groups.group_id"""
        ).fetchall()
        for (group_id,) in groups:
            try:
                conn.execute(
                    "UPDATE track_groups SET group_status='active' WHERE group_id=?",
                    (int(group_id),),
                )
            except sqlite3.IntegrityError:
                conn.execute(
                    "UPDATE track_groups SET group_status='conflict' WHERE group_id=?",
                    (int(group_id),),
                )

        conn.executescript(
            """
            DROP TABLE IF EXISTS _spotify_owner_candidates_v57;
            DROP TABLE IF EXISTS _old_l1_to_track_v57;
            DROP TABLE IF EXISTS _track_candidates_v57;
            """
        )
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


@migration(58, "normalize_track_governance_to_spotify_owners")
def migrate_058(conn: sqlite3.Connection):
    """Normalize L2/L3 governance references without rewriting raw facts.

    Version 57 restored the public canonical id to an existing ``track_id``
    but deliberately retained compatibility identities for every historical
    track row.  This follow-up makes saved groups and review candidates owner
    aware.  A track that owns any play-time Spotify id remains canonical even
    when its legacy ``tracks.spotify_track_id`` points at another owner.
    """
    from backend.domains.metadata.track_identity import resolve_canonical_track_id

    group_rows = conn.execute(
        """SELECT group_id, scope, is_manual, group_status,
                  primary_l1_id, primary_track_id
             FROM track_groups ORDER BY group_id"""
    ).fetchall()
    original_status = {int(row[0]): str(row[3]) for row in group_rows}
    normalized_members: dict[int, list[int]] = {}
    group_changed = False

    # Disable active-scope triggers while every member is rewritten through
    # the same canonical resolver.  Original statuses are restored below.
    conn.execute("UPDATE track_groups SET group_status='archived' WHERE group_status!='archived'")
    for row in group_rows:
        group_id = int(row[0])
        members = [
            int(member[0])
            for member in conn.execute(
                "SELECT l1_id FROM track_group_l1_members WHERE group_id=? ORDER BY l1_id",
                (group_id,),
            ).fetchall()
        ]
        canonical_members = sorted(
            {
                canonical
                for member in members
                if (canonical := resolve_canonical_track_id(conn, member)) is not None
            }
        )
        normalized_members[group_id] = canonical_members
        if canonical_members != members:
            group_changed = True
            conn.execute(
                """INSERT INTO track_group_migration_audit(
                       group_id, action, distinct_l1_count, details
                   ) VALUES (?, 'v58_normalized_spotify_owner_members', ?, ?)""",
                (
                    group_id,
                    len(canonical_members),
                    f"before={','.join(map(str, members))};after={','.join(map(str, canonical_members))}",
                ),
            )

    conn.execute("DELETE FROM track_group_l1_members")
    for row in group_rows:
        group_id = int(row[0])
        members = normalized_members[group_id]
        conn.executemany(
            "INSERT OR IGNORE INTO track_group_l1_members(group_id,l1_id) VALUES (?,?)",
            ((group_id, member) for member in members),
        )
        primary = resolve_canonical_track_id(conn, int(row[4])) if row[4] is not None else None
        if primary not in members:
            primary = members[0] if members else None
        representative = None
        if primary is not None:
            identity = conn.execute(
                """SELECT identities.representative_track_id, tracks.track_name
                     FROM track_l1_identities identities
                     JOIN tracks ON tracks.track_id=identities.representative_track_id
                    WHERE identities.l1_id=?""",
                (primary,),
            ).fetchone()
            if identity is not None:
                representative = int(identity[0])
        conn.execute(
            """UPDATE track_groups
                  SET primary_l1_id=?, primary_track_id=COALESCE(?, primary_track_id)
                WHERE group_id=?""",
            (primary, representative, group_id),
        )

    # Restore valid active groups deterministically.  Normalization can reveal
    # a same-scope overlap that the old compatibility ids concealed.
    active_rows = sorted(
        (row for row in group_rows if original_status[int(row[0])] == "active"),
        key=lambda row: (-int(row[2]), int(row[0])),
    )
    for row in active_rows:
        group_id = int(row[0])
        members = normalized_members[group_id]
        if len(members) < 2:
            group_changed = True
            conn.execute(
                """INSERT INTO track_group_migration_audit(
                       group_id, action, distinct_l1_count, details
                   ) VALUES (?, 'v58_collapsed_same_spotify_owner', ?, ?)""",
                (group_id, len(members), f"scope={row[1]}"),
            )
            continue
        try:
            conn.execute(
                "UPDATE track_groups SET group_status='active' WHERE group_id=?",
                (group_id,),
            )
        except sqlite3.IntegrityError:
            group_changed = True
            conn.execute(
                "UPDATE track_groups SET group_status='conflict' WHERE group_id=?",
                (group_id,),
            )
            conn.execute(
                """INSERT INTO track_group_migration_audit(
                       group_id, action, distinct_l1_count, details
                   ) VALUES (?, 'v58_quarantined_owner_overlap', ?, ?)""",
                (group_id, len(members), f"scope={row[1]}"),
            )
    for row in group_rows:
        group_id = int(row[0])
        if original_status[group_id] == "conflict" and len(normalized_members[group_id]) >= 2:
            conn.execute(
                "UPDATE track_groups SET group_status='conflict' WHERE group_id=?",
                (group_id,),
            )

    candidate_rows = conn.execute(
        """SELECT candidate_id, scope, original_l1_id, candidate_l1_id,
                  confidence, evidence_json, status, created_at
             FROM track_group_candidates ORDER BY candidate_id"""
    ).fetchall()
    candidate_changed = False
    normalized_candidates: dict[tuple[str, int, int], tuple] = {}
    status_priority = {"accepted": 0, "pending": 1, "rejected": 2}
    for row in candidate_rows:
        left = resolve_canonical_track_id(conn, int(row[2]))
        right = resolve_canonical_track_id(conn, int(row[3]))
        if left is None or right is None or left == right:
            candidate_changed = True
            conn.execute(
                """INSERT INTO track_group_migration_audit(
                       group_id, action, distinct_l1_count, details
                   ) VALUES (0, 'v58_removed_same_owner_candidate', ?, ?)""",
                (
                    0 if left is None and right is None else 1,
                    f"candidate_id={int(row[0])};before={int(row[2])},{int(row[3])}",
                ),
            )
            continue
        left, right = sorted((left, right))
        key = (str(row[1]), left, right)
        current = normalized_candidates.get(key)
        if current is None or status_priority[str(row[6])] < status_priority[str(current[6])]:
            normalized_candidates[key] = (
                int(row[0]),
                str(row[1]),
                left,
                right,
                row[4],
                str(row[5]),
                str(row[6]),
                row[7],
            )
        if left != int(row[2]) or right != int(row[3]) or current is not None:
            candidate_changed = True

    conn.execute("DELETE FROM track_group_candidates")
    for row in sorted(normalized_candidates.values(), key=lambda item: item[0]):
        status = str(row[6])
        active_group = conn.execute(
            """SELECT 1
                 FROM track_groups groups
                 JOIN track_group_l1_members left_member
                   ON left_member.group_id=groups.group_id AND left_member.l1_id=?
                 JOIN track_group_l1_members right_member
                   ON right_member.group_id=groups.group_id AND right_member.l1_id=?
                WHERE groups.scope=? AND groups.group_status='active'
                LIMIT 1""",
            (int(row[2]), int(row[3]), str(row[1])),
        ).fetchone()
        if active_group is not None and status != "accepted":
            status = "accepted"
            candidate_changed = True
        conn.execute(
            """INSERT INTO track_group_candidates(
                   candidate_id, scope, original_l1_id, candidate_l1_id,
                   confidence, evidence_json, status, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (row[0], row[1], row[2], row[3], row[4], row[5], status, row[7]),
        )

    if group_changed or candidate_changed:
        conn.execute(
            """UPDATE track_identity_state
                  SET current_revision=current_revision+1,
                      updated_at=datetime('now')
                WHERE state_id=1"""
        )
    if group_changed:
        conn.execute(
            """UPDATE music_search_snapshot_meta
                  SET status='stale',
                      last_error='track governance owner normalization requires rebuild'
                WHERE status IN ('pending', 'running', 'ready')"""
        )


@migration(59, "historical_fk_cleanup_support")
def migrate_059(conn: sqlite3.Connection):
    """Make FK enforcement viable and add explicit debt-cleanup support.

    This migration is deliberately schema-only. Historical rows are removed
    only by the separately confirmed maintenance command after its preview has
    been accepted against an unchanged database revision.
    """

    release_group_fks = conn.execute("PRAGMA foreign_key_list(release_groups)").fetchall()
    parent_targets = {str(row[2]) for row in release_group_fks if str(row[3]) == "parent_group_id"}
    if parent_targets != {"release_groups"}:
        conn.execute("PRAGMA foreign_keys=OFF")
        try:
            conn.execute("DROP TABLE IF EXISTS release_groups_repaired")
            conn.execute(
                """CREATE TABLE release_groups_repaired (
                    group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canonical_name TEXT NOT NULL,
                    artist_id INTEGER REFERENCES artists(artist_id),
                    primary_album_id INTEGER REFERENCES albums(album_id),
                    scope TEXT NOT NULL DEFAULT 'release'
                        CHECK(scope IN ('release', 'composition')),
                    parent_group_id INTEGER REFERENCES release_groups(group_id),
                    is_manual BOOLEAN DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(canonical_name, artist_id, scope)
                )"""
            )
            conn.execute(
                """INSERT INTO release_groups_repaired(
                       group_id, canonical_name, artist_id, primary_album_id,
                       scope, parent_group_id, is_manual, created_at
                   )
                   SELECT group_id, canonical_name, artist_id, primary_album_id,
                          scope, parent_group_id, is_manual, created_at
                     FROM release_groups"""
            )
            conn.execute("DROP TABLE release_groups")
            conn.execute("ALTER TABLE release_groups_repaired RENAME TO release_groups")
            conn.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_rg_artist ON release_groups(artist_id);
                CREATE INDEX IF NOT EXISTS idx_rg_scope ON release_groups(scope);
                CREATE INDEX IF NOT EXISTS idx_rg_parent ON release_groups(parent_group_id);
                """
            )
        finally:
            conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS track_id_aliases (
            alias_track_id      INTEGER PRIMARY KEY,
            canonical_track_id INTEGER NOT NULL REFERENCES tracks(track_id),
            reason             TEXT NOT NULL,
            created_at         TEXT NOT NULL DEFAULT (datetime('now')),
            CHECK(alias_track_id != canonical_track_id)
        );
        CREATE INDEX IF NOT EXISTS idx_track_id_aliases_canonical
            ON track_id_aliases(canonical_track_id);

        CREATE TABLE IF NOT EXISTS historical_fk_cleanup_runs (
            run_id          TEXT PRIMARY KEY,
            plan_token      TEXT NOT NULL,
            status          TEXT NOT NULL CHECK(status IN ('running', 'completed')),
            summary_json    TEXT NOT NULL DEFAULT '{}',
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at    TEXT
        );

        CREATE TABLE IF NOT EXISTS historical_fk_cleanup_archive (
            run_id          TEXT NOT NULL REFERENCES historical_fk_cleanup_runs(run_id),
            source_table    TEXT NOT NULL,
            source_row_key  TEXT NOT NULL,
            row_json        TEXT NOT NULL,
            archived_at     TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY(run_id, source_table, source_row_key)
        );
        CREATE INDEX IF NOT EXISTS idx_historical_fk_cleanup_archive_source
            ON historical_fk_cleanup_archive(source_table, source_row_key);
        """
    )


# ── Runner ────────────────────────────────────────────────────────────────


@migration(60, "music_search_candidate_maintenance_state")
def migrate_060(conn: sqlite3.Connection):
    """Separate the published candidate generation from its next build."""

    maintenance_state_exists = False
    if conn.execute(
        """SELECT 1 FROM sqlite_master
           WHERE type='table' AND name='music_search_candidate_maintenance_state'"""
    ).fetchone():
        prior = conn.execute(
            """SELECT target_source_revision, target_candidate_index_version,
                      maintenance_status, started_at, finished_at, last_error
               FROM music_search_candidate_maintenance_state WHERE state_id=1"""
        ).fetchone()
        # The CREATE + default singleton can survive a process interruption
        # before legacy state is backfilled.  A bare ``missing`` row is not a
        # completed migration marker and must be retried.
        maintenance_state_exists = bool(
            prior
            and (
                prior[0]
                or prior[1]
                or str(prior[2] or "missing") != "missing"
                or prior[3]
                or prior[4]
                or prior[5]
            )
        )
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS music_search_candidate_maintenance_state (
            state_id INTEGER PRIMARY KEY CHECK (state_id = 1),
            target_source_revision TEXT,
            target_candidate_index_version TEXT,
            maintenance_status TEXT NOT NULL DEFAULT 'missing'
                CHECK (maintenance_status IN (
                    'missing', 'pending', 'building', 'ready', 'failed'
                )),
            building_generation_id TEXT,
            job_id TEXT,
            started_at TEXT,
            finished_at TEXT,
            last_error TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT OR IGNORE INTO music_search_candidate_maintenance_state(
            state_id, maintenance_status
        ) VALUES (1, 'missing');
        """
    )
    if maintenance_state_exists:
        return

    state = conn.execute(
        """SELECT active_generation_id, status, tokenizer, source_revision,
                  candidate_index_version, last_error
             FROM music_search_index_state WHERE state_id=1"""
    ).fetchone()
    if state is None:
        return

    active_generation_id = str(state[0]) if state[0] else None
    active_document_exists = bool(
        active_generation_id
        and conn.execute(
            """SELECT 1 FROM music_search_documents
               WHERE generation_id=? LIMIT 1""",
            (active_generation_id,),
        ).fetchone()
    )
    legacy_status = str(state[1] or "missing")
    if active_document_exists:
        serving_status = (
            "degraded"
            if legacy_status == "degraded" or str(state[2] or "").startswith("bounded_")
            else "ready"
        )
    else:
        serving_status = "missing"
    conn.execute(
        """UPDATE music_search_index_state
              SET status=?, updated_at=datetime('now')
            WHERE state_id=1""",
        (serving_status,),
    )

    if legacy_status in {"building", "failed"}:
        maintenance_status = legacy_status
    elif active_document_exists:
        maintenance_status = "ready"
    else:
        maintenance_status = "missing"
    conn.execute(
        """UPDATE music_search_candidate_maintenance_state
              SET target_source_revision=?, target_candidate_index_version=?,
                  maintenance_status=?,
                  last_error=CASE WHEN ?='failed' THEN ? ELSE NULL END,
                  finished_at=CASE WHEN ? IN ('ready', 'failed')
                                   THEN datetime('now') ELSE NULL END,
                  updated_at=datetime('now')
            WHERE state_id=1""",
        (
            str(state[3]) if state[3] else None,
            str(state[4]) if state[4] else None,
            maintenance_status,
            maintenance_status,
            str(state[5]) if state[5] else None,
            maintenance_status,
        ),
    )


@migration(61, "music_search_snapshot_variant_state")
def migrate_061(conn: sqlite3.Connection):
    """Keep one verified serving snapshot while a newer target is maintained."""

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS music_search_snapshot_variant_state (
            merge_level INTEGER NOT NULL,
            dynamic_threshold INTEGER NOT NULL CHECK(dynamic_threshold IN (0, 1)),
            active_snapshot_key TEXT,
            active_filter_fingerprint TEXT,
            target_filter_fingerprint TEXT,
            maintenance_status TEXT NOT NULL DEFAULT 'ready'
                CHECK(maintenance_status IN ('ready', 'pending', 'building', 'failed')),
            job_id TEXT,
            last_error TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY(merge_level, dynamic_threshold)
        );
        CREATE INDEX IF NOT EXISTS idx_music_search_snapshot_variant_active
            ON music_search_snapshot_variant_state(active_snapshot_key);
        """
    )
    meta_exists = conn.execute(
        """SELECT 1 FROM sqlite_master
           WHERE type='table' AND name='music_search_snapshot_meta'"""
    ).fetchone()
    payload_exists = conn.execute(
        """SELECT 1 FROM sqlite_master
           WHERE type='table' AND name='music_search_entity_context'"""
    ).fetchone()
    if meta_exists is None or payload_exists is None:
        return
    for merge_level in (2, 3):
        for dynamic_threshold in (1, 0):
            active = conn.execute(
                """SELECT meta.snapshot_key, meta.filter_fingerprint
                   FROM music_search_snapshot_meta meta
                   WHERE meta.merge_level=? AND meta.dynamic_threshold=?
                     AND meta.status IN ('ready', 'stale')
                     AND meta.builder_version='music_search_snapshot_v8_canonical_track'
                     AND EXISTS(
                         SELECT 1 FROM music_search_entity_context payload
                         WHERE payload.snapshot_key=meta.snapshot_key
                     )
                   ORDER BY COALESCE(meta.activated_at, meta.created_at) DESC
                   LIMIT 1""",
                (merge_level, dynamic_threshold),
            ).fetchone()
            target = conn.execute(
                """SELECT filter_fingerprint, status, last_error
                   FROM music_search_snapshot_meta
                   WHERE merge_level=? AND dynamic_threshold=?
                   ORDER BY created_at DESC LIMIT 1""",
                (merge_level, dynamic_threshold),
            ).fetchone()
            if active is None and target is None:
                continue
            raw_status = str(target[1] if target is not None else "ready")
            maintenance_status = {
                "running": "building",
                "pending": "pending",
                "failed": "failed",
            }.get(raw_status, "ready")
            conn.execute(
                """INSERT OR REPLACE INTO music_search_snapshot_variant_state(
                       merge_level, dynamic_threshold, active_snapshot_key,
                       active_filter_fingerprint, target_filter_fingerprint,
                       maintenance_status, last_error, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (
                    merge_level,
                    dynamic_threshold,
                    str(active[0]) if active is not None else None,
                    str(active[1]) if active is not None else None,
                    str(target[0]) if target is not None else None,
                    maintenance_status,
                    str(target[2]) if target is not None and target[2] else None,
                ),
            )


@migration(62, "track_credit_change_sets")
def migrate_062(conn: sqlite3.Connection):
    """Persist canonical before/after evidence for bounded credit maintenance."""

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS track_credit_change_sets (
            change_set_id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_revision INTEGER NOT NULL,
            to_revision INTEGER NOT NULL UNIQUE,
            track_id INTEGER NOT NULL REFERENCES tracks(track_id),
            canonical_track_ids_json TEXT NOT NULL,
            before_credits_json TEXT NOT NULL,
            after_credits_json TEXT NOT NULL,
            before_roles_json TEXT NOT NULL,
            after_roles_json TEXT NOT NULL,
            affected_artist_ids_json TEXT NOT NULL,
            candidate_changed INTEGER NOT NULL DEFAULT 1 CHECK(candidate_changed IN (0, 1)),
            statistics_membership_changed INTEGER NOT NULL DEFAULT 0
                CHECK(statistics_membership_changed IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            consumed_at TEXT,
            CHECK(to_revision = from_revision + 1)
        );
        CREATE INDEX IF NOT EXISTS idx_track_credit_change_sets_unconsumed
            ON track_credit_change_sets(consumed_at, to_revision);
        CREATE INDEX IF NOT EXISTS idx_track_credit_change_sets_track
            ON track_credit_change_sets(track_id, to_revision);
        """
    )


@migration(63, "music_search_entity_deny_overlay")
def migrate_063(conn: sqlite3.Connection):
    """Exclude sensitive entities immediately while an older generation serves."""

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS music_search_entity_deny_overlay (
            entity_key TEXT PRIMARY KEY,
            reason TEXT NOT NULL,
            target_source_revision TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_music_search_entity_deny_target
            ON music_search_entity_deny_overlay(target_source_revision);
        """
    )


@migration(64, "album_project_revision_state")
def migrate_064(conn: sqlite3.Connection):
    """Add an O(1) revision for Album Project and track-presentation changes."""

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS album_project_revision_state (
            state_id INTEGER PRIMARY KEY CHECK(state_id = 1),
            current_revision INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT OR IGNORE INTO album_project_revision_state(state_id, current_revision)
        VALUES (1, 0);
        """
    )


@migration(65, "music_search_track_presentation_fields")
def migrate_065(conn: sqlite3.Connection):
    """Persist structured track ownership and artwork provenance in generations."""

    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(music_search_documents)")}
    additions = {
        "membership_role": "TEXT",
        "cover_album_id": "INTEGER",
        "cover_source": "TEXT",
        "presentation_status": "TEXT",
    }
    for name, sql_type in additions.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE music_search_documents ADD COLUMN {name} {sql_type}")


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
