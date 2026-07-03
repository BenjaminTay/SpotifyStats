from __future__ import annotations

import pytest

from backend.domains.ai_reports.narrative_quality import evaluate_visual_yearly_quality

pytestmark = pytest.mark.unit


def test_quality_rejects_adjacent_repeated_core_facts():
    artifact = {
        "sections": [
            {
                "heading": "一份仍在展开的音乐年记",
                "prose": (
                    "播放记录里有 174 个活跃日、7860 次播放和约 498 小时聆听。"
                    "174 个活跃日、7860 次播放和约 498 小时聆听构成时间侧证据。"
                ),
                "chart_refs": ["listening_calendar"],
            }
        ],
        "chart_specs": [{"id": "listening_calendar"}],
        "chart_data": {"listening_calendar": {"summary": "活跃 174 天"}},
    }

    result = evaluate_visual_yearly_quality(artifact)

    assert result["ok"] is False
    assert "repeated_core_fact" in result["issue_codes"]


def test_quality_rejects_chart_section_without_concrete_observation():
    artifact = {
        "sections": [
            {
                "heading": "Taylor Swift，你反复回到的声音",
                "prose": "这条声音反复出现在你的年度路径里，形成稳定陪伴。",
                "chart_refs": ["artist_monthly_trend"],
            }
        ],
        "chart_specs": [{"id": "artist_monthly_trend"}],
        "chart_data": {
            "artist_monthly_trend": {
                "observations": [
                    "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。"
                ]
            }
        },
    }

    result = evaluate_visual_yearly_quality(artifact)

    assert result["ok"] is False
    assert "missing_chart_observation" in result["issue_codes"]


def test_quality_accepts_interpreted_chart_reading_without_exact_echo():
    observation = "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。"
    artifact = {
        "sections": [
            {
                "heading": "六月，第二条线变得更清楚",
                "prose": (
                    "到了 2026-06，Olivia Rodrigo 的月度播放已经越过 Taylor Swift。"
                    "这说明第二条线不是平均铺开，而是在上半年尾声突然变亮。"
                ),
                "chart_refs": ["artist_monthly_trend"],
            }
        ],
        "chart_specs": [{"id": "artist_monthly_trend"}],
        "chart_data": {"artist_monthly_trend": {"observations": [observation]}},
    }

    result = evaluate_visual_yearly_quality(artifact)

    assert result["ok"] is True
    assert result["issue_codes"] == []


def test_quality_rejects_exact_chart_echo_without_interpretation():
    observation = "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。"
    artifact = {
        "sections": [
            {
                "heading": "六月，第二条线变得更清楚",
                "prose": observation,
                "chart_refs": ["artist_monthly_trend"],
            }
        ],
        "chart_specs": [{"id": "artist_monthly_trend"}],
        "chart_data": {"artist_monthly_trend": {"observations": [observation]}},
    }

    result = evaluate_visual_yearly_quality(artifact)

    assert result["ok"] is False
    assert "chart_prose_echo" in result["issue_codes"]
    assert "missing_chart_observation" not in result["issue_codes"]


def test_quality_uses_editorial_plan_for_fact_home_and_language_budget():
    artifact = {
        "sections": [
            {
                "role": "opening",
                "heading": "序章",
                "prose": "The Life of a Showgirl 让播放量和个人 Billboard 指向同一个重心。入口入口入口",
                "chart_refs": [],
            },
            {
                "role": "closing",
                "heading": "收束",
                "prose": "The Life of a Showgirl 让播放量和个人 Billboard 指向同一个重心。",
                "chart_refs": [],
            },
        ],
        "chart_data": {},
    }
    editorial_plan = {
        "facts": [
            {
                "id": "album_alignment",
                "claim": "The Life of a Showgirl 让播放量和个人 Billboard 指向同一个重心",
                "home_section_role": "album_story",
            }
        ],
        "language_budget": {"入口": 1},
    }

    result = evaluate_visual_yearly_quality(artifact, editorial_plan)

    assert result["ok"] is False
    assert "duplicate_fact_home" in result["issue_codes"]
    assert "section_role_violation" in result["issue_codes"]
    assert "generic_language_overuse" in result["issue_codes"]


def test_quality_rejects_life_claim_and_data_listing_when_editorial_plan_present():
    artifact = {
        "sections": [
            {
                "role": "rhythm",
                "heading": "节奏",
                "prose": (
                    "2026-04 有 143 次，2026-05 有 120 次。"
                    "Taylor Swift 有 1115 次，Olivia Rodrigo 有 769 次。"
                    "Opalite 有 88 次，另一首歌有 66 次。"
                    "这些播放一定发生在考试和失眠里。"
                ),
                "chart_refs": [],
            }
        ],
        "chart_data": {},
    }

    result = evaluate_visual_yearly_quality(artifact, {"facts": [], "language_budget": {}})

    assert result["ok"] is False
    assert "unsupported_life_claim" in result["issue_codes"]
    assert "data_listing_without_interpretation" in result["issue_codes"]
