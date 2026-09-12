from __future__ import annotations

import pytest

from backend.domains.ai_agent.claim_ledger import (
    build_claim_ledger,
    claim_ledger_issues,
    render_grounded_fallback,
)
from backend.domains.ai_agent.fact_catalog import build_fact_catalog

pytestmark = pytest.mark.unit


def _comparison_cards() -> list[dict]:
    return [
        {
            "card_id": "artist:comparison",
            "title": "实体比较摘要",
            "entity_type": "artist",
            "source": {
                "tool_name": "compare_entities",
                "source_range": "2026-03-04..2026-08-21",
            },
            "metrics": [
                {
                    "name": "Olivia Rodrigo_total_plays",
                    "label": "Olivia Rodrigo 播放次数",
                    "value": 889,
                    "unit": "plays",
                },
                {
                    "name": "Taylor Swift_total_plays",
                    "label": "Taylor Swift 播放次数",
                    "value": 854,
                    "unit": "plays",
                },
                {
                    "name": "Olivia Rodrigo_hours",
                    "label": "Olivia Rodrigo 播放时长",
                    "value": 53.87,
                    "unit": "hours",
                },
                {
                    "name": "Taylor Swift_hours",
                    "label": "Taylor Swift 播放时长",
                    "value": 52.96,
                    "unit": "hours",
                },
            ],
        }
    ]


def _temporal_context() -> dict:
    return {
        "today": "2026-08-31",
        "data_start_date": "2022-07-01",
        "data_end_date": "2026-08-21",
        "latest_play_date": "2026-08-21",
    }


def _temporal_guard() -> dict:
    return {
        "time_interpretation": {
            "label": "最近6个月",
            "requested_start_date": "2026-03-04",
            "requested_end_date": "2026-08-31",
            "effective_start_date": "2026-03-04",
            "effective_end_date": "2026-08-21",
        }
    }


def test_fact_catalog_contains_source_metrics_derived_differences_and_ranges() -> None:
    facts = build_fact_catalog(
        _comparison_cards(),
        temporal_context=_temporal_context(),
        temporal_guard=_temporal_guard(),
    )

    by_label = {item["label"]: item for item in facts}
    assert by_label["Olivia Rodrigo 播放次数"]["value"] == 889
    assert by_label["播放次数绝对差"]["value"] == 35.0
    assert by_label["播放次数相对差"]["value"] == 4.1
    assert by_label["实际分析范围结束"]["value"] == "2026-08-21"
    assert by_label["证据范围开始"]["value"] == "2026-03-04"
    assert by_label["证据范围结束"]["value"] == "2026-08-21"
    assert len(by_label["播放次数绝对差"]["derived_from"]) == 2


def test_claim_ledger_maps_supported_numbers_and_rejects_invented_metrics() -> None:
    facts = build_fact_catalog(
        _comparison_cards(),
        temporal_context=_temporal_context(),
        temporal_guard=_temporal_guard(),
    )
    answer = (
        "Olivia Rodrigo 有 889 次，Taylor Swift 有 854 次，相差 35 次（4.1%）。"
        "实际分析范围为 2026-03-04 至 2026-08-21。"
    )

    ledger = build_claim_ledger(answer, facts)

    assert ledger["evidence_coverage"] == 1.0
    assert ledger["unsupported_literals"] == []
    assert claim_ledger_issues(ledger) == []

    unsupported = build_claim_ledger(answer + "两人一共覆盖 250 首歌。", facts)
    assert unsupported["evidence_coverage"] < 1.0
    assert "250" in unsupported["unsupported_literals"]
    assert claim_ledger_issues(unsupported)


def test_claim_ledger_ignores_markdown_list_ordinals() -> None:
    facts = build_fact_catalog(
        _comparison_cards(),
        temporal_context=_temporal_context(),
        temporal_guard=_temporal_guard(),
    )

    ledger = build_claim_ledger(
        "1. Olivia Rodrigo 播放 889 次。\n2. Taylor Swift 播放 854 次。", facts
    )

    assert ledger["unsupported_literals"] == []
    assert ledger["numeric_claim_count"] == 2


def test_fact_catalog_recovers_allowlisted_metrics_without_evidence_card() -> None:
    facts = build_fact_catalog(
        [],
        tool_results=[
            {
                "tool_name": "analysis_stats",
                "status": "done",
                "source_range": "2026",
                "data": {"summary": {"total_plays": 77}},
            },
            {
                "tool_name": "listening_hours",
                "status": "done",
                "source_range": "late_night_ratio",
                "data": [{"year": 2026, "rate": 12.5}],
            },
        ],
    )

    by_metric = {item["metric_name"]: item for item in facts}
    assert by_metric["summary.total_plays"]["value"] == 77
    assert by_metric["0.rate"]["value"] == 12.5
    assert by_metric["0.rate"]["unit"] == "%"


def test_community_post_facts_render_named_grounded_fallback() -> None:
    content = "本周个人艺人榜：Olivia Rodrigo 排名第 2，播放 18 次。"
    facts = build_fact_catalog(
        [],
        tool_results=[
            {
                "tool_name": "community_feed_search",
                "status": "done",
                "source_range": "community_feed:scoped_chart_snapshot",
                "data": {
                    "posts": [
                        {
                            "content": content,
                            "posted_at": "2026-08-14",
                            "linked_entities": [{"type": "artist", "name": "Olivia Rodrigo"}],
                            "chart": {
                                "week": "2026-08-14",
                                "rank": 2,
                                "play_count": 18,
                            },
                        }
                    ]
                },
            }
        ],
    )

    answer = render_grounded_fallback(facts)
    ledger = build_claim_ledger(answer, facts)

    assert content in answer
    assert ledger["unsupported_literals"] == []
    assert ledger["unsupported_semantic_claims"] == []
