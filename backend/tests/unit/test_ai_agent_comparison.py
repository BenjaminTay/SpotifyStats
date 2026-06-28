from __future__ import annotations

import pytest

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
