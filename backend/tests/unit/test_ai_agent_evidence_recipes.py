from __future__ import annotations

import pytest

from backend.domains.ai_agent.evidence_recipes import recipe_for_frame
from backend.domains.ai_agent.question_frame import build_question_frame
from backend.domains.ai_agent.question_intent import parse_question_intent

pytestmark = pytest.mark.unit


def _recipe(question: str):
    intent = parse_question_intent(question)
    frame = build_question_frame(question, intent)
    return recipe_for_frame(frame)


def test_preference_comparison_recipe_requires_recent_windows_and_compare_tool() -> None:
    recipe = _recipe(
        "从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl这两张专辑的喜爱程度哪张专辑更甚？"
    )

    assert recipe.family == "preference_comparison"
    assert set(recipe.required_axes) >= {"cumulative", "recency", "intensity"}
    assert "personal_billboard" in recipe.required_axes
    assert "fairness" in recipe.conditional_axes
    assert {"tool_name": "compare_entities"} in recipe.required_tool_patterns
    assert {
        "tool_name": "entity_stats",
        "period": "last_6_months",
    } in recipe.required_tool_patterns
    assert {
        "tool_name": "entity_stats",
        "period": "last_4_weeks",
    } in recipe.required_tool_patterns


def test_simple_ranking_recipe_stays_small() -> None:
    recipe = _recipe("2023年我播放量最高的艺人是谁？")

    assert recipe.family == "simple_ranking"
    assert recipe.required_axes == ["ranking"]
    assert {"tool_name": "analysis_charts"} in recipe.required_tool_patterns
    assert recipe.required_context == {
        "entity_type": "artist",
        "time_scope": "year:2023",
        "metric": "plays",
    }
    assert recipe.max_followup_calls == 2


def test_scoped_ranking_recipe_requires_artist_entity_stats() -> None:
    recipe = _recipe("我最喜欢的Ariana Grande的专辑和歌曲是什么")

    assert recipe.family == "scoped_ranking"
    assert recipe.required_axes == ["scope", "cumulative", "ranking"]
    assert recipe.conditional_axes == ["recency"]
    assert {
        "tool_name": "entity_stats",
        "entity": "artist",
        "period": "lifetime",
    } in recipe.required_tool_patterns
    assert {
        "tool_name": "entity_stats",
        "entity": "artist",
        "period": "last_6_months",
    } in recipe.recommended_tool_patterns
    assert recipe.required_context == {
        "scope_entity_type": "artist",
        "scope_entity_name": "Ariana Grande",
        "target_entity_types": ["album", "track"],
        "metric": "plays",
    }


def test_time_of_day_recipe_uses_late_night_tracks() -> None:
    recipe = _recipe("我深夜最爱听什么歌？")

    assert recipe.family == "time_of_day_ranking"
    assert recipe.required_tool_patterns == [
        {"tool_name": "listening_hours", "view": "late_night_tracks"}
    ]


def test_identity_preference_recipe_uses_comparison_and_recent_artist_evidence() -> None:
    recipe = _recipe("Taylor Swift 和 Olivia Rodrigo 谁更像我的本命？")

    assert recipe.family == "identity_preference"
    assert set(recipe.required_axes) >= {"cumulative", "recency", "consistency", "peak"}
    assert {"tool_name": "compare_entities"} in recipe.required_tool_patterns
    assert {
        "tool_name": "entity_stats",
        "period": "last_6_months",
    } in recipe.required_tool_patterns
    assert {"tool_name": "billboard_entity_detail"} in recipe.required_tool_patterns
    assert "fairness" in recipe.conditional_axes


def test_metric_boundary_question_uses_habit_summary_recipe() -> None:
    recipe = _recipe("播放次数最多是否就代表最喜欢？")

    assert recipe.family == "habit_summary"
    assert recipe.required_axes == ["behavior", "cumulative"]
    assert recipe.required_tool_patterns == [
        {"tool_name": "analysis_stats"},
        {"tool_name": "listening_hours"},
    ]


def test_trend_preference_recipe_requires_recent_entity_and_ranking_context() -> None:
    recipe = _recipe("我最近六个月是不是越来越喜欢 Olivia Rodrigo？")

    assert recipe.family == "trend_preference"
    assert recipe.required_axes == ["recency", "trend"]
    assert {
        "tool_name": "entity_stats",
        "period": "last_6_months",
    } in recipe.required_tool_patterns
    assert {
        "tool_name": "analysis_charts",
        "period": "last_6_months",
    } in recipe.required_tool_patterns


def test_period_comparison_recipe_requires_period_and_ranking_evidence() -> None:
    recipe = _recipe("今年和去年口味有什么变化？")

    assert recipe.family == "period_comparison"
    assert recipe.required_axes == ["period", "ranking"]
    assert {"tool_name": "analysis_charts"} in recipe.required_tool_patterns
    assert {"tool_name": "wrapped_yearly"} in recipe.required_tool_patterns


def test_change_explanation_recipe_requires_before_after_context() -> None:
    recipe = _recipe("为什么 GUTS 最近播放量下降了？")

    assert recipe.family == "change_explanation"
    assert set(recipe.required_axes) == {"trend", "recency", "ranking"}
    assert {
        "tool_name": "entity_stats",
        "period": "last_6_months",
    } in recipe.required_tool_patterns
    assert {
        "tool_name": "entity_stats",
        "period": "last_4_weeks",
    } in recipe.required_tool_patterns


def test_entity_detail_with_billboard_requires_billboard_detail() -> None:
    recipe = _recipe("GUTS 的播放和 Billboard 表现如何？")

    assert recipe.family == "entity_detail"
    assert "personal_billboard" in recipe.required_axes
    assert {"tool_name": "entity_stats"} in recipe.required_tool_patterns
    assert {"tool_name": "billboard_entity_detail"} in recipe.required_tool_patterns
