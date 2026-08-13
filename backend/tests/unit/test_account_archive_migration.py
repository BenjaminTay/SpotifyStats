from __future__ import annotations

import sqlite3

import pytest

from backend.core.migrations import migrate_031

pytestmark = pytest.mark.unit


def test_migrate_031_backfills_legacy_date_provenance_idempotently() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE saved_tracks (
            track_uri TEXT PRIMARY KEY,
            track_name TEXT,
            added_date TEXT
        );
        INSERT INTO saved_tracks(track_uri, track_name, added_date)
        VALUES
            ('spotify:track:dated', 'Dated', '2024-01-02T03:04:05Z'),
            ('spotify:track:missing', 'Missing', NULL);
        """
    )

    migrate_031(conn)
    migrate_031(conn)

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(saved_tracks)")}
    rows = conn.execute(
        "SELECT track_uri, added_date_source FROM saved_tracks ORDER BY track_uri"
    ).fetchall()
    state = conn.execute(
        "SELECT account_import_revision, collection_date_revision "
        "FROM account_archive_state WHERE state_id = 1"
    ).fetchone()
    conn.close()

    assert "added_date_source" in columns
    assert [(row[0], row[1]) for row in rows] == [
        ("spotify:track:dated", "legacy"),
        ("spotify:track:missing", None),
    ]
    assert tuple(state) == (0, 0)
