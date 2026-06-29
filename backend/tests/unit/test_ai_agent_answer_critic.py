from __future__ import annotations

import pytest

from backend.domains.ai_agent.answer_critic import critique_answer

pytestmark = pytest.mark.unit


def test_critic_rejects_external_billboard_market_claim_without_personal_scope() -> None:
    critique = critique_answer(
        answer="GUTS 的 Billboard 市场影响力和商业成绩更强，所以你更喜欢它。",
        final_payload={
            "coverage": {"entities": {"GUTS": {"billboard_entity_detail": "found"}}},
            "evidence_cards": [
                {
                    "title": "GUTS 个人榜单表现",
                    "limitations": [
                        "SpotifyStats Billboard 是本地个人榜单，不是外部官方 Billboard"
                    ],
                }
            ],
        },
    )

    assert critique["ok"] is False
    assert "外部官方 Billboard" in critique["issues"][0]


def test_critic_accepts_personal_billboard_language() -> None:
    critique = critique_answer(
        answer="在你的个人 Billboard 口径里，GUTS 的 Power Score 更高。",
        final_payload={
            "coverage": {"entities": {"GUTS": {"billboard_entity_detail": "found"}}},
            "evidence_cards": [],
        },
    )

    assert critique["ok"] is True
    assert critique["issues"] == []


def test_critic_allows_markdown_table_output() -> None:
    critique = critique_answer(
        answer=(
            "| 维度 | GUTS | The Life of a Showgirl |\n"
            "| --- | --- | --- |\n"
            "| 播放次数 | 1749 | 1637 |"
        ),
        final_payload={"coverage": {}, "evidence_cards": []},
    )

    assert critique["ok"] is True
    assert critique["issues"] == []


def test_critic_rejects_later_external_billboard_claim_even_with_personal_scope_elsewhere() -> None:
    critique = critique_answer(
        answer=(
            "在你的个人 Billboard 口径里，GUTS 的 Power Score 更高。"
            "但官方 Billboard 市场影响力也说明它商业成绩更强。"
        ),
        final_payload={
            "coverage": {"entities": {"GUTS": {"billboard_entity_detail": "found"}}},
            "evidence_cards": [],
        },
    )

    assert critique["ok"] is False
    assert any("外部官方 Billboard" in issue for issue in critique["issues"])


def test_critic_allows_negated_external_billboard_clarification() -> None:
    critique = critique_answer(
        answer="这不是官方 Billboard，也不能说明市场成绩；这里只看你的个人 Billboard。",
        final_payload={
            "coverage": {"entities": {"GUTS": {"billboard_entity_detail": "found"}}},
            "evidence_cards": [],
        },
    )

    assert critique["ok"] is True
    assert critique["issues"] == []


def test_critic_rejects_external_market_claim_after_distant_negation() -> None:
    critique = critique_answer(
        answer="这不是官方 Billboard 但市场影响力更强。",
        final_payload={
            "coverage": {"entities": {"GUTS": {"billboard_entity_detail": "found"}}},
            "evidence_cards": [],
        },
    )

    assert critique["ok"] is False
    assert any("外部官方 Billboard" in issue for issue in critique["issues"])


def test_critic_rejects_repeated_external_token_after_negated_first_mention() -> None:
    critique = critique_answer(
        answer="这不是官方 Billboard，但官方 Billboard 表现更强。",
        final_payload={
            "coverage": {"entities": {"GUTS": {"billboard_entity_detail": "found"}}},
            "evidence_cards": [],
        },
    )

    assert critique["ok"] is False
    assert any("外部官方 Billboard" in issue for issue in critique["issues"])


@pytest.mark.parametrize(
    ("answer", "coverage"),
    [
        (
            "GUTS 数据不足，无法比较。",
            {"entities": {"GUTS": {"entity_stats": "found"}}},
        ),
        (
            "目前缺少完整结果，未查询到足够信息，无法比较这两张专辑。",
            {
                "entities": {
                    "GUTS": {"compare_entities": "found"},
                    "The Life of a Showgirl": {"compare_entities": "found"},
                },
                "comparison": {"compare_entities": "found"},
            },
        ),
    ],
)
def test_critic_rejects_missing_data_claim_when_coverage_is_found(
    answer: str,
    coverage: dict[str, object],
) -> None:
    critique = critique_answer(
        answer=answer,
        final_payload={"coverage": coverage, "evidence_cards": []},
    )

    assert critique["ok"] is False
    assert any("found" in issue or "已查到" in issue for issue in critique["issues"])


def test_critic_allows_missing_claim_for_partial_compare_missing_entity() -> None:
    critique = critique_answer(
        answer="SOUR 数据不足，无法比较它和 GUTS。",
        final_payload={
            "coverage": {
                "comparison": {"compare_entities": "missing"},
                "entities": {
                    "GUTS": {"compare_entities": "found"},
                    "SOUR": {"compare_entities": "missing"},
                },
            },
            "evidence_cards": [],
        },
    )

    assert critique["ok"] is True
    assert critique["issues"] == []


def test_critic_rejects_analytical_brief_forbidden_claims() -> None:
    critique = critique_answer(
        answer="GUTS 在你的记录里市场影响力更大，所以它是更成功的专辑。",
        final_payload={
            "coverage": {},
            "evidence_cards": [],
            "analytical_brief": {"forbidden_claims": ["市场影响力更大", "外部官方 Billboard 成绩"]},
        },
    )

    assert critique["ok"] is False
    assert any("forbidden_claims" in issue for issue in critique["issues"])


def test_critic_allows_negated_analytical_brief_forbidden_claim() -> None:
    critique = critique_answer(
        answer="这不是市场影响力更大，只是你的个人 Billboard 表现更强。",
        final_payload={
            "coverage": {},
            "evidence_cards": [],
            "analytical_brief": {"forbidden_claims": ["市场影响力更大"]},
        },
    )

    assert critique["ok"] is True
    assert critique["issues"] == []


def test_critic_rejects_single_winner_language_when_brief_has_conflict() -> None:
    critique = critique_answer(
        answer="这些指标均指向 GUTS，毫无疑问是 GUTS 单方胜出。",
        final_payload={
            "coverage": {},
            "evidence_cards": [],
            "analytical_brief": {
                "conflict": True,
                "must_explain": ["不同口径胜者不一致，不能说单方明显胜出"],
            },
        },
    )

    assert critique["ok"] is False
    assert any("conflict" in issue for issue in critique["issues"])


def test_critic_rejects_mild_single_sided_answer_when_brief_has_conflict() -> None:
    critique = critique_answer(
        answer="从播放次数看，GUTS 更占优，所以结论是 GUTS。",
        final_payload={
            "coverage": {},
            "evidence_cards": [],
            "analytical_brief": {
                "conflict": True,
                "dimension_winners": {
                    "cumulative_plays": "GUTS",
                    "intensity": "The Life of a Showgirl",
                },
                "must_explain": ["不同口径胜者不一致，不能说单方明显胜出"],
            },
        },
    )

    assert critique["ok"] is False
    assert any("多口径" in issue or "不同口径" in issue for issue in critique["issues"])


def test_critic_accepts_layered_answer_when_brief_has_conflict() -> None:
    critique = critique_answer(
        answer=(
            "从累计播放次数看，GUTS 更占优；从近期强度看，"
            "The Life of a Showgirl 更突出，所以需要分口径判断。"
        ),
        final_payload={
            "coverage": {},
            "evidence_cards": [],
            "analytical_brief": {
                "conflict": True,
                "dimension_winners": {
                    "cumulative_plays": "GUTS",
                    "intensity": "The Life of a Showgirl",
                },
                "must_explain": ["不同口径胜者不一致，不能说单方明显胜出"],
            },
        },
    )

    assert critique["ok"] is True
    assert critique["issues"] == []


def test_critic_rejects_conflict_overclaim_even_when_sentence_has_distant_negation() -> None:
    critique = critique_answer(
        answer="这不是所有维度都完整，但 GUTS 明显胜出。",
        final_payload={
            "coverage": {},
            "evidence_cards": [],
            "analytical_brief": {
                "conflict": True,
                "must_explain": ["不同口径胜者不一致，不能说单方明显胜出"],
            },
        },
    )

    assert critique["ok"] is False
    assert any("conflict" in issue for issue in critique["issues"])


def test_critic_requires_local_personal_billboard_boundary_from_must_explain() -> None:
    critique = critique_answer(
        answer="GUTS 的 Billboard 表现更强，所以更能代表你的偏好。",
        final_payload={
            "coverage": {},
            "evidence_cards": [],
            "analytical_brief": {
                "must_explain": ["SpotifyStats Billboard 是本地个人榜单，不是外部官方 Billboard"]
            },
        },
    )

    assert critique["ok"] is False
    assert any("本地个人榜单" in issue for issue in critique["issues"])


def test_critic_requires_metric_layering_when_must_explain_mentions_conflicting_winners() -> None:
    critique = critique_answer(
        answer="结论是 GUTS 更占优。",
        final_payload={
            "coverage": {},
            "evidence_cards": [],
            "analytical_brief": {"must_explain": ["不同口径胜者不一致，不能说单方明显胜出"]},
        },
    )

    assert critique["ok"] is False
    assert any("不同口径" in issue for issue in critique["issues"])


def test_critic_requires_limitation_note_when_evidence_is_insufficient() -> None:
    critique = critique_answer(
        answer="GUTS 更胜一筹。",
        final_payload={
            "coverage": {},
            "evidence_cards": [],
            "evidence_sufficiency": {
                "sufficient": False,
                "missing_required_axes": ["recency"],
            },
        },
    )

    assert critique["ok"] is False
    assert any("evidence_sufficiency" in issue for issue in critique["issues"])


def test_critic_rejects_confident_single_conclusion_when_evidence_is_insufficient() -> None:
    critique = critique_answer(
        answer="GUTS 明显更甚，所有指标均指向它，毫无疑问可以确定。",
        final_payload={
            "coverage": {},
            "evidence_cards": [],
            "evidence_sufficiency": {"sufficient": False},
        },
    )

    assert critique["ok"] is False
    assert any("强确定" in issue for issue in critique["issues"])


def test_critic_allows_limited_answer_when_evidence_is_insufficient() -> None:
    critique = critique_answer(
        answer="证据不足，目前无法确定单一胜者；只能说现有播放证据里 GUTS 暂时更高。",
        final_payload={
            "coverage": {},
            "evidence_cards": [],
            "evidence_sufficiency": {"sufficient": False},
        },
    )

    assert critique["ok"] is True
    assert critique["issues"] == []


def test_critic_allows_global_insufficiency_note_when_compare_found() -> None:
    critique = critique_answer(
        answer="证据不足，目前无法确定单一胜者；只能说现有播放证据里 GUTS 暂时更高。",
        final_payload={
            "coverage": {
                "comparison": {"compare_entities": "found"},
                "entities": {
                    "GUTS": {"compare_entities": "found"},
                    "SOUR": {"compare_entities": "found"},
                },
            },
            "evidence_cards": [],
            "evidence_sufficiency": {"sufficient": False},
        },
    )

    assert critique["ok"] is True
    assert critique["issues"] == []
