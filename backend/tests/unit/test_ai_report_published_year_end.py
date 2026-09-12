from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from backend.domains.music_search import context as search_context
from backend.domains.music_search import snapshot as search_snapshot
from backend.services import ai_insights_service

pytestmark = pytest.mark.unit


def test_yearly_report_reads_published_year_end_projection(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE music_search_year_end_projection_state (
            snapshot_key TEXT PRIMARY KEY, builder_version TEXT, status TEXT
        );
        CREATE TABLE music_search_year_end_meta (
            snapshot_key TEXT, year INTEGER, coverage_status TEXT,
            is_complete_year INTEGER, observed_weeks INTEGER, expected_weeks INTEGER,
            first_billboard_week TEXT, last_billboard_week TEXT
        );
        CREATE TABLE music_search_entity_year_end (
            snapshot_key TEXT, family TEXT, entity_key TEXT, year INTEGER,
            year_end_rank INTEGER, year_end_score INTEGER, peak_position INTEGER,
            weeks_on_chart INTEGER, weeks_at_no1 INTEGER, chart_plays INTEGER
        );
        CREATE TABLE music_search_index_state (active_generation_id TEXT);
        CREATE TABLE music_search_documents (
            generation_id TEXT, entity_key TEXT, merge_level INTEGER,
            label TEXT, artist_name TEXT
        );
        INSERT INTO music_search_index_state VALUES ('generation');
        INSERT INTO music_search_year_end_projection_state
        VALUES ('snapshot', 'music_search_year_end_projection_v1', 'ready');
        INSERT INTO music_search_year_end_meta
        VALUES ('snapshot', 2025, 'complete', 1, 52, 52, '2025-01-03', '2025-12-26');
        INSERT INTO music_search_entity_year_end VALUES
          ('snapshot', 'track', 'track:1', 2025, 1, 100, 1, 10, 2, 80),
          ('snapshot', 'album', 'album_project:2', 2025, 1, 90, 1, 9, 1, 70),
          ('snapshot', 'artist', 'artist:3', 2025, 1, 120, 1, 12, 3, 100);
        INSERT INTO music_search_documents VALUES
          ('generation', 'track:1', 2, 'Track', 'Artist'),
          ('generation', 'album_project:2', 2, 'Album', 'Artist'),
          ('generation', 'artist:3', 0, 'Artist', 'Artist');
        """
    )
    conn.executemany(
        "INSERT INTO settings(key, value) VALUES (?, ?)",
        [
            ("bb_top_n", "30"),
            ("bb_album_top_n", "20"),
            ("bb_artist_top_n", "20"),
            ("bb_week_start_dow", "4"),
            ("bb_week_start_hour", "0"),
            ("include_compilations", "false"),
        ],
    )
    monkeypatch.setattr(
        search_context,
        "build_music_search_filter_context",
        lambda *_args, **_kwargs: SimpleNamespace(filter_fingerprint="target"),
    )
    monkeypatch.setattr(
        search_snapshot,
        "get_serving_music_search_snapshot",
        lambda *_args, **_kwargs: {
            "snapshot_key": "snapshot",
            "freshness": "last_known_good",
        },
    )

    result = ai_insights_service._load_published_year_end_for_yearly_report(
        conn,
        min_ms=30_000,
        music_only=True,
        year=2025,
        dynamic_threshold=True,
        max_merge_gap_minutes=5,
    )

    assert result is not None
    assert result["meta"]["data_source"] == "published_year_end_projection"
    assert result["meta"]["snapshot_freshness"] == "last_known_good"
    assert result["tracks"][0]["track_name"] == "Track"
    assert result["albums"][0]["album_name"] == "Album"
    assert result["artists"][0]["artist_name"] == "Artist"
    assert result["artists"][0]["play_count_basis"] == "charted_weeks"
    conn.close()
