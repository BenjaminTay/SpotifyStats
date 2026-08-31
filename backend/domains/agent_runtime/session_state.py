"""Deterministic structured state for in-flight Agent steering."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from backend.domains.ai_agent.question_intent import parse_question_intent
from backend.domains.ai_agent.temporal_context import (
    clip_custom_range_to_data,
    clip_time_interpretation_to_data_range,
    infer_time_interpretation,
)

SteeringAction = Literal[
    "replace_constraints",
    "add_requirements",
    "remove_requirements",
    "replace_task",
    "cancel",
]

_REPLACE_TASK_PATTERN = re.compile(
    r"(?:停止|算了|取消)?\s*(?:这个问题|当前问题|这次)?\s*"
    r"(?:，|,|。|；|;)?\s*(?:改问|换成|改成问|重新问)\s*(?P<question>.+)",
    re.IGNORECASE,
)
_EXPLICIT_YEAR_PATTERN = re.compile(r"(20\d{2}|2100)")
_REMOVE_TOKENS = ("不要", "不看", "排除", "去掉", "移除", "别看", "无需")
_REPLACE_TOKENS = ("只看", "仅看", "改成", "改为", "换成", "限定", "改到")
_ADD_TOKENS = ("再", "还要", "同时", "另外", "补充", "也看", "加上")
_CANCEL_TOKENS = ("取消", "停止", "别继续", "不用查了")
_CLAUSE_SPLIT_PATTERN = re.compile(r"[，,。；;\n]+")
_DIMENSION_TOKENS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("personal_billboard", ("billboard", "个人榜", "冠军周", "在榜周", "power score")),
    ("hours", ("播放时长", "收听时长", "时长", "小时")),
    ("plays", ("播放次数", "播放量", "次数")),
    ("time_of_day", ("深夜", "凌晨", "时段", "几点")),
    ("ranking", ("排名", "排行", "top")),
    ("external_context", ("外部", "联网", "网页", "市场")),
)


def _unique(values: list[str], *, limit: int = 12) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result[-limit:]


def _dimensions(content: str) -> list[str]:
    lowered = content.casefold()
    return [
        dimension
        for dimension, tokens in _DIMENSION_TOKENS
        if any(token.casefold() in lowered for token in tokens)
    ]


def _removal_dimensions(content: str) -> list[str]:
    """Only treat dimensions in a negative clause as excluded."""

    result: list[str] = []
    for clause in _CLAUSE_SPLIT_PATTERN.split(content):
        if any(token in clause for token in _REMOVE_TOKENS):
            result.extend(_dimensions(clause))
    return _unique(result)


def _without_excluded_dimensions(content: str, excluded: list[str]) -> str:
    """Remove excluded semantic dimensions from model-visible question text."""

    clauses: list[str] = []
    for raw_clause in _CLAUSE_SPLIT_PATTERN.split(content):
        clause = raw_clause.strip()
        if not clause:
            continue
        clause_dimensions = _dimensions(clause)
        if any(token in clause for token in _REMOVE_TOKENS) and any(
            dimension in excluded for dimension in clause_dimensions
        ):
            continue
        for dimension, tokens in _DIMENSION_TOKENS:
            if dimension not in excluded:
                continue
            for token in tokens:
                clause = re.sub(re.escape(token), "", clause, flags=re.IGNORECASE)
        clause = re.sub(r"\s+", " ", clause).strip(" 、和与及：:")
        if clause:
            clauses.append(clause)
    return "；".join(clauses)


def _time_range(content: str, temporal_context: dict[str, Any]) -> dict[str, Any]:
    interpretation = infer_time_interpretation(content, temporal_context)
    if interpretation:
        clipped = (
            clip_time_interpretation_to_data_range(
                interpretation,
                temporal_context,
            )
            or interpretation
        )
        return {
            "period": "custom",
            "label": str(clipped.get("label") or "自定义时间"),
            "start_date": str(
                clipped.get("effective_start_date") or clipped.get("start_date") or ""
            ),
            "end_date": str(clipped.get("effective_end_date") or clipped.get("end_date") or ""),
            "requested_start_date": clipped.get("requested_start_date"),
            "requested_end_date": clipped.get("requested_end_date"),
            "coverage_clipped": clipped.get("coverage_clipped") is True,
        }
    if any(token in content for token in ("全部时间", "所有时间", "不限时间")) and not any(
        token in content for token in _REMOVE_TOKENS
    ):
        return {"period": "lifetime", "label": "全部时间"}
    year_match = _EXPLICIT_YEAR_PATTERN.search(content)
    if year_match:
        year = year_match.group(1)
        clipped = clip_custom_range_to_data(
            f"{year}-01-01",
            f"{year}-12-31",
            temporal_context,
        )
        return {
            "period": "custom",
            "label": f"{year}年",
            "start_date": clipped.get("effective_start_date") or f"{year}-01-01",
            "end_date": clipped.get("effective_end_date") or f"{year}-12-31",
            "requested_start_date": clipped.get("requested_start_date"),
            "requested_end_date": clipped.get("requested_end_date"),
            "coverage_clipped": clipped.get("coverage_clipped") is True,
        }
    scope = parse_question_intent(content).time_scope
    if scope in {"last_6_months", "last_4_weeks"}:
        return {"period": scope, "label": scope}
    return {}


def _semantic_action(input_type: str, content: str) -> SteeringAction:
    normalized_type = input_type.strip().casefold()
    if normalized_type == "cancel":
        return "cancel"
    if normalized_type in {
        "replace_constraints",
        "add_requirements",
        "remove_requirements",
        "replace_task",
    }:
        return normalized_type  # type: ignore[return-value]
    if normalized_type == "remove":
        return "remove_requirements"
    if _REPLACE_TASK_PATTERN.search(content):
        return "replace_task"
    if normalized_type in {"followup", "add"}:
        return "add_requirements"
    if any(token in content for token in _REPLACE_TOKENS):
        return "replace_constraints"
    if any(token in content for token in _REMOVE_TOKENS):
        return "remove_requirements"
    if any(token in content for token in _ADD_TOKENS):
        return "add_requirements"
    if any(token in content for token in _CANCEL_TOKENS):
        return "cancel"
    return "replace_constraints"


@dataclass
class AgentSessionState:
    version: int = 1
    active_question: str = ""
    entities: list[str] = field(default_factory=list)
    time_range: dict[str, Any] = field(default_factory=dict)
    metrics: list[str] = field(default_factory=list)
    excluded_dimensions: list[str] = field(default_factory=list)
    filters: dict[str, Any] = field(default_factory=dict)
    pending_requirements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "active_question": self.active_question,
            "entities": list(self.entities),
            "time_range": copy.deepcopy(self.time_range),
            "metrics": list(self.metrics),
            "excluded_dimensions": list(self.excluded_dimensions),
            "filters": copy.deepcopy(self.filters),
            "pending_requirements": list(self.pending_requirements),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> AgentSessionState:
        return cls(
            version=int(value.get("version") or 1),
            active_question=str(value.get("active_question") or ""),
            entities=_unique(
                [str(item) for item in value.get("entities", []) if isinstance(item, str)]
            ),
            time_range=(
                copy.deepcopy(value["time_range"])
                if isinstance(value.get("time_range"), dict)
                else {}
            ),
            metrics=_unique(
                [str(item) for item in value.get("metrics", []) if isinstance(item, str)]
            ),
            excluded_dimensions=_unique(
                [
                    str(item)
                    for item in value.get("excluded_dimensions", [])
                    if isinstance(item, str)
                ]
            ),
            filters=(
                copy.deepcopy(value["filters"]) if isinstance(value.get("filters"), dict) else {}
            ),
            pending_requirements=_unique(
                [
                    str(item)
                    for item in value.get("pending_requirements", [])
                    if isinstance(item, str)
                ]
            ),
        )

    def effective_question(self) -> str:
        parts = [self.active_question, *self.pending_requirements]
        effective = [
            value
            for item in parts
            if (value := _without_excluded_dimensions(item, self.excluded_dimensions))
        ]
        return "；".join(_unique(effective))

    def model_context(self) -> str:
        return "SESSION_CONSTRAINTS（后端已结构化，后续工具选择与回答必须遵守）：" + json.dumps(
            self.to_dict(), ensure_ascii=False, separators=(",", ":")
        )

    def public_constraints(self) -> dict[str, Any]:
        """Return the safe subset allowed in progress/SSE task events."""

        return {
            "entities": list(self.entities),
            "time_range": copy.deepcopy(self.time_range),
            "metrics": list(self.metrics),
            "excluded_dimensions": list(self.excluded_dimensions),
            "filters": copy.deepcopy(self.filters),
        }


@dataclass(frozen=True)
class SessionStateUpdate:
    action: SteeringAction
    state: AgentSessionState
    patch: dict[str, Any]


def initial_session_state(
    request: dict[str, Any],
    *,
    default_filters: dict[str, Any],
    temporal_context: dict[str, Any],
) -> AgentSessionState:
    question = str(request.get("question") or "").strip()
    intent = parse_question_intent(question)
    time_range = _time_range(question, temporal_context)
    filters = {
        key: copy.deepcopy(value)
        for key, value in default_filters.items()
        if key not in {"period", "start_date", "end_date"}
    }
    metrics = [
        metric for metric in intent.requested_metrics if metric not in {"summary", "recent_window"}
    ]
    return AgentSessionState(
        active_question=question,
        entities=_unique(intent.entities),
        time_range=time_range
        or {
            key: copy.deepcopy(value)
            for key, value in default_filters.items()
            if key in {"period", "start_date", "end_date"} and value is not None
        },
        metrics=_unique(metrics),
        filters=filters,
    )


def restore_session_state(
    events: list[dict[str, Any]],
    fallback: AgentSessionState,
) -> AgentSessionState:
    state = fallback
    for event in sorted(events, key=lambda item: int(item.get("sequence") or 0)):
        if event.get("event_type") not in {
            "session_state_initialized",
            "session_state_updated",
        }:
            continue
        payload = event.get("payload")
        value = payload.get("state") if isinstance(payload, dict) else None
        if isinstance(value, dict):
            state = AgentSessionState.from_dict(value)
    return state


def apply_session_input(
    state: AgentSessionState,
    *,
    input_type: str,
    content: str,
    temporal_context: dict[str, Any],
) -> SessionStateUpdate:
    content = content.strip()[:500]
    action = _semantic_action(input_type, content)
    updated = AgentSessionState.from_dict(state.to_dict())
    patch: dict[str, Any] = {}
    if action == "cancel":
        return SessionStateUpdate(action=action, state=updated, patch={})

    replacement = _REPLACE_TASK_PATTERN.search(content)
    requirement = replacement.group("question").strip() if replacement else content
    intent = parse_question_intent(requirement)
    detected_time = _time_range(requirement, temporal_context)
    detected_metrics = [
        metric for metric in intent.requested_metrics if metric not in {"summary", "recent_window"}
    ]
    dimensions = _dimensions(requirement)
    removal_dimensions = _removal_dimensions(requirement)

    if action == "replace_task":
        updated = initial_session_state(
            {"question": requirement},
            default_filters=state.filters,
            temporal_context=temporal_context,
        )
        patch["active_question"] = requirement
    elif action == "remove_requirements":
        removed = removal_dimensions or dimensions
        updated.excluded_dimensions = _unique([*updated.excluded_dimensions, *removed])
        updated.metrics = [item for item in updated.metrics if item not in removed]
        if "personal_billboard" in removed:
            updated.filters["include_billboard"] = False
        patch["excluded_dimensions"] = removed
    else:
        if detected_time:
            updated.time_range = detected_time
            patch["time_range"] = detected_time
        if intent.entities:
            updated.entities = (
                _unique(intent.entities)
                if action == "replace_constraints"
                else _unique([*updated.entities, *intent.entities])
            )
            patch["entities"] = list(updated.entities)
        if detected_metrics:
            updated.metrics = (
                _unique(detected_metrics)
                if action == "replace_constraints"
                else _unique([*updated.metrics, *detected_metrics])
            )
            patch["metrics"] = list(updated.metrics)
        if "personal_billboard" in detected_metrics:
            updated.filters["include_billboard"] = True
            updated.excluded_dimensions = [
                item for item in updated.excluded_dimensions if item != "personal_billboard"
            ]
        if removal_dimensions:
            updated.excluded_dimensions = _unique(
                [*updated.excluded_dimensions, *removal_dimensions]
            )
            updated.metrics = [item for item in updated.metrics if item not in removal_dimensions]
            if "personal_billboard" in removal_dimensions:
                updated.filters["include_billboard"] = False
            patch["excluded_dimensions"] = removal_dimensions
        updated.pending_requirements = _unique([*updated.pending_requirements, requirement])
        patch["pending_requirements"] = list(updated.pending_requirements)

    if "不合并" in requirement:
        updated.filters["merge_enabled"] = False
        patch.setdefault("filters", {})["merge_enabled"] = False
    elif "合并" in requirement:
        updated.filters["merge_enabled"] = True
        patch.setdefault("filters", {})["merge_enabled"] = True
    if any(token in requirement for token in ("包含播客", "包括播客", "不要只看音乐")):
        updated.filters["music_only"] = False
        patch.setdefault("filters", {})["music_only"] = False
    elif "只看音乐" in requirement:
        updated.filters["music_only"] = True
        patch.setdefault("filters", {})["music_only"] = True
    return SessionStateUpdate(action=action, state=updated, patch=patch)


def filters_for_session_state(
    state: AgentSessionState,
    base_filters: dict[str, Any],
) -> dict[str, Any]:
    filters = {**base_filters, **state.filters}
    filters.pop("start_date", None)
    filters.pop("end_date", None)
    filters.update(
        {
            key: value
            for key, value in state.time_range.items()
            if key in {"period", "start_date", "end_date"} and value not in {None, ""}
        }
    )
    return filters
