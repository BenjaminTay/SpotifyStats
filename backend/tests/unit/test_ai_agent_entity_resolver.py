from __future__ import annotations

import sqlite3

import pytest

from backend.domains.ai_agent.entity_resolver import resolve_entities

pytestmark = pytest.mark.unit


def _normalized_conn() -> sqlite3.Connection:
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
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            album_id INTEGER NOT NULL,
            duration_ms INTEGER
        );
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            track_id INTEGER NOT NULL,
            ms_played INTEGER
        );

        INSERT INTO artists(artist_id, artist_name) VALUES
            (1, 'Olivia Rodrigo'),
            (2, 'Taylor Swift');
        INSERT INTO albums(album_id, album_name, artist_id) VALUES
            (10, 'GUTS', 1),
            (11, 'GUTS (spilled)', 1),
            (20, 'The Life of a Showgirl', 2);
        INSERT INTO tracks(track_id, track_name, artist_id, album_id, duration_ms) VALUES
            (100, 'vampire', 1, 10, 219724),
            (101, 'bad idea right?', 1, 10, 184783),
            (102, 'obsessed', 1, 11, 170000),
            (200, 'The Fate of Ophelia', 2, 20, 206000);
        INSERT INTO plays(play_id, track_id, ms_played) VALUES
            (1, 100, 200000),
            (2, 100, 190000),
            (3, 101, 180000),
            (4, 102, 170000),
            (5, 102, 165000),
            (6, 102, 160000),
            (7, 200, 210000);
        """
    )
    return conn


def _simple_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE tracks (
            track_name TEXT,
            artist_name TEXT,
            album_name TEXT,
            ms_played INTEGER
        );
        INSERT INTO tracks(track_name, artist_name, album_name, ms_played) VALUES
            ('vampire', 'Olivia Rodrigo', 'GUTS', 200000),
            ('bad idea right?', 'Olivia Rodrigo', 'GUTS', 180000),
            ('The Fate of Ophelia', 'Taylor Swift', 'The Life of a Showgirl', 210000);
        """
    )
    return conn


def test_resolve_track_on_normalized_schema_returns_ids_and_context() -> None:
    conn = _normalized_conn()

    result = resolve_entities(conn, query="VAMP", entity_type="track", limit=5)

    assert result == {
        "found": True,
        "query": "VAMP",
        "entity_type": "track",
        "candidates": [
            {
                "name": "vampire",
                "entity_type": "track",
                "track_id": 100,
                "artist_name": "Olivia Rodrigo",
                "album_name": "GUTS",
                "play_events": 2,
                "total_ms": 390000,
            }
        ],
    }


def test_resolve_album_on_normalized_schema_prioritizes_exact_name_before_play_count() -> None:
    conn = _normalized_conn()

    result = resolve_entities(conn, query="GUTS", entity_type="album", limit=5)

    assert result["found"] is True
    assert [candidate["name"] for candidate in result["candidates"]] == [
        "GUTS",
        "GUTS (spilled)",
    ]
    assert result["candidates"][0]["album_id"] == 10
    assert result["candidates"][0]["artist_name"] == "Olivia Rodrigo"
    assert result["candidates"][0]["play_events"] == 3
    assert result["candidates"][0]["total_ms"] == 570000


def test_resolve_artist_on_simple_schema_is_case_insensitive() -> None:
    conn = _simple_conn()

    result = resolve_entities(conn, query="olivia", entity_type="artist", limit=5)

    assert result["found"] is True
    assert result["candidates"][0] == {
        "name": "Olivia Rodrigo",
        "entity_type": "artist",
        "artist_name": "Olivia Rodrigo",
        "play_events": 2,
        "total_ms": 380000,
    }


def test_resolve_album_on_simple_schema_returns_album_artist_context() -> None:
    conn = _simple_conn()

    result = resolve_entities(conn, query="showgirl", entity_type="album", limit=5)

    assert result["found"] is True
    assert result["candidates"][0] == {
        "name": "The Life of a Showgirl",
        "entity_type": "album",
        "album_name": "The Life of a Showgirl",
        "artist_name": "Taylor Swift",
        "play_events": 1,
        "total_ms": 210000,
    }


def test_resolve_entities_returns_empty_result_for_blank_query() -> None:
    conn = _normalized_conn()

    result = resolve_entities(conn, query="   ", entity_type="artist", limit=5)

    assert result == {
        "found": False,
        "query": "   ",
        "entity_type": "artist",
        "candidates": [],
    }
