"""Structured models for agentic yearly report generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

AGENTIC_YEARLY_CONTRACT_VERSION = "agentic_yearly_v14"
AGENTIC_YEARLY_REPORT_MODE = "agentic_longform"
BASIC_SUMMARY_FALLBACK_LEVEL = "basic_summary"


def _list(value: tuple[Any, ...] | list[Any]) -> list[Any]:
    return list(value)


@dataclass(frozen=True)
class EvidenceLedgerEntry:
    tool_name: str
    params: dict[str, Any]
    result_summary: str
    supports: tuple[str, ...] = ()
    questions_raised: tuple[str, ...] = ()
    tool_call_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "params": self.params,
            "result_summary": self.result_summary,
            "supports": _list(self.supports),
            "questions_raised": _list(self.questions_raised),
            "tool_call_id": self.tool_call_id,
        }


@dataclass(frozen=True)
class InsightSynthesis:
    main_thesis: str
    supporting_arguments: tuple[dict[str, Any], ...] = ()
    billboard_findings: tuple[str, ...] = ()
    playback_findings: tuple[str, ...] = ()
    tensions: tuple[str, ...] = ()
    interesting_anomalies: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "main_thesis": self.main_thesis,
            "supporting_arguments": _list(self.supporting_arguments),
            "billboard_findings": _list(self.billboard_findings),
            "playback_findings": _list(self.playback_findings),
            "tensions": _list(self.tensions),
            "interesting_anomalies": _list(self.interesting_anomalies),
        }


@dataclass(frozen=True)
class OutlineSection:
    heading: str
    question: str
    claims: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "heading": self.heading,
            "question": self.question,
            "claims": _list(self.claims),
        }


@dataclass(frozen=True)
class DynamicOutline:
    title: str
    sections: tuple[OutlineSection, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "sections": [section.to_dict() for section in self.sections],
        }


@dataclass(frozen=True)
class EditorialIssue:
    code: str
    message: str
    severity: str = "high"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class EditorialCritique:
    ok: bool
    issues: tuple[EditorialIssue, ...] = ()
    repair_instructions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
            "repair_instructions": _list(self.repair_instructions),
        }


@dataclass(frozen=True)
class AgenticYearlyMetadata:
    report_mode: str
    contract_version: str
    fallback_level: str | None
    tool_calls: int
    data_range: str
    is_partial_year: bool
    critic_passed: bool
    article_length: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_mode": self.report_mode,
            "contract_version": self.contract_version,
            "fallback_level": self.fallback_level,
            "tool_calls": self.tool_calls,
            "data_range": self.data_range,
            "is_partial_year": self.is_partial_year,
            "critic_passed": self.critic_passed,
            "article_length": self.article_length,
        }
