"""Deterministic fact catalog derived from compact Agent evidence cards."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

_ISO_DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")
_TOOL_METRIC_SPECS: dict[str, tuple[str, str | None]] = {
    "total_plays": ("播放次数", "plays"),
    "plays": ("播放次数", "plays"),
    "hours": ("播放时长", "hours"),
    "total_hours": ("播放时长", "hours"),
    "rate": ("比例", "%"),
    "share_pct": ("占比", "%"),
    "rank": ("排名", None),
    "peak_position": ("最高排名", None),
    "power_score": ("个人榜单 Power Score", None),
    "weeks_on_chart": ("在榜周数", "weeks"),
    "weeks_at_no1": ("冠军周数", "weeks"),
    "year": ("年份", None),
}
_MAX_FALLBACK_TOOL_FACTS = 40
_MAX_FALLBACK_LIST_ITEMS = 20


class AgentFact(BaseModel):
    fact_id: str
    evidence_ref: str
    tool_name: str
    source_range: str = ""
    metric_name: str
    label: str
    value: Any
    unit: str | None = None
    entity_name: str | None = None
    entity_type: str | None = None
    derived_from: list[str] = Field(default_factory=list)


def _fact_id(*parts: Any) -> str:
    payload = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return "fact_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _fact_from_metric(card: dict[str, Any], metric: dict[str, Any]) -> AgentFact | None:
    card_id = str(card.get("card_id") or "").strip()
    metric_name = str(metric.get("name") or "").strip()
    label = str(metric.get("label") or metric_name).strip()
    if not card_id or not metric_name or metric.get("value") is None:
        return None
    source = card.get("source") if isinstance(card.get("source"), dict) else {}
    return AgentFact(
        fact_id=_fact_id(card_id, metric_name, metric.get("value")),
        evidence_ref=card_id,
        tool_name=str(source.get("tool_name") or ""),
        source_range=str(source.get("source_range") or ""),
        metric_name=metric_name,
        label=label,
        value=metric.get("value"),
        unit=str(metric["unit"]) if metric.get("unit") else None,
        entity_name=str(card["entity_name"]) if card.get("entity_name") else None,
        entity_type=str(card["entity_type"]) if card.get("entity_type") else None,
    )


def _comparison_metric_key(fact: AgentFact) -> str | None:
    for suffix in (
        "播放次数",
        "播放时长",
        "所选窗口周均播放",
        "单位在榜周播放",
        "个人榜单 Power Score",
        "个人榜单排名",
        "在榜周数",
    ):
        if fact.label.endswith(suffix):
            return suffix
    return None


def _derived_comparison_facts(facts: list[AgentFact]) -> list[AgentFact]:
    groups: dict[tuple[str, str], list[AgentFact]] = defaultdict(list)
    for fact in facts:
        if not isinstance(fact.value, (int, float)) or isinstance(fact.value, bool):
            continue
        key = _comparison_metric_key(fact)
        if key:
            groups[(fact.evidence_ref, key)].append(fact)

    derived: list[AgentFact] = []
    for (evidence_ref, metric_label), items in groups.items():
        if len(items) != 2:
            continue
        left, right = items
        difference = abs(float(left.value) - float(right.value))
        difference = round(difference, 2)
        values = [abs(float(left.value)), abs(float(right.value))]
        baseline = min(values)
        percent = round(difference / baseline * 100, 2) if baseline > 0 else None
        common: dict[str, Any] = {
            "evidence_ref": evidence_ref,
            "tool_name": left.tool_name,
            "source_range": left.source_range,
            "entity_type": left.entity_type,
            "derived_from": [left.fact_id, right.fact_id],
        }
        derived.append(
            AgentFact(
                fact_id=_fact_id(evidence_ref, metric_label, "difference", difference),
                metric_name=f"derived_{metric_label}_difference",
                label=f"{metric_label}绝对差",
                value=difference,
                unit=left.unit,
                **common,
            )
        )
        if percent is not None:
            derived.append(
                AgentFact(
                    fact_id=_fact_id(evidence_ref, metric_label, "difference_pct", percent),
                    metric_name=f"derived_{metric_label}_difference_pct",
                    label=f"{metric_label}相对差",
                    value=percent,
                    unit="%",
                    **common,
                )
            )
    return derived


def _temporal_facts(
    temporal_context: dict[str, Any],
    temporal_guard: dict[str, Any],
) -> list[AgentFact]:
    facts: list[AgentFact] = []
    for name, label in (
        ("today", "提问日期"),
        ("data_start_date", "本地数据起始日期"),
        ("data_end_date", "本地数据截止日期"),
        ("latest_play_date", "最新播放日期"),
    ):
        value = temporal_context.get(name)
        if not value:
            continue
        facts.append(
            AgentFact(
                fact_id=_fact_id("temporal_context", name, value),
                evidence_ref="temporal_context",
                tool_name="deterministic_temporal_context",
                source_range="local_data_coverage",
                metric_name=name,
                label=label,
                value=value,
            )
        )
    interpretation = temporal_guard.get("time_interpretation")
    if isinstance(interpretation, dict):
        for name, label in (
            ("label", "用户时间表达"),
            ("requested_start_date", "请求范围开始"),
            ("requested_end_date", "请求范围结束"),
            ("effective_start_date", "实际分析范围开始"),
            ("effective_end_date", "实际分析范围结束"),
        ):
            value = interpretation.get(name)
            if not value:
                continue
            facts.append(
                AgentFact(
                    fact_id=_fact_id("temporal_guard", name, value),
                    evidence_ref="temporal_guard",
                    tool_name="deterministic_temporal_guard",
                    source_range="effective_query_range",
                    metric_name=name,
                    label=label,
                    value=value,
                )
            )
    return facts


def _source_range_facts(evidence_cards: list[dict[str, Any]]) -> list[AgentFact]:
    facts: list[AgentFact] = []
    for card in evidence_cards:
        if not isinstance(card, dict):
            continue
        source = card.get("source") if isinstance(card.get("source"), dict) else {}
        source_range = str(source.get("source_range") or "")
        dates = list(dict.fromkeys(_ISO_DATE_RE.findall(source_range)))
        for index, value in enumerate(dates[:2]):
            boundary = "start" if index == 0 else "end"
            facts.append(
                AgentFact(
                    fact_id=_fact_id(card.get("card_id"), "source_range", boundary, value),
                    evidence_ref=str(card.get("card_id") or ""),
                    tool_name=str(source.get("tool_name") or ""),
                    source_range=source_range,
                    metric_name=f"source_range_{boundary}",
                    label="证据范围开始" if index == 0 else "证据范围结束",
                    value=value,
                )
            )
    return facts


def _tool_result_facts(tool_results: list[dict[str, Any]]) -> list[AgentFact]:
    """Recover known deterministic metrics when a tool has no card builder yet."""

    facts: list[AgentFact] = []

    def visit(
        value: Any,
        *,
        tool_name: str,
        evidence_ref: str,
        source_range: str,
        path: tuple[str, ...],
    ) -> None:
        if len(facts) >= _MAX_FALLBACK_TOOL_FACTS:
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if len(facts) >= _MAX_FALLBACK_TOOL_FACTS:
                    break
                next_path = (*path, str(key))
                spec = _TOOL_METRIC_SPECS.get(str(key))
                if (
                    spec is not None
                    and isinstance(item, (int, float))
                    and not isinstance(item, bool)
                ):
                    label, unit = spec
                    facts.append(
                        AgentFact(
                            fact_id=_fact_id(evidence_ref, next_path, item),
                            evidence_ref=evidence_ref,
                            tool_name=tool_name,
                            source_range=source_range,
                            metric_name=".".join(next_path),
                            label=label,
                            value=item,
                            unit=unit,
                        )
                    )
                visit(
                    item,
                    tool_name=tool_name,
                    evidence_ref=evidence_ref,
                    source_range=source_range,
                    path=next_path,
                )
        elif isinstance(value, list):
            # Long row series (for example daily trends) are evidence payloads,
            # not a useful final-answer fact catalog. Their summary metrics
            # should come from an evidence-card builder instead.
            if len(value) > _MAX_FALLBACK_LIST_ITEMS:
                return
            for index, item in enumerate(value):
                visit(
                    item,
                    tool_name=tool_name,
                    evidence_ref=evidence_ref,
                    source_range=source_range,
                    path=(*path, str(index)),
                )

    for index, result in enumerate(tool_results):
        if not isinstance(result, dict) or result.get("status") == "error":
            continue
        tool_name = str(result.get("tool_name") or "")
        evidence_ref = f"tool_result:{index}:{tool_name}"
        visit(
            result.get("data"),
            tool_name=tool_name,
            evidence_ref=evidence_ref,
            source_range=str(result.get("source_range") or ""),
            path=(),
        )
    return facts


def build_fact_catalog(
    evidence_cards: list[dict[str, Any]],
    *,
    tool_results: list[dict[str, Any]] | None = None,
    temporal_context: dict[str, Any] | None = None,
    temporal_guard: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build compact, stable facts that final-answer claims may reference."""

    facts: list[AgentFact] = []
    for card in evidence_cards:
        if not isinstance(card, dict):
            continue
        metrics = card.get("metrics")
        if not isinstance(metrics, list):
            continue
        for metric in metrics:
            if not isinstance(metric, dict):
                continue
            fact = _fact_from_metric(card, metric)
            if fact is not None:
                facts.append(fact)
    facts.extend(_derived_comparison_facts(facts))
    facts.extend(_source_range_facts(evidence_cards))
    facts.extend(_tool_result_facts(tool_results or []))
    facts.extend(_temporal_facts(temporal_context or {}, temporal_guard or {}))
    return [fact.model_dump(exclude_none=True) for fact in facts]
