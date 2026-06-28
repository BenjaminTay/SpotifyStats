from __future__ import annotations

import json

import pytest

from backend.domains.ai_agent.question_intent import parse_question_intent
from backend.services import ai_agent_service

pytestmark = pytest.mark.unit


def test_detects_album_comparison_with_named_entities() -> None:
    intent = parse_question_intent(
        "从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl这两张专辑的喜爱程度哪张专辑更甚？"
    )

    assert intent.task_type == "comparison"
    assert intent.entity_type == "album"
    assert intent.entities == ["GUTS", "The Life of a Showgirl"]
    assert "plays" in intent.requested_metrics
    assert "personal_billboard" in intent.requested_metrics
    assert intent.needs_fairness_note is True


def test_detects_trend_question() -> None:
    intent = parse_question_intent("我最近六个月是不是越来越喜欢 Olivia Rodrigo？")

    assert intent.task_type == "trend"
    assert intent.entity_type == "artist"
    assert intent.entities == ["Olivia Rodrigo"]
    assert intent.time_scope == "last_6_months"
    assert "recent_window" in intent.requested_metrics


def test_ignores_product_names_when_extracting_entities() -> None:
    intent = parse_question_intent("SpotifyStats Billboard 里 GUTS 这张专辑表现如何？")

    assert intent.entities == ["GUTS"]


def test_planner_user_content_includes_question_intent() -> None:
    payload = json.loads(
        ai_agent_service._planner_user_content(
            {
                "question": "GUTS 和 Sour 哪张专辑播放量更高？",
                "conversation_history": [],
            }
        )
    )

    assert payload["question_intent"]["task_type"] == "comparison"
    assert payload["question_intent"]["entity_type"] == "album"
    assert payload["question_intent"]["entities"] == ["GUTS", "Sour"]
