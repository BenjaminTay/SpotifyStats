"""Typed compact evidence cards for AI Agent final-answer context."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvidenceMetric(BaseModel):
    name: str
    label: str
    value: Any
    unit: str | None = None
    note: str | None = None


class EvidenceSource(BaseModel):
    tool_name: str
    source_range: str = ""
    params_summary: str = ""
    result_summary: str = ""


class EvidenceCard(BaseModel):
    card_id: str
    title: str
    entity_name: str | None = None
    entity_type: str | None = None
    question_axis: str | None = None
    source: EvidenceSource
    metrics: list[EvidenceMetric] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def compact_evidence_cards(
    cards: list[EvidenceCard],
    *,
    max_cards: int = 12,
    max_metrics_per_card: int = 10,
) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for card in cards[:max_cards]:
        payload = card.model_dump(exclude_none=True)
        payload["metrics"] = payload.get("metrics", [])[:max_metrics_per_card]
        compact.append(payload)
    return compact
