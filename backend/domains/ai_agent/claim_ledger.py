"""Deterministic numeric and semantic grounding for Agent final answers."""

from __future__ import annotations

import math
import re
from typing import Any

from pydantic import BaseModel, Field

_DATE_OR_NUMBER_RE = re.compile(
    r"20\d{2}-\d{2}-\d{2}|(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?%?|(?<![\w.])\d+(?:\.\d+)?%?"
)
_DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")
_SENTENCE_RE = re.compile(r"[^。！？!?；;\n]+")
_RANK_RE = re.compile(r"(?:排名|排行)?第\s*([一二三四五六七八九十\d]+)|#\s*(\d+)")
_TOP_RANK_RE = re.compile(r"(?:top|TOP|Top)[ -]?([1-9]\d*)")
_RANKING_TOKENS = ("排名", "排行", "第", "#", "Top", "TOP", "最常", "最高", "榜首", "第一")
_COMPARISON_TOKENS = ("更高", "更低", "更多", "更少", "领先", "胜出", "占优", "更喜欢")
_DIRECTION_GROUPS: dict[str, tuple[str, ...]] = {
    "up": ("上升", "增加", "增长", "回升", "变多"),
    "down": ("下降", "减少", "回落", "变少", "下滑"),
    "stable": ("稳定", "持平", "不变"),
    "mixed": ("波动", "起伏"),
}
_COMPARISON_FACT_METRICS: dict[str, tuple[str, ...]] = {
    "winner_by_cumulative_plays": ("播放次数", "累计播放", "长期"),
    "winner_by_total_hours": ("播放时长", "收听时长", "小时"),
    "winner_by_power_score": ("Power Score", "个人榜单", "Billboard"),
    "winner_by_intensity": ("强度", "周均", "单位时间"),
}
_CHINESE_RANKS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


class SemanticClaim(BaseModel):
    text: str
    claim_type: str
    subject: str | None = None
    predicate: str
    object: str | int | float | None = None
    fact_refs: list[str] = Field(default_factory=list)
    supported: bool = False


class GroundedClaim(BaseModel):
    text: str
    numeric_literals: list[str] = Field(default_factory=list)
    fact_refs: list[str] = Field(default_factory=list)
    unsupported_literals: list[str] = Field(default_factory=list)
    claim_types: list[str] = Field(default_factory=list)
    semantic_claims: list[SemanticClaim] = Field(default_factory=list)


class ClaimLedger(BaseModel):
    claims: list[GroundedClaim] = Field(default_factory=list)
    numeric_claim_count: int = 0
    supported_numeric_claim_count: int = 0
    evidence_coverage: float = 1.0
    unsupported_literals: list[str] = Field(default_factory=list)
    semantic_claim_count: int = 0
    supported_semantic_claim_count: int = 0
    semantic_coverage: float = 1.0
    unsupported_semantic_claims: list[SemanticClaim] = Field(default_factory=list)


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


def _fact_ref(fact: dict[str, Any]) -> list[str]:
    fact_id = str(fact.get("fact_id") or "")
    return [fact_id] if fact_id else []


def _rank_number(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    return _CHINESE_RANKS.get(value)


def _claimed_rank(sentence: str) -> int | None:
    match = _RANK_RE.search(sentence)
    if match:
        return _rank_number(match.group(1) or match.group(2))
    top_match = _TOP_RANK_RE.search(sentence)
    if top_match:
        return int(top_match.group(1))
    if any(token in sentence for token in ("最常", "最高", "榜首", "第一")):
        return 1
    return None


def _fact_rank(fact: dict[str, Any]) -> int | None:
    metric_name = str(fact.get("metric_name") or "")
    match = re.search(r"(?:^|\.)top_(\d+)(?:_|$)", metric_name)
    if match:
        return int(match.group(1))
    label = str(fact.get("label") or "")
    label_match = re.search(r"#(\d+)", label)
    if label_match:
        return int(label_match.group(1))
    if metric_name in {"top_artist", "top_track", "top_album"} or "第一" in label:
        return 1
    return None


def _ranking_facts(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        fact
        for fact in facts
        if isinstance(fact, dict)
        and isinstance(fact.get("value"), str)
        and _fact_rank(fact) is not None
    ]


def _semantic_ranking_claims(sentence: str, facts: list[dict[str, Any]]) -> list[SemanticClaim]:
    if not any(token in sentence for token in _RANKING_TOKENS):
        return []
    claimed_rank = _claimed_rank(sentence)
    if claimed_rank is None:
        return []
    claims: list[SemanticClaim] = []
    for fact in _ranking_facts(facts):
        entity_name = str(fact.get("value") or "")
        if not entity_name or entity_name not in sentence:
            continue
        expected_rank = _fact_rank(fact)
        supported = expected_rank == claimed_rank
        claims.append(
            SemanticClaim(
                text=sentence,
                claim_type="ranking",
                subject=entity_name,
                predicate="rank",
                object=claimed_rank,
                fact_refs=_fact_ref(fact) if supported else [],
                supported=supported,
            )
        )
    return claims


def _known_entity_names(facts: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    metric_suffixes = (
        "播放次数",
        "播放时长",
        "所选窗口周均播放",
        "单位在榜周播放",
        "个人榜单 Power Score",
        "个人榜单排名",
        "在榜周数",
    )
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        entity_name = fact.get("entity_name")
        if isinstance(entity_name, str) and entity_name:
            names.add(entity_name)
        label = str(fact.get("label") or "")
        for suffix in metric_suffixes:
            if label.endswith(suffix):
                prefix = label[: -len(suffix)].strip()
                if prefix:
                    names.add(prefix)
    return names


def _comparison_fact_for_sentence(
    sentence: str,
    facts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for fact in facts:
        if not isinstance(fact, dict) or not isinstance(fact.get("value"), str):
            continue
        metric_name = str(fact.get("metric_name") or "")
        tokens = _COMPARISON_FACT_METRICS.get(metric_name)
        if tokens and any(token in sentence for token in tokens):
            candidates.append(fact)
    return candidates[0] if len(candidates) == 1 else None


def _semantic_comparison_claims(
    sentence: str,
    facts: list[dict[str, Any]],
) -> list[SemanticClaim]:
    if not any(token in sentence for token in _COMPARISON_TOKENS):
        return []
    fact = _comparison_fact_for_sentence(sentence, facts)
    if fact is None:
        return []
    mentioned = [name for name in _known_entity_names(facts) if name in sentence]
    if len(mentioned) != 1:
        return []
    subject = mentioned[0]
    winner = str(fact.get("value") or "")
    supported = subject == winner
    return [
        SemanticClaim(
            text=sentence,
            claim_type="comparison",
            subject=subject,
            predicate=str(fact.get("metric_name") or "winner"),
            object=winner,
            fact_refs=_fact_ref(fact) if supported else [],
            supported=supported,
        )
    ]


def _normalized_direction(value: Any) -> str | None:
    text = str(value or "")
    lowered = text.casefold()
    if lowered in {"up", "increase", "increasing", "positive"}:
        return "up"
    if lowered in {"down", "decrease", "decreasing", "negative"}:
        return "down"
    if lowered in {"stable", "flat", "unchanged"}:
        return "stable"
    for direction, tokens in _DIRECTION_GROUPS.items():
        if any(token in text for token in tokens):
            return direction
    return None


def _semantic_direction_claims(sentence: str, facts: list[dict[str, Any]]) -> list[SemanticClaim]:
    claimed = next(
        (
            direction
            for direction, tokens in _DIRECTION_GROUPS.items()
            if any(token in sentence for token in tokens)
        ),
        None,
    )
    if claimed is None:
        return []
    candidates = [
        fact
        for fact in facts
        if isinstance(fact, dict)
        and any(
            token in str(fact.get("metric_name") or "").casefold()
            for token in ("direction", "trend", "change")
        )
        and _normalized_direction(fact.get("value")) is not None
    ]
    if len(candidates) != 1:
        return []
    fact = candidates[0]
    expected = _normalized_direction(fact.get("value"))
    supported = claimed == expected
    return [
        SemanticClaim(
            text=sentence,
            claim_type="direction",
            subject=str(fact.get("entity_name") or "") or None,
            predicate="trend_direction",
            object=claimed,
            fact_refs=_fact_ref(fact) if supported else [],
            supported=supported,
        )
    ]


def _semantic_time_claims(sentence: str, facts: list[dict[str, Any]]) -> list[SemanticClaim]:
    dates = list(dict.fromkeys(_DATE_OR_NUMBER_RE.findall(sentence)))
    dates = [date for date in dates if _DATE_RE.fullmatch(date)]
    if not dates:
        return []
    refs: list[str] = []
    for date in dates:
        refs.extend(ref for ref in _literal_fact_refs(facts, date) if ref not in refs)
    supported = len(refs) >= len(dates)
    return [
        SemanticClaim(
            text=sentence,
            claim_type="time_range",
            predicate="time_range",
            object="..".join(dates),
            fact_refs=refs if supported else [],
            supported=supported,
        )
    ]


def _semantic_claims(sentence: str, facts: list[dict[str, Any]]) -> list[SemanticClaim]:
    return [
        *_semantic_ranking_claims(sentence, facts),
        *_semantic_comparison_claims(sentence, facts),
        *_semantic_direction_claims(sentence, facts),
        *_semantic_time_claims(sentence, facts),
    ]


def build_claim_ledger(answer: str, facts: list[dict[str, Any]]) -> dict[str, Any]:
    """Map numeric and high-confidence semantic claims to deterministic facts."""

    claims: list[GroundedClaim] = []
    all_unsupported: list[str] = []
    numeric_count = 0
    supported_count = 0
    semantic_count = 0
    supported_semantic_count = 0
    all_unsupported_semantic: list[SemanticClaim] = []
    for match in _SENTENCE_RE.finditer(answer):
        sentence = match.group(0).strip()
        if not sentence:
            continue
        literals: list[str] = []
        refs: list[str] = []
        unsupported: list[str] = []
        semantic_claims = _semantic_claims(sentence, facts)
        semantic_count += len(semantic_claims)
        for semantic_claim in semantic_claims:
            if semantic_claim.supported:
                supported_semantic_count += 1
                refs.extend(ref for ref in semantic_claim.fact_refs if ref not in refs)
            else:
                all_unsupported_semantic.append(semantic_claim)
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
        if literals or semantic_claims:
            claims.append(
                GroundedClaim(
                    text=sentence,
                    numeric_literals=literals,
                    fact_refs=refs,
                    unsupported_literals=unsupported,
                    claim_types=list(
                        dict.fromkeys(
                            ["numeric"]
                            if literals
                            else [] + [claim.claim_type for claim in semantic_claims]
                        )
                    ),
                    semantic_claims=semantic_claims,
                )
            )
    coverage = supported_count / numeric_count if numeric_count else 1.0
    semantic_coverage = supported_semantic_count / semantic_count if semantic_count else 1.0
    return ClaimLedger(
        claims=claims,
        numeric_claim_count=numeric_count,
        supported_numeric_claim_count=supported_count,
        evidence_coverage=round(coverage, 4),
        unsupported_literals=all_unsupported,
        semantic_claim_count=semantic_count,
        supported_semantic_claim_count=supported_semantic_count,
        semantic_coverage=round(semantic_coverage, 4),
        unsupported_semantic_claims=all_unsupported_semantic,
    ).model_dump()


def claim_ledger_issues(ledger: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    unsupported = ledger.get("unsupported_literals")
    if isinstance(unsupported, list) and unsupported:
        rendered = "、".join(str(item) for item in unsupported[:8])
        issues.append(f"回答包含无法追溯到事实目录的数字：{rendered}")
    unsupported_semantic = ledger.get("unsupported_semantic_claims")
    if isinstance(unsupported_semantic, list) and unsupported_semantic:
        rendered_claims = [
            str(item.get("text") or item.get("predicate") or "语义结论")
            for item in unsupported_semantic[:4]
            if isinstance(item, dict)
        ]
        issues.append(
            "回答包含无法追溯到事实目录的排名、比较、方向或时间结论：" + "；".join(rendered_claims)
        )
    return issues


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
