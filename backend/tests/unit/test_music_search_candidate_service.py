from __future__ import annotations

import sqlite3

import pytest

from backend.services.music_search_candidate_service import search_music_candidates

pytestmark = pytest.mark.unit


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE artists (artist_id INTEGER PRIMARY KEY, artist_name TEXT NOT NULL);
        CREATE TABLE albums (
            album_id INTEGER PRIMARY KEY,
            album_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL
        );
        CREATE TABLE tracks (
            track_id INTEGER PRIMARY KEY,
            track_name TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            album_id INTEGER
        );
        CREATE TABLE plays (
            play_id INTEGER PRIMARY KEY,
            track_id INTEGER NOT NULL,
            ms_played INTEGER,
            source_album_id INTEGER
        );
        INSERT INTO artists VALUES (1, 'Taylor Swift');
        INSERT INTO albums VALUES (10, 'folklore', 1);
        INSERT INTO tracks VALUES (100, 'cardigan', 1, 10);
        INSERT INTO plays VALUES (1, 100, 200000, 10);
        """
    )
    return conn


def test_current_candidates_fail_closed_without_exact_snapshot(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("candidate path must not load filtered plays or Billboard")

    monkeypatch.setattr(
        "backend.services.music_search_service.load_period_plays",
        forbidden,
    )
    monkeypatch.setattr(
        "backend.services.music_search_service.compute_summaries_staged",
        forbidden,
    )
    monkeypatch.setattr(
        "backend.services.music_search_service.compute_power_scores_staged",
        forbidden,
    )
    monkeypatch.setattr(
        "backend.services.music_search_service.compute_weekly_data",
        forbidden,
    )

    result = search_music_candidates(_conn(), query="card", eligibility="current")

    assert result.snapshot_status == "unavailable"
    assert result.total == 0
    assert result.tracks == []

    mismatched_builder = search_music_candidates(
        _conn(),
        query="card",
        eligibility="current",
        snapshot_status="ready",
        snapshot_key=None,
    )
    assert mismatched_builder.snapshot_status == "unavailable"
    assert mismatched_builder.total == 0
    assert mismatched_builder.tracks == []


def test_private_any_local_returns_clickable_candidate_without_context_metrics(
    monkeypatch,
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("candidate path must not load filtered plays or Billboard")

    monkeypatch.setattr(
        "backend.services.music_search_service.load_period_plays",
        forbidden,
    )
    monkeypatch.setattr(
        "backend.services.music_search_service.compute_summaries_staged",
        forbidden,
    )
    monkeypatch.setattr(
        "backend.services.music_search_service.compute_power_scores_staged",
        forbidden,
    )
    monkeypatch.setattr(
        "backend.services.music_search_service.compute_weekly_data",
        forbidden,
    )

    result = search_music_candidates(
        _conn(),
        query="  CARD  ",
        kinds=("track",),
        eligibility="any_local",
    )

    assert result.snapshot_status == "ready"
    assert result.normalized_query == "card"
    assert result.total == 1
    item = result.tracks[0]
    assert item.entity_key == "track:100"
    assert item.href == "/music/tracks/100"
    assert item.match_field == "label"
    assert item.match_quality == "prefix"
    payload = item.model_dump()
    assert "play_events" not in payload
    assert "total_ms" not in payload
    assert "chart" not in payload


def test_latin_single_character_is_gated_before_resolver(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("short query must not reach resolver")

    monkeypatch.setattr(
        "backend.services.music_search_candidate_service.resolve_entities",
        forbidden,
    )

    result = search_music_candidates(_conn(), query="a", eligibility="any_local")

    assert result.snapshot_status == "ready"
    assert result.total == 0
