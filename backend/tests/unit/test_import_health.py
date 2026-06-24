from __future__ import annotations

import sqlite3

import pytest

pytestmark = pytest.mark.unit


def test_import_health_report_counts_recent_missing_metadata():
    from backend.domains.metadata.import_health import build_import_health_report

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE plays(
            play_id INTEGER PRIMARY KEY,
            ts_date TEXT,
            content_type TEXT,
            track_id INTEGER,
            source_album_id INTEGER,
            spotify_track_id_at_play TEXT
        );
        CREATE TABLE tracks(track_id INTEGER PRIMARY KEY, spotify_track_id TEXT);
        CREATE TABLE spotify_track_meta(spotify_track_id TEXT PRIMARY KEY, spotify_album_id TEXT);
        CREATE TABLE spotify_album_meta(
            spotify_album_id TEXT PRIMARY KEY,
            album_type TEXT,
            total_tracks INTEGER,
            image_url TEXT
        );
        CREATE TABLE album_spotify_links(album_id INTEGER, spotify_album_id TEXT);
        CREATE TABLE album_project_tracks(track_id INTEGER);
        CREATE TABLE album_project_albums(album_id INTEGER);
        INSERT INTO plays VALUES (1, '2026-06-01', 'audio', 1, 10, NULL);
        INSERT INTO tracks VALUES (1, 'track-a');
        """
    )

    report = build_import_health_report(conn, since_date="2026-05-13")

    assert report["recent_plays"] == 1
    assert report["recent_tracks"] == 1
    assert report["recent_source_albums"] == 1
    assert report["unresolved_recent_tracks"] == 1
    assert report["unresolved_recent_albums"] == 0


def test_import_health_report_counts_project_eligible_album_without_membership():
    from backend.domains.metadata.import_health import build_import_health_report

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE plays(
            play_id INTEGER PRIMARY KEY,
            ts_date TEXT,
            content_type TEXT,
            track_id INTEGER,
            source_album_id INTEGER,
            spotify_track_id_at_play TEXT
        );
        CREATE TABLE tracks(track_id INTEGER PRIMARY KEY, spotify_track_id TEXT);
        CREATE TABLE spotify_track_meta(spotify_track_id TEXT PRIMARY KEY, spotify_album_id TEXT);
        CREATE TABLE spotify_album_meta(
            spotify_album_id TEXT PRIMARY KEY,
            album_type TEXT,
            total_tracks INTEGER,
            image_url TEXT
        );
        CREATE TABLE album_spotify_links(album_id INTEGER, spotify_album_id TEXT);
        CREATE TABLE album_project_tracks(track_id INTEGER);
        CREATE TABLE album_project_albums(album_id INTEGER);
        INSERT INTO plays VALUES (1, '2026-06-01', 'audio', 1, 10, NULL);
        INSERT INTO tracks VALUES (1, 'track-a');
        INSERT INTO spotify_track_meta VALUES ('track-a', 'album-a');
        INSERT INTO spotify_album_meta VALUES ('album-a', 'album', 11, 'cover.jpg');
        INSERT INTO album_spotify_links VALUES (10, 'album-a');
        """
    )

    report = build_import_health_report(conn, since_date="2026-05-13")

    assert report["unresolved_recent_tracks"] == 0
    assert report["unresolved_recent_albums"] == 1


def test_import_health_report_prefers_play_time_spotify_track_id():
    from backend.domains.metadata.import_health import build_import_health_report

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE plays(
            play_id INTEGER PRIMARY KEY,
            ts_date TEXT,
            content_type TEXT,
            track_id INTEGER,
            source_album_id INTEGER,
            spotify_track_id_at_play TEXT
        );
        CREATE TABLE tracks(track_id INTEGER PRIMARY KEY, spotify_track_id TEXT);
        CREATE TABLE spotify_track_meta(spotify_track_id TEXT PRIMARY KEY, spotify_album_id TEXT);
        CREATE TABLE spotify_album_meta(
            spotify_album_id TEXT PRIMARY KEY,
            album_type TEXT,
            total_tracks INTEGER,
            image_url TEXT
        );
        CREATE TABLE album_spotify_links(album_id INTEGER, spotify_album_id TEXT);
        CREATE TABLE album_project_tracks(track_id INTEGER);
        CREATE TABLE album_project_albums(album_id INTEGER);
        INSERT INTO plays VALUES (1, '2026-06-01', 'audio', 1, 10, 'new-track');
        INSERT INTO tracks VALUES (1, 'old-track');
        INSERT INTO spotify_track_meta VALUES ('new-track', 'album-a');
        INSERT INTO spotify_album_meta VALUES ('album-a', 'single', 1, 'cover.jpg');
        INSERT INTO album_spotify_links VALUES (10, 'album-a');
        """
    )

    report = build_import_health_report(conn, since_date="2026-05-13")

    assert report["unresolved_recent_tracks"] == 0
