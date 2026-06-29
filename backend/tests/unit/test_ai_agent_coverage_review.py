from __future__ import annotations

import pytest

from backend.domains.ai_agent.coverage_review import (
    review_coverage,
    review_evidence_sufficiency,
)
from backend.domains.ai_agent.evidence_recipes import recipe_for_frame
from backend.domains.ai_agent.question_frame import build_question_frame
from backend.domains.ai_agent.question_intent import parse_question_intent

pytestmark = pytest.mark.unit


def test_review_requests_missing_billboard_for_album_comparison() -> None:
    review = review_coverage(
        question_intent={
            "task_type": "comparison",
            "entity_type": "album",
            "entities": ["GUTS", "The Life of a Showgirl"],
            "requested_metrics": ["plays", "personal_billboard"],
        },
        coverage={
            "entities": {
                "GUTS": {"entity_stats": "found", "billboard_entity_detail": "found"},
                "The Life of a Showgirl": {"entity_stats": "found"},
            }
        },
    )

    assert review["sufficient"] is False
    assert review["followup_tool_calls"] == [
        {
            "tool_name": "billboard_entity_detail",
            "params": {"entity": "album", "album_name": "The Life of a Showgirl"},
        }
    ]
    assert any("The Life of a Showgirl" in reason for reason in review["reasons"])


def test_review_accepts_complete_comparison_coverage() -> None:
    review = review_coverage(
        question_intent={
            "task_type": "comparison",
            "entity_type": "album",
            "entities": ["GUTS", "The Life of a Showgirl"],
            "requested_metrics": ["plays", "personal_billboard"],
        },
        coverage={
            "entities": {
                "GUTS": {"entity_stats": "found", "billboard_entity_detail": "found"},
                "The Life of a Showgirl": {
                    "entity_stats": "found",
                    "billboard_entity_detail": "found",
                },
            }
        },
    )

    assert review["sufficient"] is True
    assert review["reasons"] == []
    assert review["followup_tool_calls"] == []


def test_review_accepts_found_compare_entities_without_redundant_followups() -> None:
    review = review_coverage(
        question_intent={
            "task_type": "comparison",
            "entity_type": "album",
            "entities": ["GUTS", "The Life of a Showgirl"],
            "requested_metrics": ["plays", "personal_billboard"],
        },
        coverage={
            "comparison": {"compare_entities": "found"},
            "entities": {
                "GUTS": {"compare_entities": "found"},
                "The Life of a Showgirl": {"compare_entities": "found"},
            },
        },
    )

    assert review["sufficient"] is True
    assert review["reasons"] == []
    assert review["followup_tool_calls"] == []


def test_review_does_not_accept_compare_entities_when_requested_entity_missing() -> None:
    review = review_coverage(
        question_intent={
            "task_type": "comparison",
            "entity_type": "album",
            "entities": ["GUTS", "The Life of a Showgirl", "SOUR"],
            "requested_metrics": ["plays", "personal_billboard"],
        },
        coverage={
            "comparison": {"compare_entities": "found"},
            "entities": {
                "GUTS": {"compare_entities": "found"},
                "The Life of a Showgirl": {"compare_entities": "found"},
            },
        },
    )

    assert review["sufficient"] is False
    assert {
        "tool_name": "entity_stats",
        "params": {"entity": "album", "album_name": "SOUR"},
    } in review["followup_tool_calls"]


def test_review_requests_compare_entities_for_track_comparison_gap() -> None:
    review = review_coverage(
        question_intent={
            "task_type": "comparison",
            "entity_type": "track",
            "entities": ["vampire", "drivers license"],
            "requested_metrics": ["plays", "personal_billboard"],
        },
        coverage={"entities": {}},
    )

    assert review["sufficient"] is False
    assert review["followup_tool_calls"] == [
        {
            "tool_name": "compare_entities",
            "params": {"entity_type": "track", "names": ["vampire", "drivers license"]},
        }
    ]


def _frame_and_recipe(question: str):
    intent = parse_question_intent(question)
    frame = build_question_frame(question, intent)
    return frame, recipe_for_frame(frame)


def test_preference_comparison_requests_recent_followups_when_lifetime_compare_exists() -> None:
    question = (
        "从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl"
        "这两张专辑的喜爱程度哪张专辑更甚？"
    )
    frame, recipe = _frame_and_recipe(question)
    tool_results = [
        {
            "tool_name": "compare_entities",
            "status": "done",
            "source_range": "comparison",
            "params_summary": "entity_type=album, names=['GUTS', 'The Life of a Showgirl']",
            "data": {
                "entity_type": "album",
                "winner_by_cumulative_plays": "GUTS",
                "winner_by_power_score": "GUTS",
                "winner_by_intensity": "The Life of a Showgirl",
                "entities": [
                    {
                        "name": "GUTS",
                        "found": True,
                        "plays": 1749,
                        "power_score": 13566,
                    },
                    {
                        "name": "The Life of a Showgirl",
                        "found": True,
                        "plays": 1637,
                        "power_score": 10629,
                    },
                ],
                "fairness_notes": ["对象进入你的播放历史时间不同，累计值和强度值需要分开看。"],
            },
        }
    ]

    review = review_evidence_sufficiency(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=tool_results,
        coverage={"comparison": {"compare_entities": "found"}},
    )

    assert review["sufficient"] is False
    assert review["axis_coverage"]["cumulative"] == "covered"
    assert review["axis_coverage"]["recency"] == "missing"
    assert review["axis_coverage"]["intensity"] == "covered"
    assert review["axis_coverage"]["personal_billboard"] == "covered"
    assert any(
        call["params"]["period"] == "last_6_months" for call in review["followup_tool_calls"]
    )
    assert any(call["params"]["period"] == "last_4_weeks" for call in review["followup_tool_calls"])


def test_preference_comparison_keeps_missing_entity_recent_followups() -> None:
    question = (
        "从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl"
        "这两张专辑的喜爱程度哪张专辑更甚？"
    )
    frame, recipe = _frame_and_recipe(question)

    review = review_evidence_sufficiency(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "compare_entities",
                "status": "done",
                "source_range": "comparison",
                "data": {
                    "winner_by_cumulative_plays": "GUTS",
                    "winner_by_power_score": "GUTS",
                    "winner_by_intensity": "The Life of a Showgirl",
                },
            },
            {
                "tool_name": "entity_stats",
                "status": "done",
                "source_range": "last_6_months",
                "params_summary": "entity=album, album_name=GUTS, period=last_6_months",
                "data": {"period": {"period": "last_6_months"}, "found": True},
            },
        ],
        coverage={"comparison": {"compare_entities": "found"}},
    )

    assert {
        "tool_name": "entity_stats",
        "params": {
            "entity": "album",
            "album_name": "The Life of a Showgirl",
            "period": "last_6_months",
        },
    } in review["followup_tool_calls"]


def test_time_of_day_ranking_is_sufficient_with_late_night_tool() -> None:
    frame, recipe = _frame_and_recipe("我深夜最爱听什么歌？")

    review = review_evidence_sufficiency(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "listening_hours",
                "status": "done",
                "source_range": "late_night_tracks",
                "params_summary": "view=late_night_tracks",
                "data": {"view": "late_night_tracks", "items": {"tracks": []}},
            }
        ],
        coverage={},
    )

    assert review["sufficient"] is True
    assert review["axis_coverage"]["time_of_day"] == "covered"
    assert review["axis_coverage"]["ranking"] == "covered"


def test_habit_summary_requests_stats_and_listening_hours_from_recipe() -> None:
    frame, recipe = _frame_and_recipe("播放次数最多是否就代表最喜欢？")

    review = review_evidence_sufficiency(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[],
        coverage={},
    )

    assert review["sufficient"] is False
    assert review["axis_coverage"]["behavior"] == "missing"
    assert review["axis_coverage"]["cumulative"] == "missing"
    assert [call["tool_name"] for call in review["followup_tool_calls"]] == [
        "analysis_stats",
        "listening_hours",
    ]


def test_simple_ranking_followup_uses_recipe_required_context() -> None:
    frame, recipe = _frame_and_recipe("2023年我播放量最高的艺人是谁？")

    review = review_evidence_sufficiency(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[],
        coverage={},
    )

    assert review["sufficient"] is False
    assert review["axis_coverage"]["ranking"] == "missing"
    assert review["followup_tool_calls"] == [
        {
            "tool_name": "analysis_charts",
            "params": {
                "entity": "artist",
                "metric": "plays",
                "period": "custom",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
                "limit": 10,
            },
        }
    ]


def test_simple_ranking_wrong_entity_chart_does_not_satisfy_required_context() -> None:
    frame, recipe = _frame_and_recipe("2023年我播放量最高的艺人是谁？")

    review = review_evidence_sufficiency(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "analysis_charts",
                "status": "done",
                "source_range": "2023",
                "params_summary": "entity=track, metric=plays, period=custom",
                "data": {
                    "entity": "track",
                    "metric": "plays",
                    "period": {
                        "period": "custom",
                        "start_date": "2023-01-01",
                        "end_date": "2023-12-31",
                    },
                },
            }
        ],
        coverage={},
    )

    assert review["sufficient"] is False
    assert review["axis_coverage"]["ranking"] == "missing"
    assert review["followup_tool_calls"] == [
        {
            "tool_name": "analysis_charts",
            "params": {
                "entity": "artist",
                "metric": "plays",
                "period": "custom",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
                "limit": 10,
            },
        }
    ]


def test_simple_ranking_late_night_tool_does_not_cover_general_ranking_axis() -> None:
    frame, recipe = _frame_and_recipe("2023年我播放量最高的艺人是谁？")

    review = review_evidence_sufficiency(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "listening_hours",
                "status": "done",
                "source_range": "late_night_tracks",
                "params_summary": "view=late_night_tracks",
                "data": {"view": "late_night_tracks", "items": {"tracks": []}},
            }
        ],
        coverage={},
    )

    assert review["sufficient"] is False
    assert review["axis_coverage"]["ranking"] == "missing"


def test_scoped_ranking_rejects_global_album_chart_without_artist_scope() -> None:
    frame, recipe = _frame_and_recipe("我最喜欢的Ariana Grande的专辑和歌曲是什么")

    review = review_evidence_sufficiency(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "analysis_charts",
                "status": "done",
                "source_range": "2022-07-01..2026-06-23",
                "params_summary": "entity=album, metric=plays, period=lifetime, limit=10",
                "data": {
                    "entity": "album",
                    "metric": "plays",
                    "rows": [{"rank": 1, "album_name": "Midnights", "plays": 2559}],
                    "period": {"period": "lifetime"},
                },
            }
        ],
        coverage={},
    )

    assert review["sufficient"] is False
    assert review["axis_coverage"]["scope"] == "missing"
    assert review["axis_coverage"]["ranking"] == "missing"
    assert {
        "tool_name": "entity_stats",
        "params": {
            "entity": "artist",
            "artist_name": "Ariana Grande",
            "period": "lifetime",
        },
    } in review["followup_tool_calls"]


def test_scoped_ranking_accepts_artist_stats_with_album_and_track_rankings() -> None:
    frame, recipe = _frame_and_recipe("我最喜欢的Ariana Grande的专辑和歌曲是什么")

    review = review_evidence_sufficiency(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "entity_stats",
                "status": "done",
                "source_range": "2022-07-01..2026-06-23",
                "params_summary": "entity=artist, artist_name=Ariana Grande, period=lifetime",
                "data": {
                    "found": True,
                    "period": {"period": "lifetime"},
                    "summary": {"total_plays": 2153, "total_hours": 115.7},
                    "top_albums": [{"rank": 1, "album_name": "eternal sunshine", "plays": 997}],
                    "top_tracks": [{"rank": 1, "track_name": "Santa Tell Me", "plays": 145}],
                },
            }
        ],
        coverage={},
    )

    assert review["sufficient"] is True
    assert review["axis_coverage"]["scope"] == "covered"
    assert review["axis_coverage"]["cumulative"] == "covered"
    assert review["axis_coverage"]["ranking"] == "covered"


def test_compare_entities_for_wrong_objects_does_not_satisfy_preference_comparison() -> None:
    question = (
        "从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl"
        "这两张专辑的喜爱程度哪张专辑更甚？"
    )
    frame, recipe = _frame_and_recipe(question)

    review = review_evidence_sufficiency(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "compare_entities",
                "status": "done",
                "source_range": "comparison",
                "params_summary": "entity_type=album, names=['SOUR', 'Red']",
                "data": {
                    "entity_type": "album",
                    "winner_by_cumulative_plays": "SOUR",
                    "winner_by_power_score": "Red",
                    "winner_by_intensity": "SOUR",
                    "entities": [
                        {"name": "SOUR", "requested_name": "SOUR", "found": True},
                        {"name": "Red", "requested_name": "Red", "found": True},
                    ],
                },
            },
            {
                "tool_name": "entity_stats",
                "status": "done",
                "source_range": "last_6_months",
                "params_summary": "entity=album, album_name=GUTS, period=last_6_months",
                "data": {"period": {"period": "last_6_months"}, "found": True},
            },
            {
                "tool_name": "entity_stats",
                "status": "done",
                "source_range": "last_6_months",
                "params_summary": (
                    "entity=album, album_name=The Life of a Showgirl, period=last_6_months"
                ),
                "data": {"period": {"period": "last_6_months"}, "found": True},
            },
            {
                "tool_name": "entity_stats",
                "status": "done",
                "source_range": "last_4_weeks",
                "params_summary": "entity=album, album_name=GUTS, period=last_4_weeks",
                "data": {"period": {"period": "last_4_weeks"}, "found": True},
            },
            {
                "tool_name": "entity_stats",
                "status": "done",
                "source_range": "last_4_weeks",
                "params_summary": (
                    "entity=album, album_name=The Life of a Showgirl, period=last_4_weeks"
                ),
                "data": {"period": {"period": "last_4_weeks"}, "found": True},
            },
        ],
        coverage={},
    )

    assert review["sufficient"] is False
    assert {
        "tool_name": "compare_entities",
        "params": {
            "entity_type": "album",
            "names": ["GUTS", "The Life of a Showgirl"],
        },
    } in review["followup_tool_calls"]


def test_required_partial_axes_keep_identity_preference_insufficient() -> None:
    frame, recipe = _frame_and_recipe("Taylor Swift 和 Olivia Rodrigo 谁更像我的本命？")

    review = review_evidence_sufficiency(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[
            {
                "tool_name": "compare_entities",
                "status": "done",
                "source_range": "comparison",
                "params_summary": "entity_type=artist, names=['Taylor Swift', 'Olivia Rodrigo']",
                "data": {
                    "entity_type": "artist",
                    "winner_by_cumulative_plays": "Taylor Swift",
                    "winner_by_power_score": "Olivia Rodrigo",
                    "entities": [
                        {"name": "Taylor Swift", "requested_name": "Taylor Swift", "found": True},
                        {
                            "name": "Olivia Rodrigo",
                            "requested_name": "Olivia Rodrigo",
                            "found": True,
                        },
                    ],
                },
            },
            {
                "tool_name": "entity_stats",
                "status": "done",
                "source_range": "last_6_months",
                "params_summary": "entity=artist, artist_name=Taylor Swift, period=last_6_months",
                "data": {"period": {"period": "last_6_months"}, "found": True},
            },
            {
                "tool_name": "entity_stats",
                "status": "done",
                "source_range": "last_6_months",
                "params_summary": "entity=artist, artist_name=Olivia Rodrigo, period=last_6_months",
                "data": {"period": {"period": "last_6_months"}, "found": True},
            },
            {
                "tool_name": "billboard_entity_detail",
                "status": "done",
                "source_range": "all_years",
                "params_summary": "entity=artist, artist_name=Taylor Swift",
                "data": {"found": True},
            },
            {
                "tool_name": "billboard_entity_detail",
                "status": "done",
                "source_range": "all_years",
                "params_summary": "entity=artist, artist_name=Olivia Rodrigo",
                "data": {"found": True},
            },
        ],
        coverage={},
    )

    assert review["axis_coverage"]["consistency"] == "partial"
    assert review["axis_coverage"]["peak"] == "partial"
    assert review["sufficient"] is False


def test_preference_comparison_cold_start_followups_cover_compare_and_all_recent_windows() -> None:
    question = (
        "从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl"
        "这两张专辑的喜爱程度哪张专辑更甚？"
    )
    frame, recipe = _frame_and_recipe(question)

    review = review_evidence_sufficiency(
        question_frame=frame.model_dump(),
        evidence_recipe=recipe.model_dump(),
        tool_results=[],
        coverage={},
    )

    assert review["sufficient"] is False
    assert review["followup_tool_calls"] == [
        {
            "tool_name": "compare_entities",
            "params": {
                "entity_type": "album",
                "names": ["GUTS", "The Life of a Showgirl"],
            },
        },
        {
            "tool_name": "entity_stats",
            "params": {"entity": "album", "album_name": "GUTS", "period": "last_6_months"},
        },
        {
            "tool_name": "entity_stats",
            "params": {
                "entity": "album",
                "album_name": "The Life of a Showgirl",
                "period": "last_6_months",
            },
        },
        {
            "tool_name": "entity_stats",
            "params": {"entity": "album", "album_name": "GUTS", "period": "last_4_weeks"},
        },
        {
            "tool_name": "entity_stats",
            "params": {
                "entity": "album",
                "album_name": "The Life of a Showgirl",
                "period": "last_4_weeks",
            },
        },
    ]
