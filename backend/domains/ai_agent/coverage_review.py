"""Deterministic coverage review for bounded AI Agent follow-up tool calls."""

from __future__ import annotations

from typing import Any


def _requested_entities(question_intent: dict[str, Any]) -> list[str]:
    entities = question_intent.get("entities")
    if not isinstance(entities, list):
        return []
    return [entity for entity in entities if isinstance(entity, str) and entity.strip()]


def _requested_metrics(question_intent: dict[str, Any]) -> set[str]:
    metrics = question_intent.get("requested_metrics")
    if not isinstance(metrics, list):
        return set()
    return {metric for metric in metrics if isinstance(metric, str)}


def _entity_param(entity_type: str, entity_name: str) -> dict[str, Any]:
    if entity_type == "album":
        return {"entity": "album", "album_name": entity_name}
    if entity_type == "artist":
        return {"entity": "artist", "artist_name": entity_name}
    return {"entity": "track", "track_name": entity_name}


def _track_resolve_call(entity_name: str) -> dict[str, Any]:
    return {
        "tool_name": "resolve_entity",
        "params": {"entity_type": "track", "query": entity_name},
    }


def _missing_call(tool_name: str, entity_type: str, entity_name: str) -> dict[str, Any]:
    if entity_type == "track":
        return _track_resolve_call(entity_name)
    return {"tool_name": tool_name, "params": _entity_param(entity_type, entity_name)}


def _comparison_already_found(
    requested_entities: list[str],
    entities: dict[str, Any],
    coverage: dict[str, Any],
) -> bool:
    comparison = coverage.get("comparison")
    if isinstance(comparison, dict) and comparison.get("compare_entities") == "found":
        return True
    if not requested_entities:
        return False
    return all(
        isinstance(entities.get(entity_name), dict)
        and entities[entity_name].get("compare_entities") == "found"
        for entity_name in requested_entities
    )


def review_coverage(
    question_intent: dict[str, Any],
    coverage: dict[str, Any],
) -> dict[str, Any]:
    """Review evidence coverage and return one bounded follow-up tool plan."""
    if not isinstance(question_intent, dict):
        question_intent = {}
    if not isinstance(coverage, dict):
        coverage = {}

    task_type = question_intent.get("task_type")
    entity_type = str(question_intent.get("entity_type") or "unknown")
    requested_metrics = _requested_metrics(question_intent)
    requested_entities = _requested_entities(question_intent)
    entities = coverage.get("entities")
    if not isinstance(entities, dict):
        entities = {}

    followup_tool_calls: list[dict[str, Any]] = []
    reasons: list[str] = []
    seen_calls: set[tuple[str, str]] = set()

    def add_followup(tool_name: str, entity_name: str, reason: str) -> None:
        if len(followup_tool_calls) >= 4:
            return
        call = _missing_call(tool_name, entity_type, entity_name)
        identity = (call["tool_name"], repr(sorted(call.get("params", {}).items())))
        if identity in seen_calls:
            return
        seen_calls.add(identity)
        followup_tool_calls.append(call)
        reasons.append(reason)

    if task_type == "comparison" and not _comparison_already_found(
        requested_entities,
        entities,
        coverage,
    ):
        for entity_name in requested_entities:
            statuses = entities.get(entity_name, {})
            if not isinstance(statuses, dict):
                statuses = {}
            if statuses.get("entity_stats") != "found":
                add_followup(
                    "entity_stats",
                    entity_name,
                    f"{entity_name} 缺少播放统计",
                )
            if (
                "personal_billboard" in requested_metrics
                and statuses.get("billboard_entity_detail") != "found"
            ):
                add_followup(
                    "billboard_entity_detail",
                    entity_name,
                    f"{entity_name} 缺少个人榜单证据",
                )

    return {
        "sufficient": len(followup_tool_calls) == 0,
        "reasons": reasons,
        "followup_tool_calls": followup_tool_calls,
    }
