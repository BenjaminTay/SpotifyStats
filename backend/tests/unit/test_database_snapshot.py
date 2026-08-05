from __future__ import annotations

import sqlite3

import pytest

pytestmark = pytest.mark.unit


def test_database_snapshot_and_restore_preserve_wal_database(tmp_path):
    from backend.domains.imports.database_snapshot import (
        create_database_snapshot,
        restore_database_snapshot,
    )

    db_path = tmp_path / "spotify_stats.db"
    backup_dir = tmp_path / "import_backups"
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() == "wal"
        conn.execute("CREATE TABLE plays (id INTEGER PRIMARY KEY, label TEXT NOT NULL)")
        conn.execute("INSERT INTO plays(label) VALUES ('before import')")
        conn.commit()
    finally:
        conn.close()

    snapshot = create_database_snapshot(
        job_id="fixture/job",
        db_path=db_path,
        backup_dir=backup_dir,
    )
    assert snapshot["status"] == "created"
    assert snapshot["path"]

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO plays(label) VALUES ('partial import')")
        conn.commit()
    finally:
        conn.close()

    restored = restore_database_snapshot(snapshot["path"], db_path=db_path)
    assert restored["status"] == "restored"

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT label FROM plays ORDER BY id").fetchall()
    finally:
        conn.close()
    assert rows == [("before import",)]
    assert not list(backup_dir.glob(".*.tmp"))


def test_snapshot_skips_missing_database_for_first_import(tmp_path):
    from backend.domains.imports.database_snapshot import (
        create_database_snapshot,
        discard_database_created_by_failed_import,
    )

    db_path = tmp_path / "missing.db"
    result = create_database_snapshot(db_path=db_path)

    assert result["status"] == "skipped"
    assert result["reason"] == "database_not_found"
    assert result["source_db"] == str(db_path)
    assert result["path"] is None
    assert result["created_at"]

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE partial_import (id INTEGER)")
        conn.commit()
    finally:
        conn.close()

    rollback = discard_database_created_by_failed_import(db_path)

    assert rollback["status"] == "removed_new_database"
    assert not db_path.exists()
