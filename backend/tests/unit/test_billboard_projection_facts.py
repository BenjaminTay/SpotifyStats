from __future__ import annotations

import copy

import pytest

from backend.api.billboard.projections import (
    all_time_projection,
    number_ones_projection,
    weekly_projection,
)

pytestmark = pytest.mark.unit


def fixture_data():
    row = {
        "billboard_week": "2026-01-02",
        "track_id": 1,
        "track_name": "fixture",
        "artist_name": "a",
        "album_name": "x",
        "rank": 1,
        "play_count": 3,
        "cover_url": "first",
    }
    return {
        "snapshot": {"freshness": "current"},
        "meta": {"all_weeks_desc": ["2026-01-23", "2026-01-16", "2026-01-09", "2026-01-02"]},
        "weekly": [row, {**row, "billboard_week": "2026-01-23", "rank": 2, "cover_url": "later"}],
        "weekly_album": [],
        "weekly_artist": [],
        "power_scores": [
            {
                "track_id": 1,
                "track_name": "fixture",
                "artist_name": "a",
                "weeks_on_chart": 2,
                "peak_position": 1,
                "power_score": 30,
                "power_rank": 1,
                "weeks_top5": 2,
                "weeks_top10": 2,
            }
        ],
        "album_power_scores": [],
        "artist_power_scores": [],
        "track_summary": [
            {"track_id": 1, "weeks_at_peak": 1, "total_chart_plays": 6, "is_debut_no1": True}
        ],
        "album_track_counts": [],
        "artist_track_counts": [],
    }


def test_weekly_keeps_reentry_after_gap_and_previous_complete_week():
    data = fixture_data()
    data["weekly"].append({**data["weekly"][0], "billboard_week": "2026-01-16", "track_id": 2})
    before = copy.deepcopy(data)
    result = weekly_projection(data, "2026-01-23", "tracks")
    assert result["previous"][0]["track_id"] == 2
    assert result["historical"] == [{"track_id": 1, "album_name": "x", "artist_name": "a"}]
    assert result["current"][0] == data["weekly"][1]
    assert weekly_projection(data, "2026-01-02", "tracks")["historical"] == []
    assert weekly_projection(data, "invalid", "tracks")["selected_week"] == "2026-01-23"
    assert data == before


def test_projection_keeps_first_cover_power_rank_and_champion_facts():
    data = fixture_data()
    before = copy.deepcopy(data)
    row = all_time_projection(data, "tracks")["rows"][0]
    assert row["cover_url"] == "first"
    assert row["power_rank"] == 1 and row["total_chart_plays"] == 6 and row["is_debut_no1"]
    champions = number_ones_projection(data)
    assert champions["weekly"] == [data["weekly"][0]]
    assert champions["power_scores"] == [{"track_id": 1, "power_score": 30}]
    assert data == before


def test_selected_week_keeps_the_legacy_rank_order():
    data = fixture_data()
    current = data["weekly"][1]
    data["weekly"].append({**current, "track_id": 2, "rank": 1})
    projected = weekly_projection(data, "2026-01-23", "tracks")
    assert [r["rank"] for r in projected["current"]] == [1, 2]
    assert [r["track_id"] for r in projected["current"]] == [2, 1]
