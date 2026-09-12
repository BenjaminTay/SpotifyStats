"""Read-only allowlist registry for backend-defined AI agent tools."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel


class UnknownAgentToolError(ValueError):
    """Raised when the agent asks for a tool outside the backend allowlist."""


@dataclass(frozen=True)
class AgentToolResult:
    data: dict[str, Any]
    result_summary: str
    source_range: str
    cache_hit: bool = False


@dataclass(frozen=True)
class AgentToolDefinition:
    name: str
    description: str
    read_only: bool
    params_model: type[BaseModel]
    handler: Callable[[BaseModel], AgentToolResult]
    cost: Literal["low", "medium", "high"] = "low"
    timeout_seconds: float = 30.0
    cacheability: Literal["none", "revision"] = "none"
    supports_parallel: bool = True
    best_for: tuple[str, ...] = ()
    covers: tuple[str, ...] = ()
    cold_build_risk: Literal["none", "low", "medium", "high"] = "none"
    avoid_when: tuple[str, ...] = ()
    fallback: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("AI agent tool timeout_seconds must be positive")

    def runtime_metadata(self) -> dict[str, Any]:
        return {
            "cost": self.cost,
            "timeout_seconds": self.timeout_seconds,
            "cacheability": self.cacheability,
            "supports_parallel": self.supports_parallel,
        }

    def routing_metadata(self) -> dict[str, Any]:
        """Return machine-readable guidance safe to expose to the model."""

        return {
            "best_for": list(self.best_for),
            "covers": list(self.covers),
            "cost": self.cost,
            "parallel_safe": self.supports_parallel,
            "cold_build_risk": self.cold_build_risk,
            "avoid_when": list(self.avoid_when),
            "fallback": list(self.fallback),
        }


def summarize_params(params: BaseModel) -> str:
    values = params.model_dump(exclude_none=True)
    parts = []
    for key, value in values.items():
        if isinstance(value, bool):
            rendered = str(value).lower()
        else:
            rendered = str(value)
        parts.append(f"{key}={rendered}")
    return ", ".join(parts)


class AgentToolRegistry:
    """Registry for backend-owned, read-only tool definitions."""

    def __init__(self) -> None:
        self._tools: dict[str, AgentToolDefinition] = {}

    def register(self, definition: AgentToolDefinition) -> None:
        if not definition.read_only:
            raise ValueError("AI agent tools must be read-only")
        if definition.name in self._tools:
            raise ValueError(f"AI agent tool already registered: {definition.name}")
        self._tools[definition.name] = definition

    def get(self, tool_name: str) -> AgentToolDefinition:
        try:
            return self._tools[tool_name]
        except KeyError as exc:
            raise UnknownAgentToolError(f"Unknown AI agent tool: {tool_name}") from exc

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": definition.name,
                "description": definition.description,
                "read_only": definition.read_only,
                "params_schema": definition.params_model.model_json_schema(),
                "runtime": definition.runtime_metadata(),
                "routing": definition.routing_metadata(),
            }
            for definition in self._tools.values()
        ]

    def describe_for_model(self) -> list[dict[str, Any]]:
        """Return tool descriptions in the compact shape sent to the planner LLM."""
        return self.list_tools()

    def runtime_metadata(self, tool_name: str) -> dict[str, Any]:
        """Return scheduling metadata without exposing the executable handler."""
        return self.get(tool_name).runtime_metadata()

    def dispatch(self, tool_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        definition = self.get(tool_name)
        parsed_params = definition.params_model.model_validate(params or {})
        result = definition.handler(parsed_params)
        return {
            "tool_name": definition.name,
            "params_summary": summarize_params(parsed_params),
            "result_summary": result.result_summary,
            "source_range": result.source_range,
            "cache_hit": result.cache_hit,
            "data": result.data,
        }

    def execute(self, tool_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Compatibility alias for chat agent runners."""
        return self.dispatch(tool_name, params)


@lru_cache(maxsize=1)
def get_default_registry() -> AgentToolRegistry:
    from backend.domains.ai_agent.tools import (
        ACCOUNT_COLLECTION_INSIGHTS_TOOL,
        ACCOUNT_SUMMARY_TOOL,
        ANALYSIS_CHARTS_TOOL,
        ANALYSIS_STATS_TOOL,
        BILLBOARD_ENTITY_DETAIL_TOOL,
        COMMUNITY_FEED_SEARCH_TOOL,
        COMMUNITY_TRENDING_TOOL,
        COMPARE_ENTITIES_TOOL,
        ENTITY_STATS_TOOL,
        LISTENING_HOURS_TOOL,
        PLAYBACK_RECORDS_TOOL,
        RESOLVE_ENTITY_TOOL,
        SEARCH_HISTORY_TOOL,
        TASTE_PROFILE_TOOL,
        WRAPPED_YEARLY_TOOL,
    )
    from backend.domains.ai_agent.web_search_tool import WEB_SEARCH_TOOL

    registry = AgentToolRegistry()
    registry.register(ANALYSIS_STATS_TOOL)
    registry.register(ANALYSIS_CHARTS_TOOL)
    registry.register(TASTE_PROFILE_TOOL)
    registry.register(PLAYBACK_RECORDS_TOOL)
    registry.register(WRAPPED_YEARLY_TOOL)
    registry.register(ENTITY_STATS_TOOL)
    registry.register(BILLBOARD_ENTITY_DETAIL_TOOL)
    registry.register(LISTENING_HOURS_TOOL)
    registry.register(RESOLVE_ENTITY_TOOL)
    registry.register(COMPARE_ENTITIES_TOOL)
    registry.register(ACCOUNT_SUMMARY_TOOL)
    registry.register(ACCOUNT_COLLECTION_INSIGHTS_TOOL)
    registry.register(SEARCH_HISTORY_TOOL)
    registry.register(COMMUNITY_FEED_SEARCH_TOOL)
    registry.register(COMMUNITY_TRENDING_TOOL)
    registry.register(WEB_SEARCH_TOOL)
    return registry


def dispatch_tool(tool_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return get_default_registry().dispatch(tool_name, params)


def list_tools() -> list[dict[str, Any]]:
    return get_default_registry().list_tools()


def describe_for_model() -> list[dict[str, Any]]:
    return get_default_registry().describe_for_model()


def execute_tool(tool_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return get_default_registry().execute(tool_name, params)
