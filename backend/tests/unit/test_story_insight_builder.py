from __future__ import annotations

import pytest

from backend.domains.ai_reports.story_insight_builder import build_story_insights

pytestmark = pytest.mark.unit


def test_story_insights_marks_album_relation_aligned_when_leaders_match():
    context = {
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [
                {
                    "name": "The Life of a Showgirl",
                    "artist": "Taylor Swift",
                    "rank": 1,
                    "weeks_on_chart": 24,
                }
            ]
        },
    }

    insights = build_story_insights(context, {})

    album = insights["album_relation"]
    assert album["mode"] == "aligned"
    assert album["playback_leader"] == "The Life of a Showgirl"
    assert album["chart_leader"] == "The Life of a Showgirl"
    assert "重合" in album["claim"]
    assert "两种不同的喜欢" not in album["interpretation"]
    assert "同一个" in insights["album_axis"]


def test_story_insights_marks_album_relation_divergent_when_leaders_differ():
    context = {
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 1106}],
        "personal_billboard_year_end": {
            "albums": [
                {
                    "name": "光良「回憶裡的瘋狂」巡迴演唱會",
                    "artist": "Michael Wong",
                    "rank": 1,
                    "weeks_on_chart": 32,
                }
            ]
        },
    }

    insights = build_story_insights(context, {})

    album = insights["album_relation"]
    assert album["mode"] == "divergent"
    assert album["playback_leader"] == "The Life of a Showgirl"
    assert album["chart_leader"] == "光良「回憶裡的瘋狂」巡迴演唱會"
    assert "不完全相同" in album["claim"]


def test_story_insights_does_not_force_chinese_language_claim_for_english_artist():
    context = {
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "genre_distribution": {
            "top_genres": [
                {"name": "mandopop", "share": 14.4},
                {"name": "c-pop", "share": 14.4},
            ]
        },
    }

    insights = build_story_insights(context, {})

    second = insights["second_thread"]
    assert second["entity"] == "Olivia Rodrigo"
    assert insights["second_artist"] == "Olivia Rodrigo"
    assert insights["second_thread_kind"] in {"英文/流行", "情绪/叙事线", "artist_contrast"}
    assert "华语" not in second["interpretation"]
    assert "现场感" not in second["interpretation"]
    assert "回望" not in second["interpretation"]


def test_story_insights_sanitizes_highlight_guidance_and_discovery_confidence():
    context = {
        "highlight_day_detail": {
            "date": "2026-04-03",
            "plays": 143,
            "interpretation_guidance": "当天最高单曲播放不高，不要写成重度单曲循环。",
        },
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "plays": 574, "first_date": "2026-03-09"}]
        },
    }
    narrative = {"discovery_thread": {"entity": "Zhang Zhen Yue", "confidence": "high"}}

    insights = build_story_insights(context, narrative)

    assert insights["highlight_day"]["mode"] == "multi_track_dense_day"
    assert "不要写成" not in insights["highlight_day"]["interpretation"]
    assert "重度单曲循环" not in insights["highlight_day"]["interpretation"]
    assert insights["discovery"]["mode"] == "strong_new_thread"
    assert "high" not in insights["discovery"]["interpretation"]


def test_story_insights_exposes_task_one_summary_fields():
    context = {
        "reporting_period": {"year": 2026, "is_partial_year": True, "end_date": "2026-06-23"},
        "hero": {"active_days": 174, "total_plays": 7860, "total_minutes": 29882},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "rank": 1}],
            "tracks": [{"name": "Opalite", "artist": "Taylor Swift", "rank": 1}],
        },
        "genre_distribution": {"top_genres": [{"name": "pop", "share": 32.0}]},
        "highlight_day_detail": {"date": "2026-04-03", "plays": 143},
        "discovery_and_returns": {"new_artists": [{"name": "Zhang Zhen Yue", "plays": 574}]},
    }

    insights = build_story_insights(context, {})

    expected_keys = {
        "year_type",
        "opening_thesis",
        "first_artist",
        "second_artist",
        "second_thread_kind",
        "discovery_artist",
        "artist_axis",
        "top_album",
        "album_axis",
        "peak_day_axis",
        "top_track_axis",
        "style_universe",
        "time_comparison",
        "closing_watchlist",
    }
    assert expected_keys <= insights.keys()
    assert insights["year_type"] == "partial_year"
    assert insights["first_artist"] == "Taylor Swift"
    assert insights["top_album"] == "The Life of a Showgirl"
