from backend.domains.ai_agent.answer_contract import evaluate_answer_contract
from backend.domains.ai_agent.claim_ledger import build_claim_ledger


def _ranking_payload() -> dict:
    return {
        "question_frame": {"family": "simple_ranking", "entities": []},
        "evidence_sufficiency": {"sufficient": True},
        "answer_obligations": [
            {
                "kind": "ranking_result",
                "quality_dimension": "informative",
                "required_tokens_any": ["排名", "最常", "播放次数"],
                "required_values": [],
            }
        ],
        "fact_catalog": [
            {
                "fact_id": "fact-top",
                "metric_name": "top_artist",
                "label": "第一名",
                "value": "Artist A",
            },
            {
                "fact_id": "fact-plays",
                "metric_name": "top_1_plays",
                "label": "播放次数",
                "value": 12,
                "unit": "plays",
                "entity_name": "Artist A",
            },
        ],
    }


def test_grounded_but_uninformative_answer_is_partial_not_pass() -> None:
    payload = _ranking_payload()
    ledger = build_claim_ledger("已有可用结果", payload["fact_catalog"])

    result = evaluate_answer_contract("已有可用结果", payload, claim_ledger=ledger)

    assert result["ok"] is False
    assert result["classification"] == "partial"
    assert result["dimensions"]["grounded"]["passed"] is True
    assert result["dimensions"]["informative"]["passed"] is False


def test_grounded_informative_ranking_passes_contract() -> None:
    payload = _ranking_payload()
    answer = "Artist A 排名第一，播放次数为 12 次。"
    ledger = build_claim_ledger(answer, payload["fact_catalog"])

    result = evaluate_answer_contract(answer, payload, claim_ledger=ledger)

    assert result["ok"] is True
    assert result["classification"] == "pass"


def test_safe_refusal_requires_boundary_and_alternative() -> None:
    payload = {
        "question_frame": {"family": "safety_boundary"},
        "evidence_sufficiency": {"sufficient": False},
        "answer_obligations": [],
    }

    incomplete = evaluate_answer_contract("我不能执行。", payload)
    complete = evaluate_answer_contract(
        "我不能删除播放记录；可以改为使用只读工具分析现有数据。",
        payload,
    )

    assert incomplete["dimensions"]["informative"]["passed"] is False
    assert complete["ok"] is True


def test_comparison_must_cover_both_entities_and_direct_conclusion() -> None:
    payload = {
        "question_frame": {
            "family": "preference_comparison",
            "entities": ["Album A", "Album B"],
        },
        "evidence_sufficiency": {"sufficient": True},
        "answer_obligations": [],
    }

    result = evaluate_answer_contract("Album A 的数据已经查询完成。", payload)

    assert result["dimensions"]["complete"]["passed"] is False
    assert result["dimensions"]["informative"]["passed"] is False
