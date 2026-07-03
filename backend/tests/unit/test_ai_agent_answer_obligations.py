from __future__ import annotations

import pytest

from backend.domains.ai_agent.answer_critic import critique_answer
from backend.domains.ai_agent.answer_obligations import build_answer_obligations
from backend.domains.ai_agent.question_frame import build_question_frame
from backend.domains.ai_agent.question_intent import parse_question_intent
from backend.domains.ai_agent.temporal_context import apply_temporal_guard, build_temporal_context

pytestmark = pytest.mark.unit


def test_relative_time_answer_obligations_include_data_cutoff_when_data_lags_today() -> None:
    question = "去年夏天我最常听什么类型的音乐？"
    frame = build_question_frame(question, parse_question_intent(question))
    temporal_context = build_temporal_context(
        {"question_time": "2026-07-03T09:00:00+08:00"},
        data_range={"data_start_date": "2022-07-01", "data_end_date": "2026-06-23"},
    )
    _, temporal_guard = apply_temporal_guard(question, temporal_context, [])

    obligations = build_answer_obligations(
        question=question,
        question_frame=frame.model_dump(),
        temporal_context=temporal_context,
        temporal_guard=temporal_guard,
        evidence_sufficiency={"sufficient": True},
    )

    assert any(item["kind"] == "data_cutoff" for item in obligations)
    cutoff = next(item for item in obligations if item["kind"] == "data_cutoff")
    assert "2026-06-23" in cutoff["required_values"]


def test_critic_requires_obligation_values_when_present() -> None:
    payload = {
        "answer_obligations": [
            {
                "kind": "data_cutoff",
                "required_tokens_any": ["数据截止", "截至", "只覆盖到"],
                "required_values": ["2026-06-23"],
            }
        ]
    }

    missing = critique_answer("去年夏天你最常听流行音乐。", payload)
    satisfied = critique_answer("去年夏天你最常听流行音乐；数据截止到 2026-06-23。", payload)

    assert missing["ok"] is False
    assert any("data_cutoff" in issue for issue in missing["issues"])
    assert satisfied["ok"] is True


def test_insufficient_evidence_adds_limitation_obligation() -> None:
    frame = build_question_frame(
        "GUTS 和 Showgirl 哪张更喜欢？", parse_question_intent("GUTS 和 Showgirl 哪张更喜欢？")
    )

    obligations = build_answer_obligations(
        question="GUTS 和 Showgirl 哪张更喜欢？",
        question_frame=frame.model_dump(),
        temporal_context={"today": "2026-07-03", "latest_play_date": "2026-06-23"},
        temporal_guard={},
        evidence_sufficiency={"sufficient": False},
    )

    limitation = next(item for item in obligations if item["kind"] == "evidence_limitation")
    assert "证据不足" in limitation["required_tokens_any"]


def test_safe_readonly_refusal_is_not_penalized_as_insufficient_evidence() -> None:
    critique = critique_answer(
        "我不能删除你的播放记录；当前 AI 问答只允许只读查询分析。",
        {
            "question_frame": {"family": "safety_boundary"},
            "evidence_sufficiency": {"sufficient": False},
            "answer_obligations": [
                {
                    "kind": "readonly_refusal",
                    "required_tokens_any": ["只读", "不能", "无法"],
                    "required_values": [],
                }
            ],
        },
    )

    assert critique["ok"] is True
    assert critique["issues"] == []
