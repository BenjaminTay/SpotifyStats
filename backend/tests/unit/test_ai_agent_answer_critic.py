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
