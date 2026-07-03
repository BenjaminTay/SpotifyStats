from __future__ import annotations

import pytest

from backend.domains.ai_reports.narrative_brief import build_narrative_brief

pytestmark = pytest.mark.unit


def _context_2025() -> dict:
    return {
        "reporting_period": {
            "year": 2025,
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "is_partial_year": False,
        },
        "hero": {
            "total_plays": 17567,
            "total_minutes": 68100,
            "active_days": 364,
            "unique_tracks": 2758,
            "unique_artists": 445,
        },
        "top_artists": [
            {"name": "Taylor Swift", "plays": 2629},
            {"name": "Michael Wong", "plays": 2087},
        ],
        "top_tracks": [{"name": "The Fate of Ophelia", "artist": "Taylor Swift", "plays": 190}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 1106}],
        "personal_billboard_year_end": {
            "albums": [
                {
                    "name": "光良「回憶裡的瘋狂」巡迴演唱會",
                    "artist": "Michael Wong",
                    "weeks_on_chart": 32,
                    "rank": 1,
                }
            ],
            "artists": [{"name": "Taylor Swift", "rank": 1, "weeks_on_chart": 50}],
        },
        "genre_distribution": {
            "top_genres": [
                {"name": "mandopop", "share": 16.7},
                {"name": "c-pop", "share": 16.6},
            ],
            "caveat": "Spotify 流派标签可能重叠，百分比不互斥。",
        },
        "discovery_and_returns": {
            "new_artists": [{"name": "JOLIN", "first_date": "2025-05-08", "plays": 108}],
        },
        "highlight_day_detail": {
            "date": "2025-02-14",
            "plays": 154,
            "top_track": {"name": "15 Minutes", "artist": "Sabrina Carpenter", "plays": 9},
            "interpretation_guidance": "多曲目活跃日",
        },
    }


def test_narrative_brief_extracts_story_threads_for_2025():
    brief = build_narrative_brief(_context_2025())

    assert "几乎" in brief["opening_scene"]
    assert brief["companionship_thread"]["entity"] == "Taylor Swift"
    assert "反复回到" in brief["companionship_thread"]["interpretation"]
    assert brief["second_thread"]["entity"] == "Michael Wong"
    assert "另一条" in brief["second_thread"]["interpretation"]
    assert "华语" not in brief["second_thread"]["interpretation"]
    assert brief["discovery_thread"]["entity"] == "JOLIN"
    assert brief["discovery_thread"]["confidence"] in {"medium", "low"}
    assert brief["life_rhythm"]["active_days"] == 364
    assert brief["tensions"][0]["playback_leader"] == "The Life of a Showgirl"
    assert brief["tensions"][0]["chart_leader"] == "光良「回憶裡的瘋狂」巡迴演唱會"


def test_narrative_brief_uses_partial_year_language_for_2026():
    context = _context_2025()
    context["reporting_period"] = {
        "year": 2026,
        "start_date": "2026-01-01",
        "end_date": "2026-06-23",
        "is_partial_year": True,
    }

    brief = build_narrative_brief(context)

    assert "截至 2026-06-23" in brief["main_story"]
    assert "全年定论" not in brief["main_story"]
    assert "下阶段" in brief["closing_direction"]
