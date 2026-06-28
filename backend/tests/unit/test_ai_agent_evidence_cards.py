from backend.domains.ai_agent.evidence import (
    EvidenceCard,
    EvidenceMetric,
    EvidenceSource,
    compact_evidence_cards,
)
from backend.domains.ai_agent.evidence_builders import build_evidence_cards
from backend.services import ai_agent_service


def test_evidence_card_serializes_metric_and_source():
    card = EvidenceCard(
        card_id="album:GUTS:entity_stats",
        title="GUTS 播放统计",
        entity_name="GUTS",
        entity_type="album",
        source=EvidenceSource(tool_name="entity_stats", source_range="lifetime"),
        metrics=[
            EvidenceMetric(name="plays", label="播放次数", value=1749, unit="plays"),
            EvidenceMetric(name="hours", label="播放时长", value=95.6, unit="hours"),
        ],
        limitations=["全时期累计口径"],
    )

    payload = card.model_dump(exclude_none=True)

    assert payload["card_id"] == "album:GUTS:entity_stats"
    assert payload["metrics"][0]["value"] == 1749
    assert payload["source"]["tool_name"] == "entity_stats"


def test_compact_evidence_cards_limits_metric_count():
    card = EvidenceCard(
        card_id="album:GUTS:billboard",
        title="GUTS 个人榜单",
        entity_name="GUTS",
        entity_type="album",
        source=EvidenceSource(tool_name="billboard_entity_detail", source_range="all_years"),
        metrics=[EvidenceMetric(name=f"m{i}", label=f"Metric {i}", value=i) for i in range(20)],
    )

    compact = compact_evidence_cards([card], max_metrics_per_card=5)

    assert len(compact) == 1
    assert len(compact[0]["metrics"]) == 5
    assert compact[0]["metrics"][4]["name"] == "m4"


def test_builds_album_entity_stats_evidence_card():
    cards = build_evidence_cards(
        [
            {
                "tool_name": "entity_stats",
                "status": "done",
                "params_summary": "entity=album, album_name=GUTS",
                "result_summary": "found=true, plays=1749, hours=95.6",
                "source_range": "2022-07-01..2026-06-23",
                "data": {
                    "found": True,
                    "album_name": "GUTS",
                    "summary": {"total_plays": 1749, "total_hours": 95.6},
                },
            }
        ]
    )

    assert len(cards) == 1
    assert cards[0].entity_name == "GUTS"
    assert cards[0].question_axis == "personal_playback"
    assert cards[0].metrics[0].name == "total_plays"


def test_builds_album_billboard_evidence_card():
    cards = build_evidence_cards(
        [
            {
                "tool_name": "billboard_entity_detail",
                "status": "done",
                "params_summary": "entity=album, album_name=The Life of a Showgirl",
                "result_summary": "found=true",
                "source_range": "all_years",
                "data": {
                    "found": True,
                    "album_name": "The Life of a Showgirl",
                    "chart_summary": {
                        "power_score": 10629,
                        "power_rank": 9,
                        "peak_position": 1,
                        "weeks_on_chart": 37,
                        "no1_weeks": 14,
                    },
                },
            }
        ]
    )

    metric_names = {metric.name for metric in cards[0].metrics}
    assert cards[0].question_axis == "personal_billboard"
    assert "power_score" in metric_names
    assert "no1_weeks" in metric_names


def test_builds_compare_entities_evidence_card():
    cards = build_evidence_cards(
        [
            {
                "tool_name": "compare_entities",
                "status": "done",
                "params_summary": ("entity_type=album, names=['GUTS', 'The Life of a Showgirl']"),
                "result_summary": "entities=2, winner_by_plays=GUTS",
                "source_range": "comparison",
                "data": {
                    "entity_type": "album",
                    "entities": [
                        {
                            "name": "GUTS",
                            "plays": 1749,
                            "power_score": 13566,
                            "power_rank": 4,
                            "weeks_on_chart": 79,
                            "plays_per_chart_week": 22.14,
                        },
                        {
                            "name": "The Life of a Showgirl",
                            "plays": 1637,
                            "power_score": 10629,
                            "power_rank": 9,
                            "weeks_on_chart": 37,
                            "plays_per_chart_week": 44.24,
                        },
                    ],
                    "winner_by_cumulative_plays": "GUTS",
                    "winner_by_total_hours": "The Life of a Showgirl",
                    "winner_by_power_score": "GUTS",
                    "winner_by_power_rank": "GUTS",
                    "winner_by_intensity": "The Life of a Showgirl",
                    "fairness_notes": [
                        "对象进入你的播放历史时间不同，累计值和强度值需要分开看。",
                        "个人 Billboard 是本地个人 Billboard，不是外部官方 Billboard。",
                    ],
                },
            }
        ]
    )

    assert len(cards) == 1
    assert cards[0].question_axis == "comparison"
    assert cards[0].entity_type == "album"
    assert cards[0].observations
    metric_names = {metric.name for metric in cards[0].metrics}
    assert "winner_by_cumulative_plays" in metric_names
    assert "winner_by_total_hours" in metric_names
    assert "winner_by_power_score" in metric_names
    assert "winner_by_intensity" in metric_names
    assert "GUTS_total_plays" in metric_names
    assert "The Life of a Showgirl_power_score" in metric_names
    assert any("最终回答必须说明口径" in item for item in cards[0].limitations)


def test_final_payload_preserves_compare_entities_core_evidence():
    payload = ai_agent_service._final_payload(
        {
            "question": "从播放次数和billboard榜单成绩来看，GUTS和The Life of a Showgirl哪张更甚？",
            "conversation_history": [],
        },
        [
            {
                "tool_name": "compare_entities",
                "status": "done",
                "params_summary": ("entity_type=album, names=['GUTS', 'The Life of a Showgirl']"),
                "result_summary": "entities=2, winner_by_plays=GUTS",
                "source_range": "comparison",
                "data": {
                    "entity_type": "album",
                    "entities": [
                        {
                            "name": "GUTS",
                            "requested_name": "GUTS",
                            "found": True,
                            "plays": 1749,
                            "hours": 95.6,
                            "power_score": 13566,
                            "power_rank": 4,
                            "weeks_on_chart": 79,
                            "plays_per_chart_week": 22.14,
                        },
                        {
                            "name": "The Life of a Showgirl",
                            "requested_name": "The Life of a Showgirl",
                            "found": True,
                            "plays": 1637,
                            "hours": 96.0,
                            "power_score": 10629,
                            "power_rank": 9,
                            "weeks_on_chart": 37,
                            "plays_per_chart_week": 44.24,
                        },
                    ],
                    "winner_by_cumulative_plays": "GUTS",
                    "winner_by_total_hours": "The Life of a Showgirl",
                    "winner_by_power_score": "GUTS",
                    "winner_by_power_rank": "GUTS",
                    "winner_by_intensity": "The Life of a Showgirl",
                    "fairness_notes": ["对象进入你的播放历史时间不同，累计值和强度值需要分开看。"],
                },
            }
        ],
    )

    compare_evidence = payload["tool_results"][0]["evidence"]
    assert compare_evidence["winner_by_cumulative_plays"] == "GUTS"
    assert compare_evidence["winner_by_intensity"] == "The Life of a Showgirl"
    assert compare_evidence["entities"][0]["plays"] == 1749
    assert compare_evidence["entities"][1]["power_score"] == 10629
    assert payload["coverage"]["comparison"]["compare_entities"] == "found"
    assert payload["coverage"]["entities"]["GUTS"]["compare_entities"] == "found"
    assert payload["evidence_cards"][0]["metrics"][0]["name"] == "winner_by_cumulative_plays"
    assert any(
        metric["name"] == "GUTS_total_plays" for metric in payload["evidence_cards"][0]["metrics"]
    )
    assert any(
        metric["name"] == "The Life of a Showgirl_power_score"
        for metric in payload["evidence_cards"][0]["metrics"]
    )


def test_final_payload_includes_compact_evidence_cards():
    payload = ai_agent_service._final_payload(
        {"question": "我更喜欢 GUTS 吗？", "conversation_history": []},
        [
            {
                "tool_name": "entity_stats",
                "status": "done",
                "params_summary": "entity=album, album_name=GUTS",
                "result_summary": "found=true, plays=1749, hours=95.6",
                "source_range": "2022-07-01..2026-06-23",
                "data": {
                    "found": True,
                    "album_name": "GUTS",
                    "summary": {"total_plays": 1749, "total_hours": 95.6},
                },
            }
        ],
    )

    assert payload["coverage"]["entities"]["GUTS"]["entity_stats"] == "found"
    assert payload["tool_results"][0]["tool_name"] == "entity_stats"
    assert payload["evidence_cards"][0]["entity_name"] == "GUTS"
    assert payload["evidence_cards"][0]["metrics"][0]["name"] == "total_plays"
