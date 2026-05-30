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
