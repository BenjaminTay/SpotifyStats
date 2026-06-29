from __future__ import annotations

import pytest

from backend.domains.ai_agent.analytical_brief import build_analytical_brief
from backend.domains.ai_agent.evidence_recipes import recipe_for_frame
from backend.domains.ai_agent.question_frame import build_question_frame
from backend.domains.ai_agent.question_intent import parse_question_intent

pytestmark = pytest.mark.unit


def _frame_and_recipe(question: str):
    intent = parse_question_intent(question)
    frame = build_question_frame(question, intent)
    return frame, recipe_for_frame(frame)


def test_preference_comparison_brief_keeps_conflicting_and_recent_winners() -> None:
    question = (
        "从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl"
        "这两张专辑的喜爱程度哪张专辑更甚？"
    )
    frame, recipe = _frame_and_recipe(question)

    brief = build_analytical_brief(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "compare_entities",
                "status": "done",
                "data": {
                    "entity_type": "album",
                    "winner_by_cumulative_plays": "GUTS",
                    "winner_by_total_hours": "The Life of a Showgirl",
                    "winner_by_power_score": "GUTS",
                    "winner_by_intensity": "The Life of a Showgirl",
                    "entities": [
                        {
                            "name": "GUTS",
                            "found": True,
                            "plays": 1749,
                            "hours": 95.6,
                            "power_score": 13566,
                            "weeks_on_chart": 79,
                            "no1_weeks": 11,
                        },
                        {
                            "name": "The Life of a Showgirl",
                            "found": True,
                            "plays": 1637,
                            "hours": 96.0,
                            "power_score": 10629,
                            "weeks_on_chart": 37,
                            "no1_weeks": 14,
                        },
                    ],
                    "fairness_notes": ["对象进入你的播放历史时间不同，累计值和强度值需要分开看。"],
                },
            },
            {
                "tool_name": "entity_stats",
                "status": "done",
                "source_range": "last_6_months",
                "params_summary": "entity=album, album_name=GUTS, period=last_6_months",
                "data": {"summary": {"total_plays": 300}},
            },
            {
                "tool_name": "entity_stats",
                "status": "done",
                "source_range": "last_6_months",
                "params_summary": (
                    "entity=album, album_name=The Life of a Showgirl, period=last_6_months"
                ),
                "data": {"summary": {"total_plays": 1200}},
            },
            {
                "tool_name": "entity_stats",
                "status": "done",
                "source_range": "last_4_weeks",
                "params_summary": "entity=album, album_name=GUTS, period=last_4_weeks",
                "data": {"summary": {"total_plays": 80}},
            },
            {
                "tool_name": "entity_stats",
                "status": "done",
                "source_range": "last_4_weeks",
                "params_summary": (
                    "entity=album, album_name=The Life of a Showgirl, period=last_4_weeks"
                ),
                "data": {"summary": {"total_plays": 40}},
            },
        ],
        coverage={"comparison": {"compare_entities": "found"}},
        evidence_cards=[],
    )

    assert brief["family"] == "preference_comparison"
    assert brief["answer_contract"] == "layered_preference_comparison"
    assert brief["conflict"] is True
    assert brief["dimension_winners"]["cumulative_plays"] == "GUTS"
    assert brief["dimension_winners"]["total_hours"] == "The Life of a Showgirl"
    assert brief["dimension_winners"]["personal_billboard"] == "GUTS"
    assert brief["dimension_winners"]["recent_6_months"] == "The Life of a Showgirl"
    assert brief["dimension_winners"]["recent_4_weeks"] == "GUTS"
    assert brief["dimension_winners"]["intensity"] == "The Life of a Showgirl"
    assert brief["recommended_conclusion"]["long_term"] == "GUTS"
    assert brief["recommended_conclusion"]["recent_intensity"] == "The Life of a Showgirl"
    assert "personal_billboard" in brief["evidence_recipe"]["required_axes"]
    assert "SpotifyStats Billboard 是本地个人榜单，不是外部官方 Billboard" in brief["must_explain"]
    assert "不同口径胜者不一致，不能说单方明显胜出" in brief["must_explain"]
    assert "市场影响力更大" in brief["forbidden_claims"]
    assert "外部官方 Billboard 成绩" in brief["forbidden_claims"]


def test_simple_ranking_brief_stays_concise() -> None:
    frame, recipe = _frame_and_recipe("2023年我播放量最高的艺人是谁？")

    brief = build_analytical_brief(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "analysis_charts",
                "status": "done",
                "source_range": "2023-01-01..2023-12-31",
                "data": {
                    "entity": "artist",
                    "metric": "plays",
                    "rows": [{"rank": 1, "artist_name": "Taylor Swift", "plays": 800}],
                },
            }
        ],
        coverage={},
        evidence_cards=[],
    )

    assert brief["family"] == "simple_ranking"
    assert brief["answer_contract"] == "simple_rank_answer"
    assert brief["conflict"] is False
    assert brief["dimension_winners"] == {}
    assert brief["recommended_conclusion"] == {"top_result": "Taylor Swift"}
    assert brief["must_explain"] == ["说明时间范围和排序指标"]


def test_entity_detail_billboard_brief_protects_local_personal_chart_boundary() -> None:
    frame, recipe = _frame_and_recipe("GUTS 的播放和 Billboard 表现如何？")

    brief = build_analytical_brief(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "entity_stats",
                "status": "done",
                "data": {"summary": {"total_plays": 1749, "total_hours": 95.6}},
            },
            {
                "tool_name": "billboard_entity_detail",
                "status": "done",
                "data": {"power_score": 13566, "peak_position": 1, "weeks_on_chart": 79},
            },
        ],
        coverage={"entities": {"GUTS": {"entity_stats": "found"}}},
        evidence_cards=[],
    )

    assert brief["family"] == "entity_detail"
    assert "personal_billboard" in brief["evidence_recipe"]["required_axes"]
    assert "SpotifyStats Billboard 是本地个人榜单，不是外部官方 Billboard" in brief["must_explain"]
    assert "外部官方 Billboard 成绩" in brief["forbidden_claims"]
    assert "市场影响力更大" in brief["forbidden_claims"]


def test_habit_summary_brief_requires_multiple_evidence_axes() -> None:
    frame, recipe = _frame_and_recipe("播放次数最多是否就代表最喜欢？")

    brief = build_analytical_brief(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "analysis_stats",
                "status": "done",
                "data": {"summary": {"total_plays": 10000}},
            },
            {
                "tool_name": "listening_hours",
                "status": "done",
                "data": {"view": "weekday_weekend", "peak_hour": 22},
            },
        ],
        coverage={},
        evidence_cards=[],
    )

    assert brief["family"] == "habit_summary"
    assert brief["evidence_recipe"]["required_axes"] == ["behavior", "cumulative"]
    assert brief["conflict"] is False
    assert "不能只用单一播放次数判断喜好" in brief["must_explain"]
    assert "忽略行为证据" in brief["forbidden_claims"]


def test_preference_brief_ignores_compare_entities_for_wrong_objects() -> None:
    question = (
        "从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl"
        "这两张专辑的喜爱程度哪张专辑更甚？"
    )
    frame, recipe = _frame_and_recipe(question)

    brief = build_analytical_brief(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "compare_entities",
                "status": "done",
                "params_summary": "entity_type=album, names=['SOUR', 'Red']",
                "data": {
                    "entity_type": "album",
                    "winner_by_cumulative_plays": "SOUR",
                    "winner_by_power_score": "Red",
                    "entities": [
                        {"name": "SOUR", "requested_name": "SOUR", "found": True},
                        {"name": "Red", "requested_name": "Red", "found": True},
                    ],
                },
            }
        ],
        coverage={},
        evidence_cards=[],
    )

    assert brief["dimension_winners"] == {}
    assert brief["recommended_conclusion"] == {
        "long_term": None,
        "recent_intensity": None,
        "single_answer_if_forced": None,
    }


def test_preference_brief_does_not_create_recent_winner_from_partial_window() -> None:
    question = "GUTS 和 The Life of a Showgirl 哪张专辑我更喜欢？"
    frame, recipe = _frame_and_recipe(question)

    brief = build_analytical_brief(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "entity_stats",
                "status": "done",
                "source_range": "last_6_months",
                "params_summary": "entity=album, album_name=GUTS, period=last_6_months",
                "data": {"summary": {"total_plays": 300}},
            }
        ],
        coverage={},
        evidence_cards=[],
    )

    assert "recent_6_months" not in brief["dimension_winners"]
    assert "近期窗口证据未覆盖所有比较对象" in brief["must_explain"]


def test_preference_brief_ignores_recent_stats_with_wrong_entity_type() -> None:
    question = "GUTS 和 The Life of a Showgirl 哪张专辑我更喜欢？"
    frame, recipe = _frame_and_recipe(question)

    brief = build_analytical_brief(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "entity_stats",
                "status": "done",
                "source_range": "last_6_months",
                "params_summary": "entity=track, track_name=GUTS, period=last_6_months",
                "data": {"entity": "track", "summary": {"total_plays": 300}},
            },
            {
                "tool_name": "entity_stats",
                "status": "done",
                "source_range": "last_6_months",
                "params_summary": (
                    "entity=track, track_name=The Life of a Showgirl, period=last_6_months"
                ),
                "data": {"entity": "track", "summary": {"total_plays": 400}},
            },
        ],
        coverage={},
        evidence_cards=[],
    )

    assert "recent_6_months" not in brief["dimension_winners"]


def test_simple_ranking_brief_ignores_wrong_chart_context() -> None:
    frame, recipe = _frame_and_recipe("2023年我播放量最高的艺人是谁？")

    brief = build_analytical_brief(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "analysis_charts",
                "status": "done",
                "source_range": "2023-01-01..2023-12-31",
                "params_summary": "entity=track, metric=plays, period=custom",
                "data": {
                    "entity": "track",
                    "metric": "plays",
                    "period": {
                        "period": "custom",
                        "start_date": "2023-01-01",
                        "end_date": "2023-12-31",
                    },
                    "rows": [{"rank": 1, "track_name": "Cruel Summer", "plays": 300}],
                },
            }
        ],
        coverage={},
        evidence_cards=[],
    )

    assert brief["recommended_conclusion"] == {"top_result": None}


def test_no_conflict_preference_brief_does_not_forbid_all_metrics_aligned() -> None:
    question = "GUTS 和 The Life of a Showgirl 哪张专辑我更喜欢？"
    frame, recipe = _frame_and_recipe(question)

    brief = build_analytical_brief(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "compare_entities",
                "status": "done",
                "params_summary": "entity_type=album, names=['GUTS', 'The Life of a Showgirl']",
                "data": {
                    "entity_type": "album",
                    "winner_by_cumulative_plays": "GUTS",
                    "winner_by_total_hours": "GUTS",
                    "winner_by_power_score": "GUTS",
                    "winner_by_intensity": "GUTS",
                    "entities": [
                        {"name": "GUTS", "requested_name": "GUTS", "found": True},
                        {
                            "name": "The Life of a Showgirl",
                            "requested_name": "The Life of a Showgirl",
                            "found": True,
                        },
                    ],
                },
            }
        ],
        coverage={},
        evidence_cards=[],
    )

    assert brief["conflict"] is False
    assert "所有指标均指向同一对象" not in brief["forbidden_claims"]
    assert "明显单方胜出" not in brief["forbidden_claims"]
