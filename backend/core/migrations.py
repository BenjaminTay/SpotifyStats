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
