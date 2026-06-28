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


def test_ranking_signals_win_over_generic_which_terms() -> None:
    album_intent = parse_question_intent("我今年最常听哪张专辑？")
    artist_intent = parse_question_intent("哪个艺人播放量最高？")

    assert album_intent.task_type == "ranking"
    assert album_intent.entity_type == "album"
    assert album_intent.time_scope == "this_year"
    assert artist_intent.task_type == "ranking"
    assert artist_intent.entity_type == "artist"
    assert "plays" in artist_intent.requested_metrics


def test_extracts_lowercase_numeric_and_chinese_context_entities() -> None:
    album_intent = parse_question_intent("我对brat和1989这两张专辑哪个更喜欢？")
    artist_intent = parse_question_intent("周杰伦和Taylor Swift这两位艺人哪个播放量更高？")

    assert album_intent.task_type == "comparison"
    assert album_intent.entities == ["brat", "1989"]
    assert artist_intent.task_type == "comparison"
    assert artist_intent.entities == ["周杰伦", "Taylor Swift"]


def test_detects_explicit_year_scope() -> None:
    intent = parse_question_intent("2025年我最常听哪张专辑？")

    assert intent.task_type == "ranking"
    assert intent.time_scope == "year:2025"


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


def test_sanitize_plan_applies_merge_level_to_compare_entities() -> None:
    plan = ai_agent_service._sanitize_plan(
        [
            {
                "tool_name": "compare_entities",
                "params": {"entity_type": "album", "names": ["A", "B"]},
            }
        ],
        {"question": "A 和 B 哪张更高？", "merge_level": 3},
    )

    assert plan[0]["params"]["merge_level"] == 3
