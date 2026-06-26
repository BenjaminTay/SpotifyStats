from __future__ import annotations

import sqlite3

import pytest

from backend.services.account_service import get_collection_insights

pytestmark = pytest.mark.unit


def _make_collection_conn_with_invalid_save_date() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE saved_tracks (
            track_name TEXT,
            artist_name TEXT,
            album_name TEXT,
            track_uri TEXT,
            spotify_track_id TEXT,
            added_date TEXT
        );
        CREATE TABLE saved_albums (id INTEGER);
        CREATE TABLE saved_artists (id INTEGER);
        CREATE TABLE playlists (id INTEGER);
        CREATE TABLE artists (
            artist_id INTEGER,
            artist_name TEXT,
            image_path TEXT,
            image_url TEXT
        );
        CREATE TABLE albums (
            album_id INTEGER,
            album_name TEXT,
            artist_id INTEGER,
            image_path TEXT,
            image_url TEXT,
            release_date TEXT
        );
        CREATE TABLE tracks (
            track_id INTEGER,
            track_name TEXT,
            artist_id INTEGER,
            album_id INTEGER,
            spotify_track_uri TEXT
        );
        CREATE TABLE plays (
            play_id INTEGER,
            track_id INTEGER,
            ts_date TEXT
        );
        CREATE TABLE spotify_artist_meta (
            artist_name TEXT,
            genres TEXT,
            release_date TEXT
        );
        CREATE TABLE spotify_track_meta (
            spotify_track_id TEXT,
            spotify_album_id TEXT
        );
        CREATE TABLE spotify_album_meta (
            spotify_album_id TEXT,
            release_date TEXT
        );
        """
    )
    conn.execute(
        """
        INSERT INTO saved_tracks
            (track_name, artist_name, album_name, track_uri, spotify_track_id, added_date)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("No Date Song", "Date Edge", "No Date Album", "spotify:track:no-date", "no-date", ""),
    )
    conn.commit()
    return conn


def test_collection_insights_handles_saved_tracks_without_valid_added_dates():
    conn = _make_collection_conn_with_invalid_save_date()
    try:
        result = get_collection_insights(conn)
    finally:
        conn.close()

    assert result["available"] is True
    assert result["first_save_story"] is None
    assert result["chemistry"]["total_with_dates"] == 0
