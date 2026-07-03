from __future__ import annotations

import sqlite3

import pytest

from backend.services.music_search_service import search_music_entities

pytestmark = pytest.mark.unit


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY,
            artist_name TEXT NOT NULL,
            image_path TEXT,
            image_url TEXT
        );
        CREATE TABLE albums (
            album_id INTEGER PRIMARY KEY,
            album_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            image_path TEXT,
            image_url TEXT
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            album_id INTEGER NOT NULL,
            duration_ms INTEGER
        );
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            track_id INTEGER NOT NULL,
            ms_played INTEGER,
            source_album_id INTEGER
        );

        INSERT INTO artists(artist_id, artist_name, image_path, image_url) VALUES
            (1, 'Olivia Rodrigo', NULL, 'https://example.test/olivia.jpg'),
            (2, 'Taylor Swift', NULL, 'https://example.test/taylor.jpg');
        INSERT INTO albums(album_id, album_name, artist_id, image_path, image_url) VALUES
            (10, 'GUTS', 1, NULL, 'https://example.test/guts.jpg'),
            (20, 'folklore', 2, NULL, 'https://example.test/folklore.jpg');
        INSERT INTO tracks(track_id, track_name, artist_id, album_id, duration_ms) VALUES
            (100, 'vampire', 1, 10, 219724),
            (101, 'bad idea right?', 1, 10, 184783),
            (200, 'cardigan', 2, 20, 239560);
        INSERT INTO plays(play_id, track_id, ms_played, source_album_id) VALUES
            (1, 100, 200000, NULL),
            (2, 100, 190000, NULL),
            (3, 101, 180000, NULL),
            (4, 200, 210000, NULL);
        """
    )
    return conn


def test_search_music_entities_returns_grouped_results_with_detail_links() -> None:
    result = search_music_entities(_conn(), query="vamp", limit_per_type=5)

    assert result.query == "vamp"
    assert result.total == 1
    assert [item.label for item in result.tracks] == ["vampire"]
    assert result.tracks[0].kind == "track"
    assert result.tracks[0].href == "/music/tracks/100"
    assert result.tracks[0].subtitle == "Olivia Rodrigo · GUTS"
    assert result.tracks[0].cover_url == "/covers/albums/10.jpg"
    assert result.tracks[0].play_events == 2
    assert result.tracks[0].total_ms == 390000
    assert result.albums == []
    assert result.artists == []


def test_search_music_entities_searches_all_entity_types() -> None:
    result = search_music_entities(_conn(), query="olivia", limit_per_type=5)

    assert result.total == 1
    assert result.tracks == []
    assert result.albums == []
    assert [item.href for item in result.artists] == ["/music/artists/Olivia%20Rodrigo"]
    assert result.artists[0].subtitle == "3 次播放"
    assert result.artists[0].cover_url == "/covers/artists/1.jpg"


def test_search_music_entities_can_filter_entity_types() -> None:
    result = search_music_entities(_conn(), query="gut", kinds=("album",), limit_per_type=5)

    assert result.total == 1
    assert result.tracks == []
    assert result.artists == []
    assert result.albums[0].href == "/music/albums/GUTS?artist=Olivia%20Rodrigo"
    assert result.albums[0].subtitle == "Olivia Rodrigo"
    assert result.albums[0].cover_url == "/covers/albums/10.jpg"


def test_search_music_entities_returns_empty_for_blank_query_without_db_work() -> None:
    result = search_music_entities(_conn(), query="   ", limit_per_type=5)

    assert result.query == "   "
    assert result.total == 0
    assert result.tracks == []
    assert result.albums == []
    assert result.artists == []


def test_search_music_entities_bounds_limit_per_type() -> None:
    result = search_music_entities(_conn(), query="a", limit_per_type=99)

    assert result.limit_per_type == 10
    assert result.total >= 1
