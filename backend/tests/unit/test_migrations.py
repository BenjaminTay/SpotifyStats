"""Tests for versioned schema migration system."""

from __future__ import annotations

import os
import sqlite3
import tempfile

import pytest

from backend.core.migrations import MIGRATIONS, _applied_versions, _ensure_migrations_table


@pytest.fixture
def empty_db():
    """Create a fresh temporary SQLite database."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
    os.unlink(path)


def test_migrations_registered():
    """All migrations are registered with unique version numbers."""
    versions = [m[0] for m in MIGRATIONS]
    assert len(versions) == len(set(versions)), "Duplicate migration versions"
    assert versions == sorted(versions), "Migrations not sorted"
    assert len(MIGRATIONS) >= 10, f"Expected at least 10 migrations, got {len(MIGRATIONS)}"


def test_ensure_migrations_table(empty_db):
    """schema_migrations table is created idempotently."""
    _ensure_migrations_table(empty_db)
    _ensure_migrations_table(empty_db)  # idempotent

    rows = empty_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchall()
    assert len(rows) == 1


def test_applied_versions_empty(empty_db):
    """No applied versions on fresh DB."""
    _ensure_migrations_table(empty_db)
    assert _applied_versions(empty_db) == set()


def test_migration_idempotency(empty_db):
    """Running all migrations once, then re-running is safe.

    migrate_001 creates the full SCHEMA (including columns that later
    migrations add), so on fresh DBs migrations 2-9 are no-ops. The
    runner handles this via try/except OperationalError.
    """
    _ensure_migrations_table(empty_db)

    # First pass: apply all migrations (some may be no-ops on fresh DB)
    sorted_migrations = sorted(MIGRATIONS, key=lambda m: m[0])
    for version, name, fn in sorted_migrations:
        try:
            fn(empty_db)
        except sqlite3.OperationalError:
            pass  # column/index already exists from migrate_001
        empty_db.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (?, ?)",
            (version, name),
        )
        empty_db.commit()

    # Second pass: running them all again should be safe
    for version, name, fn in sorted_migrations:
        try:
            fn(empty_db)
        except sqlite3.OperationalError:
            pass  # expected

    applied = _applied_versions(empty_db)
    assert applied == {m[0] for m in MIGRATIONS}


def test_all_core_tables_exist(empty_db):
    """After running all migrations, core tables exist."""
    _ensure_migrations_table(empty_db)

    sorted_migrations = sorted(MIGRATIONS, key=lambda m: m[0])
    for _, _, fn in sorted_migrations:
        try:
            fn(empty_db)
        except sqlite3.OperationalError:
            pass

    tables = {
        r[0]
        for r in empty_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    required = {"artists", "albums", "tracks", "plays", "track_albums", "settings"}
    assert required.issubset(tables), f"Missing tables: {required - tables}"


def test_track_credit_management_tables_exist_after_migrations(empty_db):
    _ensure_migrations_table(empty_db)
    for _, _, fn in sorted(MIGRATIONS, key=lambda item: item[0]):
        try:
            fn(empty_db)
        except sqlite3.OperationalError:
            pass
    tables = {
        row[0]
        for row in empty_db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {"track_credit_overrides", "track_credit_events", "track_credit_state"} <= tables


def test_background_jobs_table_exists(empty_db):
    """background_jobs table is created by migrate_010."""
    _ensure_migrations_table(empty_db)
    sorted_migrations = sorted(MIGRATIONS, key=lambda m: m[0])
    for _, _, fn in sorted_migrations:
        try:
            fn(empty_db)
        except sqlite3.OperationalError:
            pass
    tables = {
        r[0]
        for r in empty_db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert "background_jobs" in tables


def test_plays_has_source_album_id_after_migrations(empty_db):
    """Migration 13 adds source_album_id column and index."""
    _ensure_migrations_table(empty_db)
    sorted_migrations = sorted(MIGRATIONS, key=lambda m: m[0])
    for _, _, fn in sorted_migrations:
        try:
            fn(empty_db)
        except sqlite3.OperationalError:
            pass
    cols = {row[1] for row in empty_db.execute("PRAGMA table_info(plays)").fetchall()}
    assert "source_album_id" in cols

    indexes = {row[1] for row in empty_db.execute("PRAGMA index_list(plays)").fetchall()}
    assert "idx_plays_source_album" in indexes


def test_import_maintenance_schema_after_migrations(empty_db):
    """Import maintenance schema stores play-time Spotify ids and album evidence."""
    _ensure_migrations_table(empty_db)
    sorted_migrations = sorted(MIGRATIONS, key=lambda m: m[0])
    for _, _, fn in sorted_migrations:
        try:
            fn(empty_db)
        except sqlite3.OperationalError:
            pass

    play_columns = {row[1] for row in empty_db.execute("PRAGMA table_info(plays)").fetchall()}
    assert "spotify_track_id_at_play" in play_columns
    assert "spotify_album_id_at_play" in play_columns

    tables = {
        row[0]
        for row in empty_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    assert "album_spotify_links" in tables

    play_indexes = {row[1] for row in empty_db.execute("PRAGMA index_list(plays)").fetchall()}
    assert "idx_plays_spotify_track_at_play" in play_indexes
    assert "idx_plays_spotify_album_at_play" in play_indexes

    link_indexes = {
        row[1] for row in empty_db.execute("PRAGMA index_list(album_spotify_links)").fetchall()
    }
    assert "idx_album_spotify_links_album" in link_indexes
    assert "idx_album_spotify_links_spotify_album" in link_indexes


def test_release_groups_support_scope_and_parent(empty_db):
    """Migration 14 adds scope and parent_group_id to release_groups."""
    _ensure_migrations_table(empty_db)
    sorted_migrations = sorted(MIGRATIONS, key=lambda m: m[0])
    for _, _, fn in sorted_migrations:
        try:
            fn(empty_db)
        except sqlite3.OperationalError:
            pass
    cols = {row[1] for row in empty_db.execute("PRAGMA table_info(release_groups)").fetchall()}
    assert {"scope", "parent_group_id"} <= cols


def test_migration_023_adds_artist_genre_resolution_tables(tmp_path, monkeypatch):
    from backend.core import db as db_mod
    from backend.core import migrations

    db_path = tmp_path / "spotify_stats.db"
    monkeypatch.setattr(db_mod, "DB_PATH", str(db_path))

    db_mod.init_db()
    migrations.run_migrations()

    conn = db_mod.get_db(readonly=True)
    try:
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "artist_genre_sources" in tables
        assert "artist_genre_overrides" in tables
        assert "artist_genre_review_queue" in tables

        source_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(artist_genre_sources)").fetchall()
        }
        assert {
            "artist_name",
            "source",
            "normalized_genres_json",
            "confidence",
            "status",
            "evidence_summary",
        } <= source_columns

        indexes = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        }
        assert "idx_artist_genre_sources_artist" in indexes
    finally:
        conn.close()


def test_migrate_023_upgrades_existing_database_without_fresh_schema(empty_db):
    """Migration 23 itself creates artist genre resolution tables."""
    from backend.core import migrations

    migrations.migrate_023(empty_db)

    tables = {
        row[0]
        for row in empty_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    assert "artist_genre_sources" in tables
    assert "artist_genre_overrides" in tables
    assert "artist_genre_review_queue" in tables

    source_columns = {
        row[1] for row in empty_db.execute("PRAGMA table_info(artist_genre_sources)").fetchall()
    }
    assert {
        "artist_name",
        "spotify_artist_id",
        "source",
        "source_key",
        "normalized_genres_json",
        "confidence",
        "status",
    } <= source_columns

    indexes = {
        row[1] for row in empty_db.execute("PRAGMA index_list(artist_genre_sources)").fetchall()
    }
    assert "idx_artist_genre_sources_artist" in indexes


def test_migration_027_adds_pre_review_fields_to_both_review_queues(empty_db):
    from backend.core import migrations

    migrations.migrate_001(empty_db)
    migrations.migrate_024(empty_db)
    migrations.migrate_027(empty_db)

    required = {
        "pre_review_recommendation",
        "pre_review_confidence",
        "pre_review_note",
        "pre_reviewed_by",
        "pre_reviewed_at",
    }
    for table in ("artist_genre_review_queue", "artist_language_review_queue"):
        columns = {row[1] for row in empty_db.execute(f"PRAGMA table_info({table})")}
        assert required <= columns


def test_migration_033_invalidates_old_search_documents_without_touching_source_data(empty_db):
    from backend.core import migrations

    empty_db.executescript(
        """
        CREATE TABLE music_search_index_state (
            state_id INTEGER PRIMARY KEY,
            active_generation_id TEXT,
            previous_generation_id TEXT,
            status TEXT NOT NULL,
            tokenizer TEXT,
            normalization_version TEXT NOT NULL,
            source_revision TEXT,
            document_count INTEGER NOT NULL DEFAULT 0,
            built_at TEXT,
            last_error TEXT,
            updated_at TEXT NOT NULL
        );
        INSERT INTO music_search_index_state VALUES (
            1, 'old-generation', NULL, 'ready', 'trigram', 'v1', 'old-source',
            1, '2026-08-16', NULL, '2026-08-16'
        );
        CREATE TABLE music_search_documents (
            generation_id TEXT NOT NULL,
            entity_key TEXT NOT NULL,
            kind TEXT NOT NULL,
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
            PRIMARY KEY(generation_id, entity_key)
        );
        INSERT INTO music_search_documents(
            generation_id, entity_key, kind, label, normalized_label, search_text, href
        ) VALUES ('old-generation', 'track:1', 'track', 'Old', 'old', 'old', '/old');
        CREATE TABLE music_search_snapshot_meta (
            snapshot_key TEXT PRIMARY KEY,
            filter_fingerprint TEXT NOT NULL UNIQUE,
            source_revision TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            activated_at TEXT,
            last_accessed_at TEXT,
            last_error TEXT
        );
        INSERT INTO music_search_snapshot_meta VALUES (
            'snapshot', 'fingerprint', 'old-source', 'ready', '2026-08-16',
            '2026-08-16', NULL, NULL
        );
        CREATE TABLE music_search_entity_context (
            snapshot_key TEXT NOT NULL,
            entity_key TEXT NOT NULL,
            play_events INTEGER NOT NULL DEFAULT 0,
            total_ms INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(snapshot_key, entity_key)
        );
        """
    )

    migrations.migrate_033(empty_db)

    columns = {row[1] for row in empty_db.execute("PRAGMA table_info(music_search_documents)")}
    assert "merge_level" in columns
    assert empty_db.execute("SELECT COUNT(*) FROM music_search_documents").fetchone()[0] == 0
    state = empty_db.execute(
        "SELECT active_generation_id, status, source_revision FROM music_search_index_state"
    ).fetchone()
    assert tuple(state) == (None, "missing", None)
    snapshot = empty_db.execute(
        "SELECT status, last_error FROM music_search_snapshot_meta"
    ).fetchone()
    assert tuple(snapshot) == ("stale", "search index schema upgraded")


def test_migration_034_adds_revision_state_and_invalidates_legacy_snapshots(empty_db):
    from backend.core import migrations

    empty_db.executescript(
        """
        CREATE TABLE music_search_snapshot_meta (
            snapshot_key TEXT PRIMARY KEY,
            filter_fingerprint TEXT NOT NULL UNIQUE,
            source_revision TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            activated_at TEXT,
            last_accessed_at TEXT,
            last_error TEXT
        );
        INSERT INTO music_search_snapshot_meta VALUES (
            'legacy', 'legacy', 'source', 'ready', '2026-08-16',
            '2026-08-16', NULL, NULL
        );
        """
    )

    migrations.migrate_034(empty_db)
    migrations.migrate_034(empty_db)

    columns = {row[1] for row in empty_db.execute("PRAGMA table_info(music_search_snapshot_meta)")}
    assert {
        "semantic_base_key",
        "merge_level",
        "dynamic_threshold",
        "builder_version",
    } <= columns
    revision = empty_db.execute(
        """SELECT playback_revision, billboard_revision, metadata_revision,
                  settings_revision FROM music_search_revision_state WHERE state_id=1"""
    ).fetchone()
    assert tuple(revision) == (0, 0, 0, 0)
    snapshot = empty_db.execute(
        "SELECT status, last_error FROM music_search_snapshot_meta WHERE snapshot_key='legacy'"
    ).fetchone()
    assert tuple(snapshot) == ("stale", "music search snapshot schema upgraded")
    indexes = {row[1] for row in empty_db.execute("PRAGMA index_list(music_search_snapshot_meta)")}
    assert "idx_music_search_snapshot_meta_variant" in indexes
