from __future__ import annotations

import sqlite3

import pytest

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
        "release_date_precision": None,
        "release_date_status": "legacy",
        "release_date_display": "2024",
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


def _precision_fixture(
    project_date="2024-08-23",
    project_precision="day",
    original_date="2024-08-23",
    original_precision="day",
    deluxe_date="2024-11-14",
    deluxe_precision="day",
):
    conn = _fixture_conn(project_date)
    conn.execute("ALTER TABLE album_projects ADD COLUMN release_date_precision TEXT")
    conn.execute("UPDATE album_projects SET release_date_precision=?", (project_precision,))
    conn.execute("ALTER TABLE spotify_album_meta ADD COLUMN release_date_precision TEXT")
    conn.execute(
        "UPDATE spotify_album_meta SET release_date=?,release_date_precision=? WHERE spotify_album_id='original'",
        (original_date, original_precision),
    )
    conn.execute(
        "UPDATE spotify_album_meta SET album_name='Fixture Album',release_date=?,release_date_precision=? WHERE spotify_album_id='deluxe'",
        (deluxe_date, deluxe_precision),
    )
    return conn


def test_confirmed_project_day_does_not_mix_more_played_conflicting_version():
    conn = _precision_fixture()
    try:
        meta = resolve_album_detail_meta(
            conn, "Fixture Album", "Fixture Artist", album_project_id=100
        )
        assert (
            meta["release_date"],
            meta["release_date_precision"],
            meta["label"],
            meta["total_tracks"],
            meta["popularity"],
        ) == ("2024-08-23", "day", "Original Label", 12, 80)
    finally:
        conn.close()


@pytest.mark.parametrize(
    "project_date,project_precision,original_date,original_precision,deluxe_date,deluxe_precision,label,total",
    [
        ("2024-08-23", "day", "2024-08-23", "day", "2024", "year", "Original Label", 12),
        ("2024-08-23", "day", "2024-08", "month", "2024-11", "month", "Original Label", 12),
        ("2024-08", "month", "2024-08-23", "day", "2024-11-14", "day", "Original Label", 12),
        ("2024", "year", "2024-08-23", "day", "2024-11-14", "day", "Deluxe Label", 17),
        ("2024-08-23", None, "2024-08-23", "day", "2024-11-14", "day", "Deluxe Label", 17),
        ("2024-08-23", "day", None, None, "2024-11-14", "day", "Original Label", 12),
    ],
)
def test_detail_uses_declared_ranges_and_retains_legacy_uncertainty(
    project_date,
    project_precision,
    original_date,
    original_precision,
    deluxe_date,
    deluxe_precision,
    label,
    total,
):
    c = _precision_fixture(
        project_date,
        project_precision,
        original_date,
        original_precision,
        deluxe_date,
        deluxe_precision,
    )
    try:
        meta = resolve_album_detail_meta(c, "Fixture Album", "Fixture Artist", album_project_id=100)
        assert (meta["label"], meta["total_tracks"]) == (label, total)
        assert (meta["release_date"], meta["release_date_precision"]) == (
            project_date,
            project_precision,
        )
        if project_precision is None:
            assert meta["release_date_display"] == "2024"
    finally:
        c.close()


def test_detail_conflict_only_sources_cannot_supply_mixed_metadata():
    c = _precision_fixture(original_date="2024-07-01")
    try:
        meta = resolve_album_detail_meta(c, "Fixture Album", "Fixture Artist", album_project_id=100)
        assert meta["release_date"] == "2024-08-23" and meta["release_date_precision"] == "day"
        assert not {"label", "total_tracks", "popularity"} & meta.keys()
    finally:
        c.close()


def test_detail_same_day_does_not_override_primary_source_and_name_constraints():
    c = _precision_fixture(
        original_date="2024-08", original_precision="month", deluxe_date="2024-08-23"
    )
    try:
        c.execute(
            "UPDATE spotify_album_meta SET album_name='Unrelated Edition' WHERE spotify_album_id='deluxe'"
        )
        meta = resolve_album_detail_meta(c, "Fixture Album", "Fixture Artist", album_project_id=100)
        assert (meta["label"], meta["total_tracks"]) == ("Original Label", 12)
        c.execute(
            "UPDATE spotify_album_meta SET album_name='Fixture Album' WHERE spotify_album_id='deluxe'"
        )
        c.execute("UPDATE album_spotify_links SET album_id=11 WHERE spotify_album_id='deluxe'")
        c.execute("INSERT INTO album_project_albums VALUES(100,11,'version','deluxe',0)")
        meta = resolve_album_detail_meta(c, "Fixture Album", "Fixture Artist", album_project_id=100)
        assert (meta["label"], meta["total_tracks"]) == ("Original Label", 12)
    finally:
        c.close()
