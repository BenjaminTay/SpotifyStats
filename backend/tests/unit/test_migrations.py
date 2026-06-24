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
