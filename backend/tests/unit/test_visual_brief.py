from __future__ import annotations

import pytest

from backend.domains.ai_reports.visual_brief import build_visual_brief

pytestmark = pytest.mark.unit


def test_visual_brief_selects_required_charts_for_complete_year():
    narrative = {
        "companionship_thread": {"entity": "Taylor Swift"},
        "second_thread": {"entity": "Michael Wong"},
        "discovery_thread": {"entity": "JOLIN", "confidence": "medium"},
        "tensions": [
            {
                "playback_leader": "The Life of a Showgirl",
                "chart_leader": "光良「回憶裡的瘋狂」巡迴演唱會",
            }
        ],
        "life_rhythm": {"active_days": 364},
    }
    coverage = {
        "listening_calendar": True,
        "artist_monthly_trend": True,
        "album_duality_compare": True,
        "highlight_day_timeline": True,
        "genre_language_mix": True,
        "discovery_timeline": True,
        "playback_billboard_matrix": True,
    }

    brief = build_visual_brief(narrative, coverage)

    assert len(brief["chart_specs"]) >= 4
    ids = {chart["id"] for chart in brief["chart_specs"]}
    assert "listening_calendar" in ids
    assert "artist_monthly_trend" in ids
    assert "album_duality_compare" in ids
    assert "highlight_day_timeline" in ids
    assert brief["chart_specs"][1]["entities"] == ["Taylor Swift", "Michael Wong"]


def test_visual_brief_skips_unavailable_charts_and_records_reduced_visuals():
    narrative = {
        "companionship_thread": {"entity": "Taylor Swift"},
        "second_thread": {"entity": ""},
        "discovery_thread": {"entity": "", "confidence": "low"},
        "tensions": [],
        "life_rhythm": {"active_days": 12},
    }
    coverage = {
        "listening_calendar": True,
        "artist_monthly_trend": False,
        "album_duality_compare": False,
        "highlight_day_timeline": False,
        "genre_language_mix": False,
        "discovery_timeline": False,
        "playback_billboard_matrix": False,
    }

    brief = build_visual_brief(narrative, coverage)

    assert brief["fallback_level"] == "reduced_visuals"
    assert [chart["id"] for chart in brief["chart_specs"]] == ["listening_calendar"]


def test_visual_brief_includes_dynamic_outline_sections_from_chart_data():
    narrative = {
        "companionship_thread": {"entity": "Taylor Swift"},
        "second_thread": {"entity": "Olivia Rodrigo"},
        "discovery_thread": {"entity": "Zhang Zhen Yue", "confidence": "medium"},
    }
    coverage = {
        "listening_calendar": True,
        "artist_monthly_trend": True,
        "album_duality_compare": True,
        "highlight_day_timeline": True,
        "genre_language_mix": False,
        "discovery_timeline": True,
        "playback_billboard_matrix": True,
    }
    chart_data = {
        "artist_monthly_trend": {
            "observations": ["Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。"]
        },
        "album_duality_compare": {"relation": "divergent"},
        "discovery_timeline": {"new_artists": [{"name": "Zhang Zhen Yue", "plays": 574}]},
    }

    brief = build_visual_brief(narrative, coverage, chart_data=chart_data)

    roles = [section["role"] for section in brief["outline_sections"]]
    assert "turning_point" in roles
    assert "billboard_divergence" in roles
    assert "discovery" in roles


def test_visual_brief_uses_stage_labels_for_partial_year():
    narrative = {
        "is_partial_year": True,
        "companionship_thread": {"entity": "Taylor Swift"},
        "second_thread": {"entity": "Olivia Rodrigo"},
        "discovery_thread": {"entity": "Zhang Zhen Yue", "confidence": "medium"},
    }
    coverage = {
        "listening_calendar": True,
        "artist_monthly_trend": True,
        "album_duality_compare": True,
        "highlight_day_timeline": True,
        "genre_language_mix": False,
        "discovery_timeline": True,
        "playback_billboard_matrix": True,
    }

    brief = build_visual_brief(narrative, coverage)

    rendered_labels = " ".join(
        " ".join(
            str(chart.get(key) or "")
            for key in ("title", "insight", "narrative_question", "fallback")
        )
        for chart in brief["chart_specs"]
    )
    assert "全年" not in rendered_labels
    assert "年度高光日" not in rendered_labels
    assert "年度声音线索" not in rendered_labels
    assert "当前统计期" in rendered_labels or "阶段" in rendered_labels
