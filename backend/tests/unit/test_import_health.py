from __future__ import annotations

import sqlite3

import pytest

pytestmark = pytest.mark.unit


def test_import_health_report_handles_database_before_first_import():
    from backend.domains.metadata.import_health import build_import_health_report

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    report = build_import_health_report(conn)

    assert report["status"] == "blocked"
    assert report["database"]["sqlite_integrity"] == "missing_plays_table"
    assert report["database"]["play_count"] == 0
    assert report["metadata"]["recent_plays"] == 0


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


def test_import_health_separates_legacy_fk_orphans_from_playback_blockers():
    from backend.domains.metadata.import_health import build_import_health_report

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        PRAGMA foreign_keys = OFF;
        CREATE TABLE artists(artist_id INTEGER PRIMARY KEY);
        CREATE TABLE tracks(
            track_id INTEGER PRIMARY KEY,
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
            spotify_track_id TEXT
        );
        CREATE TABLE albums(
            album_id INTEGER PRIMARY KEY,
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
            album_name TEXT
        );
        CREATE TABLE track_artists(
            track_id INTEGER NOT NULL REFERENCES tracks(track_id),
            artist_id INTEGER NOT NULL REFERENCES artists(artist_id),
            role TEXT NOT NULL
        );
        CREATE TABLE plays(
            play_id INTEGER PRIMARY KEY,
            ts_date TEXT,
            content_type TEXT,
            track_id INTEGER REFERENCES tracks(track_id),
            source_album_id INTEGER REFERENCES albums(album_id),
            spotify_track_id_at_play TEXT
        );
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
        INSERT INTO artists VALUES (1);
        INSERT INTO tracks VALUES (10, 999, 'track-a');
        INSERT INTO albums VALUES (20, 999, 'album-a');
        INSERT INTO track_artists VALUES (10, 999, 'primary');
        INSERT INTO plays VALUES (1, '2026-06-01', 'audio', 10, 20, NULL);
        """
    )

    report = build_import_health_report(conn, since_date="2026-05-13")

    assert report["status"] == "partial"
    assert report["database"]["foreign_key_issue_count"] == 3
    assert report["database"]["foreign_key_issue_breakdown"] == {
        "albums -> artists": 1,
        "track_artists -> artists": 1,
        "tracks -> artists": 1,
    }
    assert report["relationships"]["orphan_play_track_count"] == 0
    assert report["relationships"]["orphan_play_album_count"] == 0
    assert report["blockers"] == []
    artist_issue = next(
        issue for issue in report["issues"] if issue["code"] == "artist_dimension_orphans"
    )
    assert artist_issue["severity"] == "high"
    assert artist_issue["affected_play_count"] == 1
