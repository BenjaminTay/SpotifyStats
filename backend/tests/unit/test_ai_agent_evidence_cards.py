from backend.domains.ai_agent.evidence import (
    EvidenceCard,
    EvidenceMetric,
    EvidenceSource,
    compact_evidence_cards,
)


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
