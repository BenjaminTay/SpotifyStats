from __future__ import annotations

import pytest

from backend.domains.ai_agent.question_frame import build_question_frame
from backend.domains.ai_agent.question_intent import parse_question_intent

pytestmark = pytest.mark.unit


def _frame(question: str):
    return build_question_frame(question, parse_question_intent(question))


def test_album_preference_comparison_uses_layered_contract() -> None:
    frame = _frame(
        "从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl这两张专辑的喜爱程度哪张专辑更甚？"
    )

    assert frame.family == "preference_comparison"
    assert frame.task_type == "comparison"
    assert frame.entity_type == "album"
    assert frame.entities == ["GUTS", "The Life of a Showgirl"]
    assert frame.answer_contract == "layered_preference_comparison"
    assert frame.requires_layered_conclusion is True
    assert set(frame.analysis_axes) >= {
        "cumulative",
        "recency",
        "intensity",
        "personal_billboard",
        "fairness",
    }


def test_late_night_song_question_uses_time_of_day_family() -> None:
    frame = _frame("我深夜最爱听什么歌？")

    assert frame.family == "time_of_day_ranking"
    assert frame.entity_type == "track"
    assert frame.answer_contract == "time_of_day_answer"
    assert frame.analysis_axes == ["time_of_day", "ranking"]


def test_2023_top_artist_stays_simple_ranking() -> None:
    frame = _frame("2023年我播放量最高的艺人是谁？")

    assert frame.family == "simple_ranking"
    assert frame.answer_contract == "simple_rank_answer"
    assert frame.time_scope == "year:2023"
    assert frame.requires_layered_conclusion is False


def test_artist_catalog_favorite_album_and_track_uses_scoped_ranking() -> None:
    frame = _frame("我最喜欢的Ariana Grande的专辑和歌曲是什么")

    assert frame.family == "scoped_ranking"
    assert frame.task_type == "ranking"
    assert frame.entity_type == "artist"
    assert frame.entities == ["Ariana Grande"]
    assert frame.answer_contract == "scoped_ranking_answer"
    assert frame.analysis_axes == ["scope", "cumulative", "ranking", "recency"]
    assert frame.requires_layered_conclusion is True


def test_identity_question_requires_layered_axes() -> None:
    frame = _frame("Taylor Swift 和 Olivia Rodrigo 谁更像我的本命？")

    assert frame.family == "identity_preference"
    assert frame.entity_type == "artist"
    assert frame.answer_contract == "identity_preference_answer"
    assert set(frame.analysis_axes) >= {"cumulative", "recency", "consistency", "peak"}


def test_metric_boundary_question_is_habit_summary_not_simple_ranking() -> None:
    frame = _frame("播放次数最多是否就代表最喜欢？")

    assert frame.family == "habit_summary"
    assert frame.answer_contract == "habit_summary_answer"
    assert frame.requires_layered_conclusion is False


@pytest.mark.parametrize(
    ("question", "family", "contract"),
    [
        ("我的收藏夹有什么特点？", "account_collection", "account_collection_answer"),
        ("我最常搜索什么？", "search_behavior", "search_behavior_answer"),
        ("社区动态里最近谁最热？", "community_lookup", "community_lookup_answer"),
        ("帮我删除一条播放记录", "safety_boundary", "readonly_refusal_answer"),
    ],
)
def test_domain_questions_use_specific_families(
    question: str,
    family: str,
    contract: str,
) -> None:
    frame = _frame(question)

    assert frame.family == family
    assert frame.answer_contract == contract
