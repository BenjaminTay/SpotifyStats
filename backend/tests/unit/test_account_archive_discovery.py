from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.account import router as account_router
from backend.dependencies import get_conn
from backend.domains.account_archive.context import build_archive_filter_context
from backend.domains.account_archive.discovery import (
    _assign_bursts,
    _deduplicate_events,
    build_archive_discovery,
)
from backend.models.account_archive import ArchiveDiscoveryResponse

pytestmark = pytest.mark.unit


def _discovery_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO settings VALUES ('min_ms', '30000'), ('merge_enabled', 'True');
        CREATE TABLE saved_tracks (
            track_uri TEXT PRIMARY KEY,
            track_name TEXT,
            artist_name TEXT,
            album_name TEXT,
            added_date TEXT,
            spotify_track_id TEXT,
            added_date_source TEXT
        );
        CREATE TABLE saved_albums (album_uri TEXT PRIMARY KEY);
        CREATE TABLE saved_artists (artist_uri TEXT PRIMARY KEY);
        CREATE TABLE saved_shows (show_uri TEXT PRIMARY KEY);
        CREATE TABLE playlists (playlist_id INTEGER PRIMARY KEY);
        CREATE TABLE playlist_tracks (playlist_id INTEGER, track_uri TEXT);
        CREATE TABLE artists (artist_id INTEGER PRIMARY KEY, artist_name TEXT);
        CREATE TABLE albums (
            album_id INTEGER PRIMARY KEY,
            album_name TEXT,
            artist_id INTEGER,
            release_date TEXT,
            image_path TEXT,
            image_url TEXT
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT,
            artist_id INTEGER,
            album_id INTEGER,
            spotify_track_uri TEXT,
            spotify_track_id TEXT
        );
        CREATE TABLE spotify_track_meta (
            spotify_track_id TEXT PRIMARY KEY,
            duration_ms INTEGER,
            spotify_album_id TEXT
        );
        CREATE TABLE spotify_album_meta (
            spotify_album_id TEXT PRIMARY KEY,
            release_date TEXT
        );
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            ts TEXT,
            ms_played INTEGER,
            track_id INTEGER,
            source_album_id INTEGER,
            ts_date TEXT
        );
        CREATE TABLE track_groups (
            group_id INTEGER PRIMARY KEY,
            canonical_name TEXT,
            primary_track_id INTEGER,
            scope TEXT,
            parent_group_id INTEGER
        );
        CREATE TABLE track_group_members (group_id INTEGER, track_id INTEGER);
        CREATE TABLE search_queries (
            id INTEGER PRIMARY KEY,
            query_text TEXT NOT NULL,
            search_time_utc TEXT NOT NULL,
            search_date TEXT NOT NULL,
            search_hour INTEGER NOT NULL,
            search_dow INTEGER NOT NULL,
            platform TEXT,
            interaction_uri TEXT
        );

        INSERT INTO artists VALUES (1, 'Discovery Artist');
        INSERT INTO albums VALUES
            (1, 'Discovery Album', 1, '2024-01-01', '/tmp/cover.jpg', NULL);
        INSERT INTO tracks VALUES
            (1, 'Found Track', 1, 1, 'spotify:track:found', 'found'),
            (2, 'Later Track', 1, 1, 'spotify:track:later', 'later');
        INSERT INTO spotify_track_meta VALUES
            ('found', 180000, 'album'), ('later', 180000, 'album');
        INSERT INTO spotify_album_meta VALUES ('album', '2024-01-01');
        INSERT INTO saved_tracks VALUES
            ('spotify:track:found', 'Found Track', 'Discovery Artist', 'Discovery Album',
             '2024-01-05T00:00:00Z', 'found', 'legacy'),
            ('spotify:track:later', 'Later Track', 'Discovery Artist', 'Discovery Album',
             '2024-01-02T00:00:05Z', 'later', 'legacy');
        INSERT INTO plays VALUES
            (1, '2024-01-01T00:11:00Z', 60000, 1, 1, '2024-01-01'),
            (2, '2024-01-02T00:01:10Z', 60000, 2, 1, '2024-01-02'),
            (3, '2024-02-01T00:03:00Z', 180000, 2, 1, '2024-02-01');
        INSERT INTO search_queries VALUES
            (1, 'A', '2024-01-01T00:00:00.000Z[UTC]', '2024-01-01', 8, 0, '', ''),
            (2, 'ａ ', '2024-01-01T00:00:00.200Z[UTC]', '2024-01-01', 8, 0, '', ''),
            (3, 'A', '2024-01-01T00:00:00.200Z[UTC]', '2024-01-01', 8, 0, '', ''),
            (4, 'A', '2024-01-01T00:00:02.000Z[UTC]', '2024-01-01', 8, 0,
             'OSX_ARM64', 'spotify:track:found'),
            (5, 'B', '2024-01-01T01:00:00.000Z[UTC]', '2024-01-01', 9, 0,
             'OSX_ARM64', 'spotify:track:missing'),
            (6, 'C', '2024-01-02T02:00:00.000Z[UTC]', '2024-01-02', 10, 1,
             'IPHONE', 'spotify:artist:someone'),
            (7, 'D', '2024-01-02T00:00:00.000Z[UTC]', '2024-01-02', 8, 1,
             'IPHONE', 'spotify:track:later');
        """
    )
    conn.commit()
    return conn


def _context(conn: sqlite3.Connection):
    return build_archive_filter_context(
        conn,
        {
            "min_ms": None,
            "merge_enabled": None,
            "dynamic_threshold": True,
            "max_merge_gap_minutes": None,
            "merge_level": 2,
        },
    )


def test_discovery_deduplicates_unicode_queries_and_uses_five_minute_bursts() -> None:
    rows = [
        {
            "id": 1,
            "query_text": "Ａ ",
            "search_time_utc": "2024-01-01T00:00:00Z",
            "platform": "",
            "interaction_uri": "",
        },
        {
            "id": 2,
            "query_text": "a",
            "search_time_utc": "2024-01-01T00:00:00Z",
            "platform": "",
            "interaction_uri": "",
        },
        {
            "id": 3,
            "query_text": "b",
            "search_time_utc": "2024-01-01T00:05:00Z",
            "platform": "",
            "interaction_uri": "",
        },
        {
            "id": 4,
            "query_text": "c",
            "search_time_utc": "2024-01-01T00:10:00.001Z",
            "platform": "",
            "interaction_uri": "",
        },
    ]

    events, invalid = _deduplicate_events(rows)
    bursts = _assign_bursts(events)

    assert invalid == 0
    assert len(events) == 3
    assert events[0]["normalized_query"] == "a"
    assert [len(burst) for burst in bursts] == [2, 1]


def test_discovery_builds_count_only_funnel_without_raw_queries() -> None:
    conn = _discovery_conn()
    result = build_archive_discovery(conn, _context(conn))
    conn.close()
    response = ArchiveDiscoveryResponse.model_validate(result)
    serialized = json.dumps(result)

    assert response.status == "partial"
    assert response.coverage.raw_search_rows == 7
    assert response.coverage.deduplicated_search_rows == 6
    assert response.coverage.unique_normalized_queries == 4
    assert response.coverage.search_bursts == 4
    assert response.coverage.interaction_records == 4
    assert response.coverage.interaction_bursts == 4
    assert response.interaction_types.track == 3
    assert response.interaction_types.artist == 1
    assert response.funnel.display_status == "count_only"
    assert response.funnel.track_interaction_bursts == 3
    assert response.funnel.mapped_track_interaction_bursts == 2
    assert response.funnel.played_within_1h_bursts == 2
    assert response.funnel.currently_saved_within_30d_bursts == 1
    assert sum(item.bursts for item in response.weekday_distribution) == 4
    assert sum(item.bursts for item in response.hour_distribution) == 4
    assert len(response.observed_saved_examples) == 1
    assert "query_text" not in serialized
    assert "normalized_query" not in serialized
    assert "interaction_uri" not in serialized
    assert "spotify:track:" not in serialized


def test_discovery_revision_changes_when_search_content_changes() -> None:
    conn = _discovery_conn()
    first = ArchiveDiscoveryResponse.model_validate(build_archive_discovery(conn, _context(conn)))
    conn.execute("UPDATE search_queries SET query_text = 'Changed' WHERE id = 1")
    conn.commit()
    second = ArchiveDiscoveryResponse.model_validate(build_archive_discovery(conn, _context(conn)))
    conn.close()

    assert first.data_revision != second.data_revision


def test_discovery_route_returns_strict_contract_and_filter_context() -> None:
    conn = _discovery_conn()
    app = FastAPI()
    app.include_router(account_router, prefix="/api")
    app.dependency_overrides[get_conn] = lambda: conn

    response = TestClient(app).get("/api/account/discovery?merge_level=2")
    conn.close()

    assert response.status_code == 200
    assert response.json()["schema_version"] == "account_archive_discovery_v1"
    assert response.json()["filter_context"]["merge_level"] == 2
    assert response.json()["funnel"]["display_status"] == "count_only"
