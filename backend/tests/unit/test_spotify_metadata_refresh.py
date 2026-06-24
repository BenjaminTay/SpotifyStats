from __future__ import annotations

import sqlite3

import pytest

pytestmark = pytest.mark.unit


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE plays(
            play_id INTEGER PRIMARY KEY,
            track_id INTEGER,
            source_album_id INTEGER,
            ts_date TEXT,
            spotify_track_id_at_play TEXT,
            spotify_album_id_at_play TEXT
        );
        CREATE TABLE tracks(track_id INTEGER PRIMARY KEY, spotify_track_id TEXT);
        CREATE TABLE spotify_track_meta(
            spotify_track_id TEXT PRIMARY KEY,
            track_name TEXT,
            duration_ms INTEGER,
            popularity INTEGER,
            explicit INTEGER,
            track_number INTEGER,
            disc_number INTEGER,
            isrc TEXT,
            spotify_album_id TEXT
        );
        CREATE TABLE spotify_album_meta(
            spotify_album_id TEXT PRIMARY KEY,
            album_name TEXT,
            album_type TEXT,
            release_date TEXT,
            popularity INTEGER,
            label TEXT,
            genres TEXT,
            image_url TEXT,
            album_artists TEXT,
            total_tracks INTEGER,
            track_list TEXT
        );
        CREATE TABLE album_spotify_links(
            album_id INTEGER NOT NULL,
            spotify_album_id TEXT NOT NULL,
            evidence TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.0,
            play_count INTEGER NOT NULL DEFAULT 0,
            track_count INTEGER NOT NULL DEFAULT 0,
            first_seen TEXT,
            last_seen TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(album_id, spotify_album_id, evidence)
        );
        """
    )
    return conn


def test_select_missing_play_track_ids_prefers_play_time_ids():
    from backend.domains.metadata.spotify_refresh import select_missing_track_ids

    conn = _conn()
    conn.execute("INSERT INTO tracks(track_id, spotify_track_id) VALUES (1, 'old-track')")
    conn.execute(
        "INSERT INTO plays(play_id, track_id, source_album_id, ts_date, spotify_track_id_at_play) "
        "VALUES (1, 1, 10, '2026-06-01', 'new-track')"
    )

    assert select_missing_track_ids(conn, limit=50) == ["new-track", "old-track"]


def test_upsert_track_batch_updates_play_album_ids_and_album_links():
    from backend.domains.metadata.spotify_refresh import upsert_track_batch

    conn = _conn()
    conn.execute("INSERT INTO tracks(track_id, spotify_track_id) VALUES (1, 'track-a')")
    conn.execute(
        "INSERT INTO plays(play_id, track_id, source_album_id, ts_date, spotify_track_id_at_play) "
        "VALUES (1, 1, 10, '2026-06-01', 'track-a')"
    )

    updated = upsert_track_batch(
        conn,
        [
            {
                "id": "track-a",
                "name": "Track A",
                "duration_ms": 180000,
                "popularity": 42,
                "explicit": False,
                "track_number": 3,
                "disc_number": 1,
                "external_ids": {"isrc": "ISRC-A"},
                "album": {"id": "album-a"},
            }
        ],
    )

    assert updated == 1
    row = conn.execute("SELECT spotify_album_id FROM spotify_track_meta").fetchone()
    assert row["spotify_album_id"] == "album-a"
    play = conn.execute("SELECT spotify_album_id_at_play FROM plays").fetchone()
    assert play["spotify_album_id_at_play"] == "album-a"
    link = conn.execute("SELECT * FROM album_spotify_links").fetchone()
    assert link["album_id"] == 10
    assert link["spotify_album_id"] == "album-a"
    assert link["evidence"] == "play_track_api"
    assert link["play_count"] == 1


def test_backfill_album_links_uses_existing_track_metadata():
    from backend.domains.metadata.spotify_refresh import (
        backfill_album_links_from_existing_metadata,
    )

    conn = _conn()
    conn.execute("INSERT INTO tracks(track_id, spotify_track_id) VALUES (1, 'track-a')")
    conn.execute(
        """INSERT INTO spotify_track_meta(
               spotify_track_id, track_name, duration_ms, spotify_album_id)
           VALUES ('track-a', 'Track A', 180000, 'album-a')"""
    )
    conn.execute(
        "INSERT INTO plays(play_id, track_id, source_album_id, ts_date) "
        "VALUES (1, 1, 10, '2026-06-01')"
    )

    changed = backfill_album_links_from_existing_metadata(conn)

    assert changed >= 1
    play = conn.execute(
        "SELECT spotify_track_id_at_play, spotify_album_id_at_play FROM plays"
    ).fetchone()
    assert play["spotify_track_id_at_play"] == "track-a"
    assert play["spotify_album_id_at_play"] == "album-a"
    link = conn.execute("SELECT * FROM album_spotify_links").fetchone()
    assert link["album_id"] == 10
    assert link["spotify_album_id"] == "album-a"
    assert link["evidence"] == "play_track_meta"


def test_upsert_album_batch_preserves_existing_image_when_provider_omits_images():
    from backend.domains.metadata.spotify_refresh import upsert_album_batch

    conn = _conn()
    conn.execute(
        """INSERT INTO spotify_album_meta(
               spotify_album_id, album_name, album_type, release_date, image_url)
           VALUES ('album-a', 'Old Name', 'single', '2026-01-01', 'old.jpg')"""
    )

    updated = upsert_album_batch(
        conn,
        [
            {
                "id": "album-a",
                "name": "Album A",
                "album_type": "album",
                "release_date": "2026-06-01",
                "popularity": 80,
                "label": "Fixture",
                "genres": [],
                "images": [],
                "artists": [{"name": "Artist A"}],
                "total_tracks": 11,
                "tracks": {"items": [{"id": "track-a"}]},
            }
        ],
    )

    assert updated == 1
    row = conn.execute(
        "SELECT * FROM spotify_album_meta WHERE spotify_album_id = 'album-a'"
    ).fetchone()
    assert row["album_name"] == "Album A"
    assert row["album_type"] == "album"
    assert row["image_url"] == "old.jpg"
    assert row["total_tracks"] == 11
    assert row["track_list"] == '["track-a"]'


def test_refresh_missing_spotify_metadata_without_token_returns_partial_report():
    from backend.domains.metadata.spotify_refresh import refresh_missing_spotify_metadata

    conn = _conn()
    conn.execute("INSERT INTO tracks(track_id, spotify_track_id) VALUES (1, 'track-a')")
    conn.execute(
        """INSERT INTO spotify_track_meta(
               spotify_track_id, track_name, duration_ms, spotify_album_id)
           VALUES ('track-a', 'Track A', 180000, 'album-a')"""
    )
    conn.execute(
        "INSERT INTO plays(play_id, track_id, source_album_id, ts_date) "
        "VALUES (1, 1, 10, '2026-06-01')"
    )

    report = refresh_missing_spotify_metadata(conn, provider=object(), access_token=None)

    assert report.provider_available is False
    assert report.errors == ("spotify_credentials_missing",)
    assert report.album_links_backfilled >= 1
    link = conn.execute("SELECT * FROM album_spotify_links").fetchone()
    assert link["album_id"] == 10
