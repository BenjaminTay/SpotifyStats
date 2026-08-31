"""Validated read-only tool execution for Agent V2."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from backend.domains.agent_runtime.event_log import AgentEventLog
from backend.domains.agent_runtime.serialization import compact_value
from backend.domains.ai_agent.tool_registry import AgentToolRegistry
from backend.domains.ai_tasks.repository import AiTaskRepository


@dataclass(frozen=True)
class ToolOutcome:
    call_id: str
    tool_name: str
    status: str
    params: dict[str, Any]
    params_summary: str
    result_summary: str
    source_range: str
    data: dict[str, Any]
    error: str | None = None
    duplicate: bool = False

    def model_payload(self) -> dict[str, Any]:
        return compact_value(
            {
                "status": self.status,
                "tool_name": self.tool_name,
                "result_summary": self.result_summary,
                "source_range": self.source_range,
                "data": self.data,
                "error": self.error,
                "duplicate": self.duplicate,
            }
        )

    def legacy_payload(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "status": self.status,
            "params": self.params,
            "params_summary": self.params_summary,
            "result_summary": self.result_summary,
            "source_range": self.source_range,
            "data": self.data,
            "error": self.error,
        }


def _result_status(data: dict[str, Any]) -> str:
    if data.get("status") in {"empty", "partial", "error"}:
        return str(data["status"])
    if data.get("found") is False:
        return "empty"
    if data.get("partial") is True or data.get("is_partial") is True:
        return "partial"
    return "ok"


class ToolRuntime:
    def __init__(
        self,
        *,
        registry: AgentToolRegistry,
        task_repo: AiTaskRepository,
        event_log: AgentEventLog,
        task_id: str,
        default_filters: dict[str, Any],
    ) -> None:
        self.registry = registry
        self.task_repo = task_repo
        self.event_log = event_log
        self.task_id = task_id
        self.default_filters = default_filters
        self._outcomes_by_identity: dict[str, ToolOutcome] = {}

    def prepare_params(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        definition = self.registry.get(tool_name)
        properties = definition.params_model.model_json_schema().get("properties") or {}
        merged = dict(params)
        for key, value in self.default_filters.items():
            if key in properties and key not in merged and value is not None:
                merged[key] = value
        return merged

    @staticmethod
    def identity(tool_name: str, params: dict[str, Any]) -> str:
        return f"{tool_name}:{json.dumps(params, ensure_ascii=False, sort_keys=True)}"

    def execute(
        self,
        *,
        call_id: str,
        tool_name: str,
        params: dict[str, Any],
        step_index: int,
    ) -> ToolOutcome:
        try:
            prepared = self.prepare_params(tool_name, params)
        except (ValidationError, ValueError, TypeError, KeyError) as exc:
            outcome = ToolOutcome(
                call_id=call_id,
                tool_name=tool_name,
                status="error",
                params=params,
                params_summary="",
                result_summary="工具不在只读 allowlist 或参数无效",
                source_range="",
                data={},
                error=str(exc),
            )
            self.event_log.append(
                "tool_result",
                {
                    "call_id": call_id,
                    "tool_name": tool_name,
                    "outcome": outcome.model_payload(),
                },
                step_index=step_index,
            )
            self.task_repo.add_tool_call_if_not_terminal(
                task_id=self.task_id,
                tool_name=tool_name,
                status="error",
                params_summary="",
                result_summary=outcome.result_summary,
                error=outcome.error,
            )
            return outcome
        identity = self.identity(tool_name, prepared)
        previous = self._outcomes_by_identity.get(identity)
        if previous is not None:
            duplicate = ToolOutcome(
                call_id=call_id,
                tool_name=previous.tool_name,
                status=previous.status,
                params=previous.params,
                params_summary=previous.params_summary,
                result_summary=previous.result_summary,
                source_range=previous.source_range,
                data=previous.data,
                error=previous.error,
                duplicate=True,
            )
            self.event_log.append(
                "tool_call_deduplicated",
                {"call_id": call_id, "tool_name": tool_name, "params": prepared},
                step_index=step_index,
            )
            return duplicate

        self.event_log.append(
            "tool_call",
            {"call_id": call_id, "tool_name": tool_name, "params": prepared},
            step_index=step_index,
        )
        try:
            result = self.registry.dispatch(tool_name, prepared)
            data = result.get("data") if isinstance(result.get("data"), dict) else {}
            outcome = ToolOutcome(
                call_id=call_id,
                tool_name=tool_name,
                status=_result_status(data),
                params=prepared,
                params_summary=str(result.get("params_summary") or ""),
                result_summary=str(result.get("result_summary") or ""),
                source_range=str(result.get("source_range") or ""),
                data=data,
            )
        except (ValidationError, ValueError, TypeError, KeyError) as exc:
            outcome = ToolOutcome(
                call_id=call_id,
                tool_name=tool_name,
                status="error",
                params=prepared,
                params_summary="",
                result_summary="工具参数或调用无效",
                source_range="",
                data={},
                error=str(exc),
            )
        except Exception as exc:
            outcome = ToolOutcome(
                call_id=call_id,
                tool_name=tool_name,
                status="error",
                params=prepared,
                params_summary="",
                result_summary="工具执行失败",
                source_range="",
                data={},
                error=str(exc) or exc.__class__.__name__,
            )

        self._outcomes_by_identity[identity] = outcome
        self.task_repo.add_tool_call_if_not_terminal(
            task_id=self.task_id,
            tool_name=tool_name,
            status=outcome.status,
            params_summary=outcome.params_summary,
            result_summary=outcome.result_summary,
            source_range=outcome.source_range,
            error=outcome.error,
        )
        self.event_log.append(
            "tool_result",
            {
                "call_id": call_id,
                "tool_name": tool_name,
                "outcome": outcome.model_payload(),
            },
            step_index=step_index,
        )
        return outcome
