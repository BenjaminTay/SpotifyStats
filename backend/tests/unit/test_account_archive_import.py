from __future__ import annotations

import json
import sqlite3

import pytest

from backend.core.import_account_data import import_your_library

pytestmark = pytest.mark.unit


def _library_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE saved_tracks (
            track_uri TEXT PRIMARY KEY,
            track_name TEXT,
            artist_name TEXT,
            album_name TEXT,
            added_date TEXT,
            spotify_track_id TEXT,
            added_date_source TEXT CHECK(added_date_source IN ('oauth', 'manual', 'legacy'))
        );
        CREATE TABLE saved_albums (album_uri TEXT PRIMARY KEY, album_name TEXT, artist_name TEXT);
        CREATE TABLE saved_artists (artist_uri TEXT PRIMARY KEY, artist_name TEXT);
        CREATE TABLE saved_shows (show_uri TEXT PRIMARY KEY, show_name TEXT, publisher TEXT);
        CREATE TABLE banned_items (uri TEXT PRIMARY KEY, item_name TEXT, item_type TEXT);
        """
    )
    return conn


def test_your_library_reimport_preserves_existing_added_dates(tmp_path) -> None:
    payload = {
        "tracks": [
            {
                "uri": "spotify:track:keep",
                "track": "Keep Date",
                "artist": "Archive Artist",
                "album": "Archive Album",
            },
            {
                "uri": "spotify:track:new",
                "track": "No Date Yet",
                "artist": "Archive Artist",
                "album": "Archive Album",
            },
        ],
        "albums": [],
        "artists": [],
        "shows": [],
        "bannedTracks": [],
        "bannedArtists": [],
    }
    (tmp_path / "YourLibrary.json").write_text(json.dumps(payload), encoding="utf-8")
    conn = _library_conn()
    conn.executemany(
        "INSERT INTO saved_tracks("
        "track_uri, track_name, added_date, spotify_track_id, added_date_source"
        ") VALUES (?, ?, ?, ?, ?)",
        [
            (
                "spotify:track:keep",
                "Old Name",
                "2023-06-01T12:30:00Z",
                "keep",
                "oauth",
            ),
            (
                "spotify:track:removed",
                "Removed Snapshot Item",
                "2022-01-01T00:00:00Z",
                "removed",
                "legacy",
            ),
        ],
    )
    conn.commit()

    result = import_your_library(data_dir=str(tmp_path), conn=conn)
    rows = conn.execute(
        "SELECT track_uri, track_name, added_date, added_date_source "
        "FROM saved_tracks ORDER BY track_uri"
    ).fetchall()
    revision = conn.execute(
        "SELECT account_import_revision FROM account_archive_state WHERE state_id = 1"
    ).fetchone()[0]
    conn.close()

    assert result["tracks"] == 2
    assert result["preserved_added_dates"] == 1
    assert result["missing_added_dates"] == 1
    assert [tuple(row) for row in rows] == [
        (
            "spotify:track:keep",
            "Keep Date",
            "2023-06-01T12:30:00Z",
            "oauth",
        ),
        ("spotify:track:new", "No Date Yet", None, None),
    ]
    assert revision == 1
