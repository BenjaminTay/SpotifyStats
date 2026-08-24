from __future__ import annotations

import sqlite3

from backend.domains.metadata.album_detail_meta import resolve_album_detail_meta


def _fixture_conn(project_release_date: str = "2024-08-23") -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY,
            artist_name TEXT NOT NULL
        );
        CREATE TABLE albums (
            album_id INTEGER PRIMARY KEY,
            album_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            album_id INTEGER,
            spotify_track_id TEXT
        );
        CREATE TABLE track_albums (track_id INTEGER, album_id INTEGER);
        CREATE TABLE spotify_album_meta (
            spotify_album_id TEXT PRIMARY KEY,
            album_name TEXT,
            album_type TEXT,
            release_date TEXT,
            popularity INTEGER,
            label TEXT,
            total_tracks INTEGER
        );
        CREATE TABLE album_spotify_links (
            album_id INTEGER,
            spotify_album_id TEXT,
            evidence TEXT,
            confidence REAL,
            play_count INTEGER,
            track_count INTEGER
        );
        CREATE TABLE album_projects (
            project_id INTEGER PRIMARY KEY,
            canonical_name TEXT,
            artist_id INTEGER,
            primary_album_id INTEGER,
            release_date TEXT,
            scope TEXT,
            project_type TEXT,
            is_manual INTEGER DEFAULT 0
        );
        CREATE TABLE album_project_albums (
            project_id INTEGER,
            album_id INTEGER,
            role TEXT,
            source_bucket TEXT,
            inferred INTEGER DEFAULT 0
        );
        INSERT INTO artists VALUES (1, 'Fixture Artist');
        INSERT INTO albums VALUES (10, 'Fixture Album', 1);
        INSERT INTO album_projects VALUES
            (100, 'Fixture Album', 1, 10, 'PROJECT_DATE', 'release', 'album', 0);
        INSERT INTO album_project_albums VALUES
            (100, 10, 'primary', 'original_album', 0);
        INSERT INTO spotify_album_meta VALUES
            ('original', 'Fixture Album', 'album', '2024-08-23', 80, 'Original Label', 12),
            ('deluxe', 'Fixture Album (Deluxe)', 'album', '2025-02-14', 90, 'Deluxe Label', 17),
            ('soundtrack', 'Unrelated Soundtrack', 'album', '2026-05-01', 95, 'Other Label', 30);
        INSERT INTO album_spotify_links VALUES
            (10, 'original', 'play_track_meta', 0.9, 100, 12),
            (10, 'deluxe', 'play_track_meta', 0.9, 900, 17),
            (10, 'soundtrack', 'play_track_meta', 1.0, 1200, 30);
        """.replace("PROJECT_DATE", project_release_date)
    )
    return conn


def test_project_detail_prefers_release_matching_project_over_later_versions():
    conn = _fixture_conn()
    try:
        meta = resolve_album_detail_meta(
            conn,
            "Fixture Album",
            "Fixture Artist",
            merge_level=2,
            album_project_id=100,
        )
    finally:
        conn.close()

    assert meta == {
        "album_type": "album",
        "release_date": "2024-08-23",
        "popularity": 80,
        "label": "Original Label",
        "total_tracks": 12,
    }


def test_project_detail_preserves_governed_date_precision():
    conn = _fixture_conn("2024")
    try:
        meta = resolve_album_detail_meta(
            conn,
            "Fixture Album",
            "Fixture Artist",
            merge_level=3,
            album_project_id=100,
        )
    finally:
        conn.close()

    assert meta is not None
    assert meta["release_date"] == "2024"
    assert meta["total_tracks"] == 12


def test_l1_detail_prefers_exact_physical_album_name():
    conn = _fixture_conn()
    try:
        meta = resolve_album_detail_meta(
            conn,
            "Fixture Album",
            "Fixture Artist",
            merge_level=1,
            album_id=10,
        )
    finally:
        conn.close()

    assert meta is not None
    assert meta["release_date"] == "2024-08-23"
    assert meta["total_tracks"] == 12
