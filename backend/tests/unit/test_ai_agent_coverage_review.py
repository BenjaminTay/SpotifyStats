from __future__ import annotations

import pytest

from backend.domains.ai_agent.coverage_review import review_coverage

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
