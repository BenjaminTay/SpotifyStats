from __future__ import annotations

import sqlite3
from typing import cast

import pytest

from backend.domains.ai_agent import entity_comparison_service
from backend.domains.ai_agent.comparison import summarize_entity_comparison

pytestmark = pytest.mark.unit


def test_comparison_summarizes_cumulative_and_normalized_axes() -> None:
    result = summarize_entity_comparison(
        entity_type="album",
        entities=[
            {
                "name": "GUTS",
                "plays": 1749,
                "hours": 95.6,
                "first_play_date": "2023-09-08",
                "latest_play_date": "2026-06-23",
                "power_score": 13566,
                "power_rank": 4,
                "no1_weeks": 11,
                "weeks_on_chart": 79,
            },
            {
                "name": "The Life of a Showgirl",
                "plays": 1637,
                "hours": 96.0,
                "first_play_date": "2025-10-03",
                "latest_play_date": "2026-06-23",
                "power_score": 10629,
                "power_rank": 9,
                "no1_weeks": 14,
                "weeks_on_chart": 37,
            },
        ],
    )

    assert result["entity_type"] == "album"
    assert result["winner_by_cumulative_plays"] == "GUTS"
    assert result["winner_by_total_hours"] == "The Life of a Showgirl"
    assert result["winner_by_power_score"] == "GUTS"
    assert result["winner_by_power_rank"] == "GUTS"
    assert result["winner_by_intensity"] == "The Life of a Showgirl"
    assert (
        result["entities"][1]["plays_per_chart_week"]
        > result["entities"][0]["plays_per_chart_week"]
    )
    assert any("累计值" in note and "强度值" in note for note in result["fairness_notes"])
    assert any("本地个人 Billboard" in note for note in result["fairness_notes"])


def test_comparison_accepts_track_no1_metric_alias() -> None:
    result = summarize_entity_comparison(
        entity_type="track",
        entities=[
            {
                "name": "vampire",
                "plays": 435,
                "weeks_on_chart": 30,
                "weeks_at_no1": 4,
            },
            {
                "name": "drivers license",
                "plays": 400,
                "weeks_on_chart": 28,
                "weeks_at_no1": 5,
            },
        ],
    )

    assert result["entities"][0]["no1_weeks"] == 4
    assert result["entities"][1]["no1_weeks"] == 5


def test_lifetime_comparison_prefers_exact_published_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(
        entity_comparison_service,
        "_first_candidate",
        lambda conn, *, query, entity_type: {
            "name": query,
            "album_name": query,
            "artist_name": "Artist",
        },
    )
    monkeypatch.setattr(
        entity_comparison_service,
        "load_published_entity_context",
        lambda conn, **kwargs: {
            "name": kwargs["name"],
            "snapshot_freshness": "current",
            "play_events": 123,
            "total_ms": 3_600_000,
            "power_score": 456,
            "power_rank": 7,
            "weeks_at_no1": 2,
            "weeks_on_chart": 9,
            "peak_position": 1,
        },
    )

    rows = entity_comparison_service._published_lifetime_rows(
        cast(sqlite3.Connection, object()),
        entity_type="album",
        names=["Album A"],
        min_ms=30000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=True,
        max_merge_gap_minutes=5,
        merge_level=2,
        include_billboard=True,
        billboard_settings={
            "bb_top_n": 30,
            "bb_album_top_n": 20,
            "bb_artist_top_n": 20,
            "bb_week_start_dow": 4,
            "bb_week_start_hour": 12,
            "include_compilations": False,
        },
    )

    assert rows is not None
    assert rows[0]["plays"] == 123
    assert rows[0]["hours"] == 1.0
    assert rows[0]["power_score"] == 456
    assert rows[0]["evidence_source"] == "published_search_chart_snapshot"


def test_lifetime_comparison_accepts_published_last_known_good(monkeypatch) -> None:
    monkeypatch.setattr(
        entity_comparison_service,
        "_first_candidate",
        lambda conn, *, query, entity_type: {
            "name": query,
            "album_name": query,
            "artist_name": "Artist",
        },
    )
    observed: dict[str, object] = {}

    def published(conn, **kwargs):
        observed.update(kwargs)
        return {
            "name": kwargs["name"],
            "snapshot_freshness": "last_known_good",
            "play_events": 123,
            "total_ms": 3_600_000,
            "power_score": 456,
            "power_rank": 7,
            "weeks_at_no1": 2,
            "weeks_on_chart": 9,
            "peak_position": 1,
        }

    monkeypatch.setattr(entity_comparison_service, "load_published_entity_context", published)

    rows = entity_comparison_service._published_lifetime_rows(
        cast(sqlite3.Connection, object()),
        entity_type="album",
        names=["Album A"],
        min_ms=30000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=True,
        max_merge_gap_minutes=5,
        merge_level=2,
        include_billboard=True,
        billboard_settings={
            "bb_top_n": 30,
            "bb_album_top_n": 20,
            "bb_artist_top_n": 20,
            "bb_week_start_dow": 4,
            "bb_week_start_hour": 12,
            "include_compilations": False,
        },
    )

    assert rows is not None
    assert observed["allow_lkg"] is True
    assert rows[0]["evidence_source"] == "published_search_chart_snapshot_lkg"
    assert rows[0]["snapshot_freshness"] == "last_known_good"
