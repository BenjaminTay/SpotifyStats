"""Deterministic numeric-claim grounding for Agent final answers."""

from __future__ import annotations

import math
import re
from typing import Any

from pydantic import BaseModel, Field

_DATE_OR_NUMBER_RE = re.compile(
    r"20\d{2}-\d{2}-\d{2}|(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?%?|(?<![\w.])\d+(?:\.\d+)?%?"
)
_SENTENCE_RE = re.compile(r"[^。！？!?；;\n]+")


class GroundedClaim(BaseModel):
    text: str
    numeric_literals: list[str] = Field(default_factory=list)
    fact_refs: list[str] = Field(default_factory=list)
    unsupported_literals: list[str] = Field(default_factory=list)


class ClaimLedger(BaseModel):
    claims: list[GroundedClaim] = Field(default_factory=list)
    numeric_claim_count: int = 0
    supported_numeric_claim_count: int = 0
    evidence_coverage: float = 1.0
    unsupported_literals: list[str] = Field(default_factory=list)


def _normalized_number(value: str) -> float | None:
    text = value.strip().replace(",", "").removesuffix("%")
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _is_structural_number(sentence: str, literal: str) -> bool:
    stripped = sentence.lstrip()
    return bool(re.match(rf"^{re.escape(literal)}\s*[.、)]", stripped))


def _fact_matches_literal(fact: dict[str, Any], literal: str) -> bool:
    value = fact.get("value")
    if value is None:
        return False
    if isinstance(value, str):
        if literal == value:
            return True
        # Years and other four-digit identifiers may be grounded by a date or
        # explicit temporal label, but short digits must never match by substring.
        return len(literal.removesuffix("%")) >= 4 and literal in value
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    parsed = _normalized_number(literal)
    if parsed is None:
        return False
    unit = str(fact.get("unit") or "")
    if literal.endswith("%") and unit != "%":
        return False
    if not literal.endswith("%") and unit == "%":
        return False
    numeric = float(value)
    tolerance = max(1e-9, abs(numeric) * 0.0005)
    if abs(parsed - numeric) <= tolerance:
        return True
    return any(abs(parsed - round(numeric, digits)) <= tolerance for digits in (0, 1, 2))


def _literal_fact_refs(facts: list[dict[str, Any]], literal: str) -> list[str]:
    refs: list[str] = []
    for fact in facts:
        if not isinstance(fact, dict) or not _fact_matches_literal(fact, literal):
            continue
        fact_id = str(fact.get("fact_id") or "")
        if fact_id and fact_id not in refs:
            refs.append(fact_id)
    return refs


def build_claim_ledger(answer: str, facts: list[dict[str, Any]]) -> dict[str, Any]:
    """Map each public numeric literal to one or more deterministic facts."""

    claims: list[GroundedClaim] = []
    all_unsupported: list[str] = []
    numeric_count = 0
    supported_count = 0
    for match in _SENTENCE_RE.finditer(answer):
        sentence = match.group(0).strip()
        if not sentence:
            continue
        literals: list[str] = []
        refs: list[str] = []
        unsupported: list[str] = []
        for literal_match in _DATE_OR_NUMBER_RE.finditer(sentence):
            literal = literal_match.group(0)
            if _is_structural_number(sentence, literal):
                continue
            literals.append(literal)
            numeric_count += 1
            matched_refs = _literal_fact_refs(facts, literal)
            if matched_refs:
                supported_count += 1
                refs.extend(ref for ref in matched_refs if ref not in refs)
            else:
                unsupported.append(literal)
                if literal not in all_unsupported:
                    all_unsupported.append(literal)
        if literals:
            claims.append(
                GroundedClaim(
                    text=sentence,
                    numeric_literals=literals,
                    fact_refs=refs,
                    unsupported_literals=unsupported,
                )
            )
    coverage = supported_count / numeric_count if numeric_count else 1.0
    return ClaimLedger(
        claims=claims,
        numeric_claim_count=numeric_count,
        supported_numeric_claim_count=supported_count,
        evidence_coverage=round(coverage, 4),
        unsupported_literals=all_unsupported,
    ).model_dump()


def claim_ledger_issues(ledger: dict[str, Any]) -> list[str]:
    unsupported = ledger.get("unsupported_literals")
    if not isinstance(unsupported, list) or not unsupported:
        return []
    rendered = "、".join(str(item) for item in unsupported[:8])
    return [f"回答包含无法追溯到事实目录的数字：{rendered}"]


_UNIT_LABELS = {
    "plays": "次",
    "hours": "小时",
    "tracks": "首",
    "artists": "位",
    "albums": "张",
    "days": "天",
    "weeks": "周",
    "plays/week": "次/周",
    "%": "%",
}


def render_grounded_fallback(facts: list[dict[str, Any]], *, max_facts: int = 12) -> str:
    """Render a conservative answer if a model keeps emitting unsupported numbers."""

    direct: list[dict[str, Any]] = []
    effective_dates: list[dict[str, Any]] = []
    for fact in facts:
        if not isinstance(fact, dict) or fact.get("value") is None:
            continue
        metric_name = str(fact.get("metric_name") or "")
        if metric_name in {"effective_start_date", "effective_end_date", "data_end_date"}:
            effective_dates.append(fact)
            continue
        if metric_name.startswith("requested_") or metric_name in {
            "today",
            "data_start_date",
            "latest_play_date",
        }:
            continue
        if fact.get("tool_name") == "deterministic_temporal_guard":
            continue
        direct.append(fact)

    lines = ["根据当前本地只读工具能够直接核验的证据，可确认："]
    for fact in direct[: max(1, max_facts)]:
        value = fact["value"]
        unit = _UNIT_LABELS.get(str(fact.get("unit") or ""), str(fact.get("unit") or ""))
        rendered = f"{value}{unit}" if unit else str(value)
        lines.append(f"- {fact.get('label') or fact.get('metric_name')}：{rendered}")

    effective = {str(item.get("metric_name")): item.get("value") for item in effective_dates}
    start = effective.get("effective_start_date")
    end = effective.get("effective_end_date")
    cutoff = effective.get("data_end_date")
    if start and end:
        lines.append(f"实际分析范围：{start} 至 {end}。")
    if cutoff:
        lines.append(f"本地播放数据截至 {cutoff}。")
    lines.append("为避免引入无证据推断，以上只保留可追溯到工具事实目录的内容。")
    return "\n".join(lines)
