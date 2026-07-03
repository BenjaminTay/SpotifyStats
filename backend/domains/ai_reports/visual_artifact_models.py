"""Structured models for visual yearly report artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

VISUAL_YEARLY_CONTRACT_VERSION = "visual_yearly_v1"
VISUAL_YEARLY_REPORT_MODE = "visual_yearly_artifact"


def _list(value: tuple[str, ...]) -> list[str]:
    return list(value)


@dataclass(frozen=True)
class YearlyArtifactSection:
    id: str
    role: str
    heading: str
    deck: str
    prose: str
    chart_refs: tuple[str, ...] = ()
    insight_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    pull_quote: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "heading": self.heading,
            "deck": self.deck,
            "prose": self.prose,
            "chart_refs": _list(self.chart_refs),
            "insight_refs": _list(self.insight_refs),
            "evidence_refs": _list(self.evidence_refs),
            "pull_quote": self.pull_quote,
        }


@dataclass(frozen=True)
class YearlyInsightCard:
    id: str
    label: str
    value: str
    caption: str
    tone: str
    evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "value": self.value,
            "caption": self.caption,
            "tone": self.tone,
            "evidence_refs": _list(self.evidence_refs),
        }


@dataclass(frozen=True)
class YearlyChartSpec:
    id: str
    chart_type: str
    title: str
    narrative_question: str
    entities: tuple[str, ...]
    data_key: str
    insight: str
    fallback: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "chart_type": self.chart_type,
            "title": self.title,
            "narrative_question": self.narrative_question,
            "entities": _list(self.entities),
            "data_key": self.data_key,
            "insight": self.insight,
            "fallback": self.fallback,
        }


@dataclass(frozen=True)
class YearlyArtifactMetadata:
    report_mode: str
    contract_version: str
    fallback_level: str | None
    section_count: int
    chart_count: int
    insight_card_count: int
    article_length: int
    critic_passed: bool
    fact_validation_passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_mode": self.report_mode,
            "contract_version": self.contract_version,
            "fallback_level": self.fallback_level,
            "section_count": self.section_count,
            "chart_count": self.chart_count,
            "insight_card_count": self.insight_card_count,
            "article_length": self.article_length,
            "critic_passed": self.critic_passed,
            "fact_validation_passed": self.fact_validation_passed,
        }


@dataclass(frozen=True)
class VisualYearlyArtifact:
    report_mode: str
    contract_version: str
    title: str
    subtitle: str
    period: dict[str, Any]
    narrative_brief: dict[str, Any]
    visual_brief: dict[str, Any]
    sections: tuple[YearlyArtifactSection, ...]
    insight_cards: tuple[YearlyInsightCard, ...]
    chart_specs: tuple[YearlyChartSpec, ...]
    chart_data: dict[str, Any]
    metadata: YearlyArtifactMetadata

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_mode": self.report_mode,
            "contract_version": self.contract_version,
            "title": self.title,
            "subtitle": self.subtitle,
            "period": self.period,
            "narrative_brief": self.narrative_brief,
            "visual_brief": self.visual_brief,
            "sections": [section.to_dict() for section in self.sections],
            "insight_cards": [card.to_dict() for card in self.insight_cards],
            "chart_specs": [spec.to_dict() for spec in self.chart_specs],
            "chart_data": self.chart_data,
            "metadata": self.metadata.to_dict(),
        }

    def missing_chart_refs(self) -> list[str]:
        available = {spec.id for spec in self.chart_specs} & set(self.chart_data)
        refs = {ref for section in self.sections for ref in section.chart_refs}
        return sorted(ref for ref in refs if ref not in available)
