"""Deterministic section checkpoints for Agent-written yearly reports."""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.domains.ai_agent.fact_catalog import build_fact_catalog
from backend.domains.ai_agent.tool_evidence import build_tool_evidence_envelopes

REPORT_SECTION_CHECKPOINT_VERSION = "report_section_checkpoint_v1"
_NUMBER_RE = re.compile(r"(?<![\w])\d+(?:,\d{3})*(?:\.\d+)?%?")
_SENTENCE_RE = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?|[^\n]+$")


class ReportSectionCheckpoint(BaseModel):
    schema_version: str = REPORT_SECTION_CHECKPOINT_VERSION
    section_index: int = Field(ge=0)
    heading: str
    status: Literal["pass", "partial", "fail"]
    evidence_refs: list[str] = Field(default_factory=list)
    chart_refs: list[str] = Field(default_factory=list)
    unsupported_numbers: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


def normalize_report_tool_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(results):
        if not isinstance(item, dict):
            continue
        tool_name = str(item.get("tool_name") or item.get("_tool_name") or "")
        if not tool_name:
            continue
        normalized.append(
            {
                **item,
                "tool_name": tool_name,
                "call_id": str(item.get("call_id") or f"report:{index}:{tool_name}"),
                "params": (
                    item.get("params")
                    if isinstance(item.get("params"), dict)
                    else item.get("_params")
                    if isinstance(item.get("_params"), dict)
                    else {}
                ),
                "status": item.get("status") or ("error" if item.get("error") else "done"),
            }
        )
    return normalized


def build_report_tool_evidence(
    results: list[dict[str, Any]],
    *,
    year: int,
    end_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized = normalize_report_tool_results(results)
    facts = build_fact_catalog(
        [],
        tool_results=normalized,
        temporal_context={"data_end_date": end_date},
        temporal_guard={
            "effective_data_range": {
                "start_date": f"{year:04d}-01-01",
                "end_date": end_date,
            }
        },
    )
    envelopes = build_tool_evidence_envelopes(
        normalized,
        fact_catalog=facts,
        constraint_state={"year": year, "end_date": end_date, "report_mode": "yearly"},
    )
    return envelopes, facts


def audit_report_sections(
    sections: list[dict[str, Any]],
    *,
    tool_results: list[dict[str, Any]],
    chart_data: dict[str, Any],
    chart_specs: list[dict[str, Any]],
    year: int,
    end_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Attach evidence refs and evaluate every visible section independently."""

    envelopes, facts = build_report_tool_evidence(tool_results, year=year, end_date=end_date)
    valid_charts = {str(item.get("id") or "") for item in chart_specs if isinstance(item, dict)}
    allowed_numbers = _numeric_values(
        {
            "facts": facts,
            "chart_data": chart_data,
            "year": year,
            "end_date": end_date,
        }
    )
    tool_signals = _tool_signals(envelopes, normalize_report_tool_results(tool_results))
    by_tool: dict[str, list[str]] = {}
    for envelope in envelopes:
        by_tool.setdefault(str(envelope.get("tool_name") or ""), []).append(
            str(envelope.get("tool_call_id") or "")
        )

    audited: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    for index, raw in enumerate(sections):
        section = dict(raw) if isinstance(raw, dict) else {}
        heading = str(section.get("heading") or "").strip()
        prose = str(section.get("prose") or "").strip()
        chart_refs = [
            str(ref) for ref in section.get("chart_refs") or [] if str(ref) in valid_charts
        ]
        declared_refs = [str(ref) for ref in section.get("evidence_refs") or [] if str(ref)]
        evidence_refs: list[str] = []
        for ref in declared_refs:
            if ref in {str(item.get("tool_call_id") or "") for item in envelopes}:
                evidence_refs.append(ref)
            elif ref in by_tool:
                evidence_refs.extend(by_tool[ref][:1])
        for ref, signals in tool_signals.items():
            if any(signal and signal in prose for signal in signals):
                evidence_refs.append(ref)
        evidence_refs.extend(f"chart:{ref}" for ref in chart_refs)
        evidence_refs = list(dict.fromkeys(ref for ref in evidence_refs if ref))

        unsupported = [
            token for token in _numbers(prose) if _normalize_number(token) not in allowed_numbers
        ]
        issues: list[str] = []
        if not heading:
            issues.append("missing_heading")
        if len(prose) < 40:
            issues.append("prose_too_short")
        if unsupported:
            issues.append("unsupported_numeric_claims")
        if not evidence_refs:
            issues.append("missing_evidence_refs")
        status: Literal["pass", "partial", "fail"]
        if not heading or unsupported:
            status = "fail"
        elif issues:
            status = "partial"
        else:
            status = "pass"
        section.update(
            {
                "heading": heading,
                "prose": prose,
                "chart_refs": chart_refs,
                "evidence_refs": evidence_refs,
            }
        )
        audited.append(section)
        checkpoints.append(
            ReportSectionCheckpoint(
                section_index=index,
                heading=heading,
                status=status,
                evidence_refs=evidence_refs,
                chart_refs=chart_refs,
                unsupported_numbers=list(dict.fromkeys(unsupported)),
                issues=issues,
            ).model_dump()
        )
    return audited, checkpoints, envelopes


def strip_unsupported_numeric_sentences(
    prose: str,
    unsupported_numbers: list[str],
) -> str:
    if not unsupported_numbers:
        return prose
    unsupported = set(unsupported_numbers)
    kept = [
        sentence.strip()
        for sentence in _SENTENCE_RE.findall(prose)
        if sentence.strip() and not unsupported.intersection(_numbers(sentence))
    ]
    return "".join(kept).strip()


def _numbers(text: str) -> list[str]:
    return _NUMBER_RE.findall(text)


def _normalize_number(value: Any) -> str:
    rendered = str(value).replace(",", "").rstrip("%")
    try:
        number = Decimal(rendered)
    except (InvalidOperation, ValueError):
        return rendered
    normalized = format(number.normalize(), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def _numeric_values(value: Any, *, limit: int = 12000) -> set[str]:
    rendered = json.dumps(value, ensure_ascii=False, default=str)
    return {_normalize_number(token) for token in _numbers(rendered[: limit * 20])}


def _tool_signals(
    envelopes: list[dict[str, Any]],
    normalized_results: list[dict[str, Any]],
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for envelope, raw in zip(envelopes, normalized_results):
        call_id = str(envelope.get("tool_call_id") or "")
        signals: set[str] = set(_numbers(str(raw.get("result_summary") or "")))
        for fact in envelope.get("facts") or []:
            if not isinstance(fact, dict):
                continue
            subject = str(fact.get("subject") or "").strip()
            if len(subject) >= 2:
                signals.add(subject)
            if fact.get("value") is not None:
                signals.add(str(fact["value"]))
        data = raw.get("data")
        if isinstance(data, dict):
            for match in re.findall(r"[A-Za-z][A-Za-z0-9 '&,:!?-]{2,80}", str(data)[:5000]):
                signals.add(match.strip())
        result[call_id] = signals
    return result
