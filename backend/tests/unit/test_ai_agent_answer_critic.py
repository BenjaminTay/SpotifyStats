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
