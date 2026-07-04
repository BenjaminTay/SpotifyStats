"""Structured models for the yearly editorial-agent pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value if str(item).strip())
    if value:
        return (str(value),)
    return ()


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    claim: str
    source: str
    kind: str
    confidence: str = "high"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "claim": self.claim,
            "source": self.source,
            "kind": self.kind,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> EvidenceItem:
        return cls(
            id=str(value.get("id") or ""),
            claim=str(value.get("claim") or ""),
            source=str(value.get("source") or ""),
            kind=str(value.get("kind") or ""),
            confidence=str(value.get("confidence") or "high"),
        )


@dataclass(frozen=True)
class StoryCandidate:
    id: str
    title: str
    why_it_matters: str
    evidence_refs: tuple[str, ...]
    risk_notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "why_it_matters": self.why_it_matters,
            "evidence_refs": list(self.evidence_refs),
            "risk_notes": list(self.risk_notes),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> StoryCandidate:
        return cls(
            id=str(value.get("id") or ""),
            title=str(value.get("title") or ""),
            why_it_matters=str(value.get("why_it_matters") or ""),
            evidence_refs=_tuple(value.get("evidence_refs")),
            risk_notes=_tuple(value.get("risk_notes")),
        )


@dataclass(frozen=True)
class ResearchBrief:
    period: dict[str, Any]
    evidence_ledger: tuple[EvidenceItem, ...]
    story_candidates: tuple[StoryCandidate, ...]
    tensions: tuple[dict[str, Any], ...]
    forbidden_inferences: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": dict(self.period),
            "evidence_ledger": [item.to_dict() for item in self.evidence_ledger],
            "story_candidates": [item.to_dict() for item in self.story_candidates],
            "tensions": [dict(item) for item in self.tensions],
            "forbidden_inferences": list(self.forbidden_inferences),
        }


@dataclass(frozen=True)
class ArticleSection:
    id: str
    heading: str
    purpose: str
    prose: str
    evidence_refs: tuple[str, ...]
    chart_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "heading": self.heading,
            "purpose": self.purpose,
            "prose": self.prose,
            "evidence_refs": list(self.evidence_refs),
            "chart_refs": list(self.chart_refs),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ArticleSection:
        return cls(
            id=str(value.get("id") or ""),
            heading=str(value.get("heading") or ""),
            purpose=str(value.get("purpose") or ""),
            prose=str(value.get("prose") or ""),
            evidence_refs=_tuple(value.get("evidence_refs")),
            chart_refs=_tuple(value.get("chart_refs")),
        )


@dataclass(frozen=True)
class StorylinePlan:
    thesis: str
    title: str
    subtitle: str
    section_plan: tuple[ArticleSection, ...]
    must_not_write: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "thesis": self.thesis,
            "title": self.title,
            "subtitle": self.subtitle,
            "section_plan": [section.to_dict() for section in self.section_plan],
            "must_not_write": list(self.must_not_write),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> StorylinePlan:
        sections = tuple(
            ArticleSection.from_dict(item)
            for item in value.get("section_plan") or []
            if isinstance(item, dict)
        )
        return cls(
            thesis=str(value.get("thesis") or ""),
            title=str(value.get("title") or ""),
            subtitle=str(value.get("subtitle") or ""),
            section_plan=sections,
            must_not_write=_tuple(value.get("must_not_write")),
        )


@dataclass(frozen=True)
class ArticleDraft:
    title: str
    subtitle: str
    thesis: str
    sections: tuple[ArticleSection, ...]
    closing: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "thesis": self.thesis,
            "sections": [section.to_dict() for section in self.sections],
            "closing": self.closing,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ArticleDraft:
        sections = tuple(
            ArticleSection.from_dict(item)
            for item in value.get("sections") or []
            if isinstance(item, dict)
        )
        return cls(
            title=str(value.get("title") or ""),
            subtitle=str(value.get("subtitle") or ""),
            thesis=str(value.get("thesis") or ""),
            sections=sections,
            closing=str(value.get("closing") or ""),
        )


@dataclass(frozen=True)
class EditedArticle:
    article: ArticleDraft
    edit_notes: tuple[str, ...]
    risk_flags: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "article": self.article.to_dict(),
            "edit_notes": list(self.edit_notes),
            "risk_flags": list(self.risk_flags),
        }


@dataclass(frozen=True)
class ExtractedClaim:
    text: str
    claim_type: str
    matched_evidence_refs: tuple[str, ...] = ()
    status: str = "ambiguous"

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "claim_type": self.claim_type,
            "matched_evidence_refs": list(self.matched_evidence_refs),
            "status": self.status,
        }


@dataclass(frozen=True)
class ClaimCheckResult:
    claims: tuple[ExtractedClaim, ...]
    unsupported_claims: tuple[str, ...]
    contradicted_claims: tuple[str, ...]
    ambiguous_claims: tuple[str, ...]
    scope_leaks: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not (
            self.unsupported_claims
            or self.contradicted_claims
            or self.ambiguous_claims
            or self.scope_leaks
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "claims": [claim.to_dict() for claim in self.claims],
            "unsupported_claims": list(self.unsupported_claims),
            "contradicted_claims": list(self.contradicted_claims),
            "ambiguous_claims": list(self.ambiguous_claims),
            "scope_leaks": list(self.scope_leaks),
        }


@dataclass(frozen=True)
class TasteScore:
    dimensions: dict[str, int]
    notes: tuple[str, ...]

    @property
    def total(self) -> int:
        return sum(self.dimensions.values())

    @property
    def ok(self) -> bool:
        return (
            self.total >= 26
            and self.dimensions.get("事实安全", 0) == 5
            and self.dimensions.get("文章感", 0) >= 4
            and self.dimensions.get("年度主题", 0) >= 4
            and self.dimensions.get("可读性", 0) >= 4
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "total": self.total,
            "dimensions": dict(self.dimensions),
            "notes": list(self.notes),
        }
