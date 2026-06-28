"""Read-only allowlist registry for backend-defined AI agent tools."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from pydantic import BaseModel


class UnknownAgentToolError(ValueError):
    """Raised when the agent asks for a tool outside the backend allowlist."""


@dataclass(frozen=True)
class AgentToolResult:
    data: dict[str, Any]
    result_summary: str
    source_range: str


@dataclass(frozen=True)
class AgentToolDefinition:
    name: str
    description: str
    read_only: bool
    params_model: type[BaseModel]
    handler: Callable[[BaseModel], AgentToolResult]


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
            }
            for definition in self._tools.values()
        ]

    def describe_for_model(self) -> list[dict[str, Any]]:
        """Return tool descriptions in the compact shape sent to the planner LLM."""
        return self.list_tools()

    def dispatch(self, tool_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        definition = self.get(tool_name)
        parsed_params = definition.params_model.model_validate(params or {})
        result = definition.handler(parsed_params)
        return {
            "tool_name": definition.name,
            "params_summary": summarize_params(parsed_params),
            "result_summary": result.result_summary,
            "source_range": result.source_range,
            "data": result.data,
        }

    def execute(self, tool_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Compatibility alias for chat agent runners."""
        return self.dispatch(tool_name, params)


@lru_cache(maxsize=1)
def get_default_registry() -> AgentToolRegistry:
    from backend.domains.ai_agent.tools import (
        ANALYSIS_CHARTS_TOOL,
        ANALYSIS_STATS_TOOL,
        BILLBOARD_ENTITY_DETAIL_TOOL,
        COMPARE_ENTITIES_TOOL,
        ENTITY_STATS_TOOL,
        LISTENING_HOURS_TOOL,
        PLAYBACK_RECORDS_TOOL,
        RESOLVE_ENTITY_TOOL,
        WRAPPED_YEARLY_TOOL,
    )

    registry = AgentToolRegistry()
    registry.register(ANALYSIS_STATS_TOOL)
    registry.register(ANALYSIS_CHARTS_TOOL)
    registry.register(PLAYBACK_RECORDS_TOOL)
    registry.register(WRAPPED_YEARLY_TOOL)
    registry.register(ENTITY_STATS_TOOL)
    registry.register(BILLBOARD_ENTITY_DETAIL_TOOL)
    registry.register(LISTENING_HOURS_TOOL)
    registry.register(RESOLVE_ENTITY_TOOL)
    registry.register(COMPARE_ENTITIES_TOOL)
    return registry


def dispatch_tool(tool_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return get_default_registry().dispatch(tool_name, params)


def list_tools() -> list[dict[str, Any]]:
    return get_default_registry().list_tools()


def describe_for_model() -> list[dict[str, Any]]:
    return get_default_registry().describe_for_model()


def execute_tool(tool_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return get_default_registry().execute(tool_name, params)
