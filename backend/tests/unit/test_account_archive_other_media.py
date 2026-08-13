from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.account import router as account_router
from backend.dependencies import get_conn
from backend.domains.account_archive.context import build_archive_filter_context
from backend.domains.account_archive.other_media import build_archive_other_media
from backend.models.account_archive import ArchiveOtherMediaResponse

pytestmark = pytest.mark.unit


def _media_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO settings VALUES ('min_ms', '30000'), ('merge_enabled', 'True');
        CREATE TABLE saved_tracks (track_uri TEXT PRIMARY KEY, added_date TEXT);
        CREATE TABLE saved_albums (album_uri TEXT PRIMARY KEY);
        CREATE TABLE saved_artists (artist_uri TEXT PRIMARY KEY);
        CREATE TABLE saved_shows (show_uri TEXT PRIMARY KEY);
        CREATE TABLE playlists (playlist_id INTEGER PRIMARY KEY);
        CREATE TABLE playlist_tracks (playlist_id INTEGER, track_uri TEXT);
        CREATE TABLE artists (artist_id INTEGER PRIMARY KEY, artist_name TEXT);
        CREATE TABLE albums (album_id INTEGER PRIMARY KEY, album_name TEXT);
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT,
            artist_id INTEGER,
            album_id INTEGER,
            spotify_track_id TEXT,
            duration_ms INTEGER
        );
        CREATE TABLE spotify_track_meta (
            spotify_track_id TEXT PRIMARY KEY,
            duration_ms INTEGER
        );
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            ts TEXT,
            ms_played INTEGER,
            track_id INTEGER,
            source_album_id INTEGER,
            content_type TEXT,
            ts_date TEXT
        );
        CREATE TABLE podcast_plays (
            id INTEGER PRIMARY KEY,
            end_time TEXT,
            podcast_name TEXT,
            episode_name TEXT,
            ms_played INTEGER,
            play_date TEXT,
            play_hour INTEGER
        );

        INSERT INTO tracks VALUES (1, 'Media Track', 1, 1, 'media', 180000);
        INSERT INTO spotify_track_meta VALUES ('media', 180000);
        INSERT INTO plays VALUES
            (1, '2024-01-01T00:00:20Z', 20000, 1, 1, 'audio', '2024-01-01'),
            (2, '2024-01-01T00:00:40Z', 20000, 1, 1, 'audio', '2024-01-01'),
            (3, '2024-01-02T00:00:40Z', 40000, 1, 1, 'video', '2024-01-02'),
            (4, '2024-01-03T00:00:10Z', 10000, 1, 1, 'video', '2024-01-03');
        INSERT INTO podcast_plays VALUES
            (1, '2024-01-01 10:00', 'Show A', 'Private Episode One', 40000, '2024-01-01', 10),
            (2, '2024-02-01 10:00', 'Show A', 'Private Episode Two', 60000, '2024-02-01', 10),
            (3, '2024-02-02 10:00', 'Show B', 'Private Episode Three', 35000, '2024-02-02', 10),
            (4, '2024-02-03 10:00', 'Show C', 'Short Episode', 20000, '2024-02-03', 10);
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


def test_other_media_uses_shared_audio_video_filters_and_minimal_podcast_facts() -> None:
    conn = _media_conn()
    result = build_archive_other_media(conn, _context(conn))
    conn.close()
    response = ArchiveOtherMediaResponse.model_validate(result)
    serialized = json.dumps(result)

    assert response.status == "available"
    assert response.observation_window.first_play_at == "2024-01-01T00:00:20Z"
    assert response.observation_window.latest_play_at == "2024-01-03T00:00:10Z"
    assert response.podcast.source_rows == 4
    assert response.podcast.effective_events == 3
    assert response.podcast.effective_ms == 135000
    assert response.podcast.unique_shows == 2
    assert response.podcast.active_months == 2
    assert response.podcast.returning_shows == 1
    assert response.podcast.top_shows[0].show_name == "Show A"
    assert response.video.source_rows == 2
    assert response.video.effective_events == 1
    assert response.video.effective_ms == 50000
    assert response.video.first_effective_at == "2024-01-01T23:59:50Z"
    assert response.audio_video_comparison.audio_effective_events == 1
    assert response.audio_video_comparison.audio_effective_ms == 40000
    assert response.audio_video_comparison.video_effective_events == 1
    assert response.audio_video_comparison.video_effective_ms == 50000
    assert "episode_name" not in serialized
    assert "Private Episode" not in serialized
    assert "platform" not in serialized


def test_other_media_revision_changes_with_podcast_content() -> None:
    conn = _media_conn()
    first = ArchiveOtherMediaResponse.model_validate(
        build_archive_other_media(conn, _context(conn))
    )
    conn.execute("UPDATE podcast_plays SET ms_played = ms_played + 1 WHERE id = 1")
    conn.commit()
    second = ArchiveOtherMediaResponse.model_validate(
        build_archive_other_media(conn, _context(conn))
    )
    conn.close()

    assert first.data_revision != second.data_revision


def test_other_media_keeps_unmapped_video_but_does_not_count_it_as_mapped_track() -> None:
    conn = _media_conn()
    conn.execute(
        "INSERT INTO plays VALUES (?, ?, ?, ?, ?, ?, ?)",
        (5, "2024-01-04T00:00:35Z", 35000, 999, 1, "video", "2024-01-04"),
    )
    conn.commit()

    response = ArchiveOtherMediaResponse.model_validate(
        build_archive_other_media(conn, _context(conn))
    )
    conn.close()

    assert response.video.source_rows == 3
    assert response.video.effective_events == 2
    assert response.video.effective_ms == 85000
    assert response.video.unique_tracks == 1


def test_other_media_keeps_video_when_local_track_catalog_is_absent() -> None:
    conn = _media_conn()
    context = _context(conn)
    conn.execute("DROP TABLE tracks")

    response = ArchiveOtherMediaResponse.model_validate(build_archive_other_media(conn, context))
    conn.close()

    assert response.video.source_rows == 2
    assert response.video.effective_events == 1
    assert response.video.effective_ms == 40000
    assert response.video.unique_tracks == 0
    assert response.audio_video_comparison.audio_effective_events == 0


def test_other_media_route_returns_strict_filter_context() -> None:
    conn = _media_conn()
    app = FastAPI()
    app.include_router(account_router, prefix="/api")
    app.dependency_overrides[get_conn] = lambda: conn

    response = TestClient(app).get("/api/account/other-media?merge_enabled=false")
    conn.close()

    assert response.status_code == 200
    assert response.json()["schema_version"] == "account_archive_other_media_v1"
    assert response.json()["filter_context"]["merge_enabled"] is False
    assert response.json()["audio_video_comparison"]["audio_effective_events"] == 0
