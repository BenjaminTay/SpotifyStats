"""Deterministic tool-schema routing based on the parsed question frame."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from backend.domains.ai_agent.tool_registry import AgentToolRegistry

_FAMILY_TOOLS: dict[str, tuple[str, ...]] = {
    "simple_ranking": ("analysis_charts", "analysis_stats", "wrapped_yearly"),
    "scoped_ranking": (
        "entity_stats",
        "resolve_entity",
        "billboard_entity_detail",
        "analysis_charts",
    ),
    "entity_detail": ("entity_stats", "resolve_entity", "billboard_entity_detail"),
    "preference_comparison": (
        "compare_entities",
        "entity_stats",
        "resolve_entity",
        "billboard_entity_detail",
    ),
    "identity_preference": (
        "compare_entities",
        "entity_stats",
        "billboard_entity_detail",
        "resolve_entity",
    ),
    "trend_preference": ("entity_stats", "analysis_charts", "compare_entities"),
    "period_comparison": ("analysis_charts", "wrapped_yearly", "analysis_stats"),
    "change_explanation": (
        "entity_stats",
        "analysis_charts",
        "compare_entities",
        "listening_hours",
    ),
    "time_of_day_ranking": ("listening_hours", "analysis_charts", "analysis_stats"),
    "account_collection": ("account_collection_insights", "account_summary"),
    "search_behavior": ("search_history",),
    "community_lookup": ("community_trending", "community_feed_search"),
    "habit_summary": ("analysis_stats", "analysis_charts", "listening_hours"),
    "safety_boundary": (),
}


@dataclass(frozen=True)
class AgentProfile:
    name: str
    family: str
    tool_names: tuple[str, ...]


def select_agent_profile(
    question_context: dict[str, Any],
    registry: AgentToolRegistry,
) -> AgentProfile:
    frame = question_context.get("question_frame")
    frame = frame if isinstance(frame, dict) else {}
    family = str(frame.get("family") or "habit_summary")
    preferred = _FAMILY_TOOLS.get(family, _FAMILY_TOOLS["habit_summary"])
    definitions = {item["name"]: registry.get(item["name"]) for item in registry.list_tools()}
    frame_axes = {
        str(axis) for axis in (frame.get("analysis_axes") or []) if isinstance(axis, str) and axis
    }
    recipe = question_context.get("evidence_recipe")
    recipe = recipe if isinstance(recipe, dict) else {}
    required_names = {
        str(pattern.get("tool_name"))
        for pattern in (recipe.get("required_tool_patterns") or [])
        if isinstance(pattern, dict) and pattern.get("tool_name")
    }
    signals = question_context.get("routing_signals")
    signals = signals if isinstance(signals, dict) else {}
    explicit_billboard = signals.get("explicit_billboard") is True
    comparison_shape = (
        frame.get("task_type") == "comparison" and 2 <= len(frame.get("entities") or []) <= 4
    )

    candidate_names = list(preferred)
    primary_names: set[str] = set()
    if comparison_shape and "compare_entities" not in candidate_names:
        candidate_names.insert(0, "compare_entities")
    if comparison_shape:
        primary_names.add("compare_entities")
    if explicit_billboard and "billboard_entity_detail" not in candidate_names:
        candidate_names.append("billboard_entity_detail")
    candidates = [
        name
        for name in candidate_names
        if name in definitions and (name != "billboard_entity_detail" or explicit_billboard)
    ]
    cost_rank = {"low": 0, "medium": 1, "high": 2}
    risk_rank = {"none": 0, "low": 1, "medium": 2, "high": 3}
    preferred_index = {name: index for index, name in enumerate(candidate_names)}

    def routing_key(name: str) -> tuple[int, int, int, int, int]:
        definition = definitions[name]
        coverage = len(frame_axes.intersection(definition.covers))
        return (
            0 if name in primary_names else 1 if name in required_names else 2,
            -coverage,
            cost_rank[definition.cost],
            risk_rank[definition.cold_build_risk],
            preferred_index[name],
        )

    selected = tuple(sorted(candidates, key=routing_key))
    if not selected and family != "safety_boundary":
        # Custom/test registries may only expose one safe tool. Keep routing usable
        # without broadening the production profile beyond the registry allowlist.
        selected = tuple(sorted(definitions)[:6])
    return AgentProfile(name=f"chat:{family}", family=family, tool_names=selected[:6])


def tool_schemas_for_profile(
    registry: AgentToolRegistry,
    profile: AgentProfile,
) -> list[dict[str, Any]]:
    by_name = {item["name"]: item for item in registry.list_tools()}
    schemas = [
        {
            "name": item["name"],
            "description": (
                f"{item['description']}\n"
                "ROUTING_METADATA="
                + json.dumps(item["routing"], ensure_ascii=False, separators=(",", ":"))
            ),
            "parameters": item["params_schema"],
        }
        for name in profile.tool_names
        if (item := by_name.get(name)) is not None
    ]
    return schemas


def select_report_profile(registry: AgentToolRegistry) -> AgentProfile:
    """Bound yearly research to the six tools that can support its evidence contract."""

    preferred = (
        "analysis_stats",
        "analysis_charts",
        "wrapped_yearly",
        "entity_stats",
        "billboard_entity_detail",
        "web_search",
    )
    available = {item["name"] for item in registry.list_tools()}
    selected = tuple(name for name in preferred if name in available)
    if not selected:
        selected = tuple(sorted(available)[:6])
    return AgentProfile(name="report:yearly", family="yearly_report", tool_names=selected)
