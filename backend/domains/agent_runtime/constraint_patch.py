"""Versioned, deterministic constraint patches for Agent steering.

The model may propose a patch in the future, but validation, merging and the
fingerprint are deliberately owned by the backend.  This module operates on a
plain state mapping so it can be used by the current dataclass session state
without coupling the Pydantic contract to persistence details.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.domains.ai_agent.question_intent import parse_question_intent
from backend.domains.ai_agent.temporal_context import (
    clip_custom_range_to_data,
    clip_time_interpretation_to_data_range,
    infer_time_interpretation,
)

ConstraintOperation = Literal["add", "remove", "replace", "reset"]
ValidationDecision = Literal["apply", "clarify", "reject"]

CONSTRAINT_PATCH_SCHEMA_VERSION: Literal[2] = 2
CONSTRAINT_FINGERPRINT_VERSION = 2

_CLAUSE_SPLIT_PATTERN = re.compile(r"[，,。；;\n]+")
_CORRECTED_YEAR_PATTERN = re.compile(
    r"(?:不是|不要|并非)\s*(20\d{2})\s*年?\s*[，,、]?\s*(?:是|而是|改为|改成)\s*(20\d{2})"
)
_EXPLICIT_YEAR_PATTERN = re.compile(r"(20\d{2}|2100)")
_ENTITY_REPLACEMENT_PATTERN = re.compile(
    r"把\s*(?P<old>[^，,。；;]{1,100}?)\s*(?:换成|替换为|改成)\s*"
    r"(?P<new>[^，,。；;]{1,100})",
    re.IGNORECASE,
)
_RESET_PATTERN = re.compile(
    r"(?:重新开始|重置(?:全部|所有)?(?:条件|约束)?|清空(?:全部|所有)?(?:条件|约束)?)"
)
_REMOVE_TOKENS = ("不要", "不用", "不看", "排除", "去掉", "移除", "别看", "无需", "删除")
_REPLACE_TOKENS = (
    "只看",
    "仅看",
    "只保留",
    "改成",
    "改为",
    "换成",
    "限定",
    "改到",
    "不是",
    "only",
)
_ADD_TOKENS = ("再", "还要", "同时", "另外", "补充", "也看", "加上", "include")
_REFERENCE_TOKENS = (
    "它",
    "它们",
    "那个",
    "这一个",
    "前一个",
    "后一个",
    "前者",
    "后者",
    "那一年",
    "同期",
)
_DIMENSION_TOKENS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("personal_billboard", ("billboard", "个人榜", "冠军周", "在榜周", "power score")),
    ("album_ranking", ("专辑榜", "专辑排行", "album ranking")),
    ("track_ranking", ("歌曲榜", "单曲榜", "歌曲排行", "track ranking")),
    ("artist_ranking", ("艺人榜", "歌手榜", "艺人排行", "artist ranking")),
    ("time_of_day", ("深夜", "凌晨", "时段", "几点", "time of day")),
    ("ranking", ("排名", "排行", "top")),
    ("external_context", ("外部", "联网", "网页", "市场", "external")),
)
_METRIC_TOKENS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("plays", ("播放次数", "播放量", "次数", "plays", "play count")),
    ("hours", ("播放时长", "收听时长", "时长", "小时", "hours", "duration")),
    ("personal_billboard", ("billboard", "个人榜", "冠军周", "在榜周", "power score")),
    ("time_of_day", ("深夜", "凌晨", "时段", "几点", "time of day")),
)
_ALLOWED_FILTERS = {
    "include_billboard",
    "merge_enabled",
    "music_only",
    "min_ms",
    "platform",
    "source",
}


def _unique(values: list[str], *, limit: int = 24) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = re.sub(r"\s+", " ", str(value)).strip(" \t\r\n,，。？?：:；;")
        key = normalized.casefold()
        if normalized and key not in seen:
            result.append(normalized)
            seen.add(key)
    return result[:limit]


def _iso_date(value: Any) -> str | None:
    if value in {None, ""}:
        return None
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except (TypeError, ValueError):
        return None


class ConstraintTimeRange(BaseModel):
    """One requested or effective query window."""

    model_config = ConfigDict(extra="forbid")

    period: str = "custom"
    label: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    coverage_clipped: bool = False
    no_observed_overlap: bool = False

    @field_validator("period")
    @classmethod
    def _normalize_period(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if not normalized:
            raise ValueError("period must not be empty")
        return normalized

    @field_validator("start_date", "end_date")
    @classmethod
    def _validate_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = _iso_date(value)
        if normalized is None:
            raise ValueError("time range dates must be ISO dates")
        return normalized

    @model_validator(mode="after")
    def _validate_order(self) -> ConstraintTimeRange:
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("time range start_date must not be after end_date")
        return self


class ConstraintPatch(BaseModel):
    """The only supported V2 steering mutation contract."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = CONSTRAINT_PATCH_SCHEMA_VERSION
    operation: ConstraintOperation
    entities: list[str] = Field(default_factory=list, max_length=24)
    metrics: list[str] = Field(default_factory=list, max_length=24)
    dimensions: list[str] = Field(default_factory=list, max_length=24)
    excluded_dimensions: list[str] = Field(default_factory=list, max_length=24)
    filters: dict[str, Any] = Field(default_factory=dict)
    requested_time_range: ConstraintTimeRange | None = None
    effective_time_range: ConstraintTimeRange | None = None
    output_format: str | None = None
    comparison_mode: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    unresolved_references: list[str] = Field(default_factory=list, max_length=12)
    source_text: str = Field(default="", max_length=500)

    @field_validator(
        "entities",
        "metrics",
        "dimensions",
        "excluded_dimensions",
        "unresolved_references",
    )
    @classmethod
    def _normalize_lists(cls, values: list[str]) -> list[str]:
        return _unique(values)

    @field_validator("filters")
    @classmethod
    def _validate_filters(cls, value: dict[str, Any]) -> dict[str, Any]:
        unknown = sorted(set(value) - _ALLOWED_FILTERS)
        if unknown:
            raise ValueError(f"unsupported constraint filters: {', '.join(unknown)}")
        return copy.deepcopy(value)

    @field_validator("output_format", "comparison_mode")
    @classmethod
    def _normalize_optional_text(cls, value: str | None) -> str | None:
        normalized = re.sub(r"\s+", "_", value.strip().casefold()) if value else None
        return normalized or None

    @model_validator(mode="after")
    def _validate_time_pair(self) -> ConstraintPatch:
        if bool(self.requested_time_range) != bool(self.effective_time_range):
            raise ValueError(
                "requested_time_range and effective_time_range must be supplied together"
            )
        if self.operation == "reset" and any(
            (
                self.entities,
                self.metrics,
                self.dimensions,
                self.excluded_dimensions,
                self.filters,
                self.requested_time_range,
                self.output_format,
                self.comparison_mode,
            )
        ):
            raise ValueError("reset patches cannot carry constraint values")
        return self


class ConstraintPatchValidation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: ValidationDecision
    issues: list[str] = Field(default_factory=list)
    high_risk_ambiguity: bool = False


class ConstraintMergeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: dict[str, Any]
    previous_fingerprint: str
    constraint_fingerprint: str
    constraints_changed: bool
    evidence_invalidated: bool
    validation: ConstraintPatchValidation


def _tokens_for(content: str, definitions: tuple[tuple[str, tuple[str, ...]], ...]) -> list[str]:
    lowered = content.casefold()
    return [
        name for name, tokens in definitions if any(token.casefold() in lowered for token in tokens)
    ]


def _negative_clauses(content: str) -> list[str]:
    return [
        clause.strip()
        for clause in _CLAUSE_SPLIT_PATTERN.split(content)
        if clause.strip() and any(token in clause for token in _REMOVE_TOKENS)
    ]


def _positive_content(content: str) -> str:
    return "；".join(
        clause.strip()
        for clause in _CLAUSE_SPLIT_PATTERN.split(content)
        if clause.strip() and not any(token in clause for token in _REMOVE_TOKENS)
    )


def _infer_operation(input_type: str, content: str) -> ConstraintOperation:
    normalized_type = input_type.strip().casefold()
    if _RESET_PATTERN.search(content) or normalized_type == "reset":
        return "reset"
    if normalized_type in {"add", "followup", "add_requirements"}:
        return "add"
    if normalized_type in {"remove", "remove_requirements"}:
        return "remove"
    if normalized_type in {"replace", "replace_constraints", "steer"}:
        if any(token in content for token in _REPLACE_TOKENS):
            return "replace"
        if any(token in content for token in _REMOVE_TOKENS) and not any(
            token in content for token in _ADD_TOKENS
        ):
            return "remove"
    if any(token in content for token in _REPLACE_TOKENS):
        return "replace"
    if any(token in content for token in _REMOVE_TOKENS):
        return "remove"
    if any(token in content for token in _ADD_TOKENS):
        return "add"
    return "replace"


def _time_ranges(
    content: str,
    temporal_context: Mapping[str, Any],
) -> tuple[ConstraintTimeRange | None, ConstraintTimeRange | None, list[str]]:
    corrected = _CORRECTED_YEAR_PATTERN.search(content)
    time_text = corrected.group(2) if corrected else content
    years = _EXPLICIT_YEAR_PATTERN.findall(content)
    unresolved: list[str] = []
    positive_time_text = _positive_content(content)
    has_lifetime = any(
        token in positive_time_text for token in ("全部时间", "所有时间", "不限时间", "lifetime")
    )
    has_bounded_time = (
        bool(years)
        or infer_time_interpretation(
            positive_time_text,
            dict(temporal_context),
        )
        is not None
    )
    if has_lifetime and has_bounded_time:
        unresolved.append("multiple_time_scopes")
        return None, None, unresolved
    if len(set(years)) > 1 and corrected is None:
        unresolved.append("time_range_conflict")
        return None, None, unresolved

    interpretation = infer_time_interpretation(time_text, dict(temporal_context))
    if interpretation is None:
        year_match = _EXPLICIT_YEAR_PATTERN.search(time_text)
        if year_match:
            year = year_match.group(1)
            clipped = clip_custom_range_to_data(
                f"{year}-01-01",
                f"{year}-12-31",
                dict(temporal_context),
            )
            label = f"{year}年"
            requested = ConstraintTimeRange(
                period="custom",
                label=label,
                start_date=clipped.get("requested_start_date") or f"{year}-01-01",
                end_date=clipped.get("requested_end_date") or f"{year}-12-31",
            )
            effective = ConstraintTimeRange(
                period="custom",
                label=label,
                start_date=clipped.get("effective_start_date"),
                end_date=clipped.get("effective_end_date"),
                coverage_clipped=clipped.get("coverage_clipped") is True,
                no_observed_overlap=clipped.get("no_observed_overlap") is True,
            )
            return requested, effective, unresolved
        if any(token in content for token in ("全部时间", "所有时间", "不限时间", "lifetime")):
            lifetime = ConstraintTimeRange(period="lifetime", label="全部时间")
            return lifetime, lifetime.model_copy(deep=True), unresolved
        return None, None, unresolved

    clipped = (
        clip_time_interpretation_to_data_range(
            interpretation,
            dict(temporal_context),
        )
        or interpretation
    )
    requested = ConstraintTimeRange(
        period="custom",
        label=str(clipped.get("label") or "自定义时间"),
        start_date=clipped.get("requested_start_date") or clipped.get("start_date"),
        end_date=clipped.get("requested_end_date") or clipped.get("end_date"),
    )
    effective = ConstraintTimeRange(
        period="custom",
        label=str(clipped.get("label") or "自定义时间"),
        start_date=clipped.get("effective_start_date") or clipped.get("start_date"),
        end_date=clipped.get("effective_end_date") or clipped.get("end_date"),
        coverage_clipped=clipped.get("coverage_clipped") is True,
        no_observed_overlap=clipped.get("no_observed_overlap") is True,
    )
    return requested, effective, unresolved


def _replacement_entities(content: str) -> tuple[list[str], str | None]:
    match = _ENTITY_REPLACEMENT_PATTERN.search(content)
    if not match:
        return [], None
    target = match.group("old").strip()
    replacement_text = match.group("new").strip()
    parsed = parse_question_intent(f"比较 {replacement_text} 这位艺人").entities
    return (_unique(parsed) or [replacement_text]), target


def _output_format(content: str) -> str | None:
    lowered = content.casefold()
    if "markdown" in lowered and "表格" in content:
        return "markdown_table"
    if "表格" in content or "table" in lowered:
        return "table"
    if "列表" in content or "list" in lowered:
        return "list"
    if "json" in lowered:
        return "json"
    if any(token in content for token in ("简短", "简洁", "一句话")):
        return "concise"
    if any(token in content for token in ("详细", "展开说明")):
        return "detailed"
    return None


def _comparison_mode(content: str) -> str | None:
    lowered = content.casefold()
    if any(token in content for token in ("周均", "每周平均")):
        return "weekly_average"
    if any(token in content for token in ("月均", "每月平均")):
        return "monthly_average"
    if any(token in content for token in ("同比", "同一时间窗口", "共同区间", "公平比较")):
        return "common_window"
    if any(token in content for token in ("占比", "百分比")) or "percentage" in lowered:
        return "percentage"
    if any(token in content for token in ("绝对值", "总量")):
        return "absolute"
    return None


def build_constraint_patch(
    *,
    input_type: str,
    content: str,
    temporal_context: Mapping[str, Any],
    current_state: Mapping[str, Any] | None = None,
) -> ConstraintPatch:
    """Parse deterministic high-confidence steering signals into a V2 patch."""

    source = content.strip()[:500]
    operation = _infer_operation(input_type, source)
    if operation == "reset":
        return ConstraintPatch(operation="reset", source_text=source)

    positive = _positive_content(source) or source
    negative_clauses = _negative_clauses(source)
    removed_dimensions = _unique(
        [item for clause in negative_clauses for item in _tokens_for(clause, _DIMENSION_TOKENS)]
    )
    removed_metrics = _unique(
        [item for clause in negative_clauses for item in _tokens_for(clause, _METRIC_TOKENS)]
    )
    dimensions = _tokens_for(positive, _DIMENSION_TOKENS)
    intent = parse_question_intent(positive)
    metrics = _unique(
        [
            metric
            for metric in [*_tokens_for(positive, _METRIC_TOKENS), *intent.requested_metrics]
            if metric not in {"summary", "recent_window"}
        ]
    )

    entities, replacement_target = _replacement_entities(source)
    state_entities = _unique(
        [str(item) for item in (current_state or {}).get("entities", []) if isinstance(item, str)]
    )
    if replacement_target and entities:
        replacement = entities[0]
        target_key = replacement_target.casefold()
        matched_target = next(
            (item for item in state_entities if item.casefold() == target_key),
            None,
        )
        if replacement_target in {"它", "那个", "这一个"} and len(state_entities) == 1:
            matched_target = state_entities[0]
        if matched_target is not None:
            entities = _unique(
                [replacement if item == matched_target else item for item in state_entities]
            )
    if not entities:
        entities = _unique(intent.entities)

    requested_time, effective_time, unresolved = _time_ranges(source, temporal_context)
    if replacement_target and replacement_target in {"它", "那个", "这一个"}:
        if len(state_entities) != 1:
            unresolved.append("entity_reference")
    for token in _REFERENCE_TOKENS:
        if token not in source:
            continue
        if (
            token in {"它", "那个", "这一个"}
            and replacement_target == token
            and len(state_entities) == 1
        ):
            continue
        if token in {"它", "那个", "这一个"} and replacement_target == token:
            continue
        if token == "同期" and current_state and current_state.get("time_range"):
            continue
        unresolved.append(token)

    filters: dict[str, Any] = {}
    if "不合并" in source:
        filters["merge_enabled"] = False
    elif "合并" in source:
        filters["merge_enabled"] = True
    if any(token in source for token in ("包含播客", "包括播客", "不要只看音乐")):
        filters["music_only"] = False
    elif "只看音乐" in source:
        filters["music_only"] = True
    if "personal_billboard" in removed_dimensions or "personal_billboard" in removed_metrics:
        filters["include_billboard"] = False
    elif "personal_billboard" in dimensions or "personal_billboard" in metrics:
        filters["include_billboard"] = True

    if operation == "remove":
        dimensions = _unique([*removed_dimensions, *dimensions])
        metrics = _unique([*removed_metrics, *metrics])
    confidence = 0.4 if unresolved else 1.0
    return ConstraintPatch(
        operation=operation,
        entities=entities,
        metrics=metrics,
        dimensions=dimensions,
        excluded_dimensions=removed_dimensions,
        filters=filters,
        requested_time_range=requested_time,
        effective_time_range=effective_time,
        output_format=_output_format(source),
        comparison_mode=_comparison_mode(source),
        confidence=confidence,
        unresolved_references=_unique(unresolved),
        source_text=source,
    )


def validate_constraint_patch(
    patch: ConstraintPatch,
    *,
    current_state: Mapping[str, Any] | None = None,
) -> ConstraintPatchValidation:
    """Return an apply/clarify/reject decision without mutating state."""

    issues: list[str] = []
    if patch.unresolved_references:
        issues.extend(f"unresolved:{item}" for item in patch.unresolved_references)
    if patch.operation != "reset" and not any(
        (
            patch.entities,
            patch.metrics,
            patch.dimensions,
            patch.excluded_dimensions,
            patch.filters,
            patch.requested_time_range,
            patch.output_format,
            patch.comparison_mode,
        )
    ):
        issues.append("empty_patch")
    if patch.operation == "remove" and patch.requested_time_range is not None:
        issues.append("cannot_remove_time_range_without_explicit_replacement")
    if patch.operation == "remove" and patch.entities:
        known = {
            str(item).casefold()
            for item in (current_state or {}).get("entities", [])
            if isinstance(item, str)
        }
        missing = [item for item in patch.entities if item.casefold() not in known]
        if missing:
            issues.append("remove_unknown_entity")
    high_risk = bool(patch.unresolved_references) or any(
        issue
        in {
            "cannot_remove_time_range_without_explicit_replacement",
            "remove_unknown_entity",
        }
        for issue in issues
    )
    if high_risk or patch.confidence < 0.5:
        decision: ValidationDecision = "clarify"
    elif "empty_patch" in issues:
        decision = "reject"
    else:
        decision = "apply"
    return ConstraintPatchValidation(
        decision=decision,
        issues=issues,
        high_risk_ambiguity=high_risk,
    )


def _canonical_state(state: Mapping[str, Any]) -> dict[str, Any]:
    time_range = state.get("time_range") if isinstance(state.get("time_range"), dict) else {}
    return {
        "fingerprint_version": CONSTRAINT_FINGERPRINT_VERSION,
        "entities": sorted(
            _unique([str(item) for item in state.get("entities", []) if isinstance(item, str)]),
            key=str.casefold,
        ),
        "time_range": {
            key: copy.deepcopy(time_range.get(key))
            for key in (
                "period",
                "start_date",
                "end_date",
                "requested_start_date",
                "requested_end_date",
                "coverage_clipped",
                "no_observed_overlap",
            )
            if time_range.get(key) not in {None, ""}
        },
        "metrics": sorted(
            _unique([str(item) for item in state.get("metrics", []) if isinstance(item, str)]),
            key=str.casefold,
        ),
        "dimensions": sorted(
            _unique([str(item) for item in state.get("dimensions", []) if isinstance(item, str)]),
            key=str.casefold,
        ),
        "excluded_dimensions": sorted(
            _unique(
                [
                    str(item)
                    for item in state.get("excluded_dimensions", [])
                    if isinstance(item, str)
                ]
            ),
            key=str.casefold,
        ),
        "filters": copy.deepcopy(state.get("filters"))
        if isinstance(state.get("filters"), dict)
        else {},
        "output_format": state.get("output_format"),
        "comparison_mode": state.get("comparison_mode"),
    }


def constraint_fingerprint(state: Mapping[str, Any]) -> str:
    payload = json.dumps(
        _canonical_state(state),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _legacy_time_range(patch: ConstraintPatch) -> dict[str, Any]:
    requested = patch.requested_time_range
    effective = patch.effective_time_range
    if requested is None or effective is None:
        return {}
    return {
        "period": effective.period,
        "label": effective.label or requested.label,
        "start_date": effective.start_date,
        "end_date": effective.end_date,
        "requested_start_date": requested.start_date,
        "requested_end_date": requested.end_date,
        "coverage_clipped": effective.coverage_clipped,
        "no_observed_overlap": effective.no_observed_overlap,
    }


def merge_constraint_patch(
    state: Mapping[str, Any],
    patch: ConstraintPatch,
    *,
    reset_state: Mapping[str, Any] | None = None,
) -> ConstraintMergeResult:
    """Apply a validated field-local patch and compute evidence invalidation."""

    original = copy.deepcopy(dict(state))
    previous_fingerprint = constraint_fingerprint(original)
    validation = validate_constraint_patch(patch, current_state=original)
    if validation.decision != "apply":
        unchanged = copy.deepcopy(original)
        unchanged["constraint_fingerprint"] = previous_fingerprint
        return ConstraintMergeResult(
            state=unchanged,
            previous_fingerprint=previous_fingerprint,
            constraint_fingerprint=previous_fingerprint,
            constraints_changed=False,
            evidence_invalidated=False,
            validation=validation,
        )

    if patch.operation == "reset":
        updated = copy.deepcopy(dict(reset_state or {}))
        updated.setdefault("version", CONSTRAINT_PATCH_SCHEMA_VERSION)
    else:
        updated = copy.deepcopy(original)
        updated["version"] = max(int(updated.get("version") or 1), CONSTRAINT_PATCH_SCHEMA_VERSION)

        list_fields = ("entities", "metrics", "dimensions")
        for field_name in list_fields:
            values = list(getattr(patch, field_name))
            if not values:
                continue
            current = [str(item) for item in updated.get(field_name, []) if isinstance(item, str)]
            if patch.operation == "add":
                updated[field_name] = _unique([*current, *values])
            elif patch.operation == "remove":
                removal = {item.casefold() for item in values}
                updated[field_name] = [item for item in current if item.casefold() not in removal]
            else:
                updated[field_name] = _unique(values)

        excluded = [
            str(item) for item in updated.get("excluded_dimensions", []) if isinstance(item, str)
        ]
        if patch.excluded_dimensions:
            excluded = _unique([*excluded, *patch.excluded_dimensions])
        if patch.operation in {"add", "replace"} and patch.dimensions:
            restored = {item.casefold() for item in patch.dimensions}
            excluded = [item for item in excluded if item.casefold() not in restored]
        updated["excluded_dimensions"] = excluded

        if patch.requested_time_range and patch.effective_time_range:
            updated["time_range"] = _legacy_time_range(patch)
        if patch.filters:
            current_filters = (
                updated.get("filters") if isinstance(updated.get("filters"), dict) else {}
            )
            updated["filters"] = {**copy.deepcopy(current_filters), **copy.deepcopy(patch.filters)}
        if patch.output_format is not None:
            updated["output_format"] = patch.output_format
        if patch.comparison_mode is not None:
            updated["comparison_mode"] = patch.comparison_mode

    fingerprint = constraint_fingerprint(updated)
    updated["constraint_fingerprint"] = fingerprint
    changed = fingerprint != previous_fingerprint
    return ConstraintMergeResult(
        state=updated,
        previous_fingerprint=previous_fingerprint,
        constraint_fingerprint=fingerprint,
        constraints_changed=changed,
        evidence_invalidated=changed,
        validation=validation,
    )
