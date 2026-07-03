from __future__ import annotations

import pytest

from backend.domains.ai_reports.editorial_plan import build_editorial_plan

pytestmark = pytest.mark.unit


def _context() -> dict:
    return {
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_plays": 7860, "total_minutes": 29882},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "rank": 1, "weeks_on_chart": 24}],
            "tracks": [{"name": "Opalite", "rank": 1, "weeks_on_chart": 19}],
            "artists": [{"name": "Taylor Swift", "rank": 1, "weeks_on_chart": 25}],
        },
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "first_date": "2026-03-09", "plays": 574}]
        },
        "highlight_day_detail": {"date": "2026-04-03", "plays": 143},
        "chart_data": {
            "artist_monthly_trend": {
                "observations": [
                    "Olivia Rodrigo 在 2026-05 达到 105 次，超过 Taylor Swift 的 67 次。"
                ]
            },
            "playback_billboard_matrix": {
                "observations": ["Opalite 是单曲里兼具高播放和长在榜的核心作品。"]
            },
            "highlight_day_timeline": {
                "observations": ["2026-04-03 是播放最密集的一天，共 143 次。"]
            },
        },
    }


def _narrative() -> dict:
    return {
        "main_story": "Taylor Swift 是稳定回访对象，Olivia Rodrigo 形成阶段性上升。",
        "opening_scene": "这是一份截至 2026-06-23 的阶段性音乐年记。",
    }


def _insights() -> dict:
    return {
        "first_artist": "Taylor Swift",
        "second_thread": {"entity": "Olivia Rodrigo", "claim": "Olivia Rodrigo 形成第二条线索"},
        "album_relation": {
            "mode": "aligned",
            "playback_leader": "The Life of a Showgirl",
            "chart_leader": "The Life of a Showgirl",
            "claim": "The Life of a Showgirl 让播放量和个人 Billboard 指向同一个重心",
            "interpretation": "播放热度与榜单长留重合。",
        },
        "highlight_day": {
            "date": "2026-04-03",
            "plays": 143,
            "interpretation": "这一天更像许多歌曲密集经过。",
        },
        "discovery": {
            "entity": "Zhang Zhen Yue",
            "plays": 574,
            "first_date": "2026-03-09",
            "interpretation": "已经形成清晰的新支线。",
        },
    }


def _visual() -> dict:
    return {
        "outline_sections": [
            {"role": "opening", "reason": "建立时间范围"},
            {"role": "main_artist", "reason": "解释主线艺人"},
            {"role": "turning_point", "reason": "解释月度转折"},
            {"role": "album_story", "reason": "解释专辑关系"},
            {"role": "highlight_day", "reason": "解释高光日"},
            {"role": "discovery", "reason": "解释新发现"},
            {"role": "closing", "reason": "收束年度画像"},
        ]
    }


def test_editorial_plan_assigns_each_fact_to_one_home_section():
    plan = build_editorial_plan(_context(), _narrative(), _insights(), _visual())

    fact_ids = [fact.id for fact in plan.facts]
    assert len(fact_ids) == len(set(fact_ids))
    assert all(fact.home_section_role for fact in plan.facts)

    home_counts = {}
    for fact in plan.facts:
        home_counts.setdefault(fact.id, set()).add(fact.home_section_role)

    assert all(len(homes) == 1 for homes in home_counts.values())
    assert any(fact.home_section_role == "turning_point" for fact in plan.facts)
    assert any(fact.home_section_role == "album_story" for fact in plan.facts)


def test_editorial_plan_uses_visual_outline_roles_and_owns_chart_observations():
    plan = build_editorial_plan(_context(), _narrative(), _insights(), _visual())

    roles = [section.role for section in plan.sections]
    assert roles[:4] == ["opening", "main_artist", "turning_point", "album_story"]

    turning = next(section for section in plan.sections if section.role == "turning_point")
    owned = {fact.id for fact in plan.facts if fact.id in turning.owned_fact_ids}
    assert "artist_monthly_trend_primary_observation" in owned

    opening = next(section for section in plan.sections if section.role == "opening")
    assert "artist_monthly_trend_primary_observation" not in opening.owned_fact_ids


def test_editorial_plan_exposes_language_budget_and_metadata():
    plan = build_editorial_plan(_context(), _narrative(), _insights(), _visual())
    payload = plan.to_dict()

    assert payload["version"] == "yearly_editorial_v1"
    assert payload["language_budget"]["入口"] <= 2
    assert payload["language_budget"]["陪伴"] <= 4
    assert payload["metadata"]["fact_count"] == len(plan.facts)
    assert payload["metadata"]["section_roles"] == [section.role for section in plan.sections]
