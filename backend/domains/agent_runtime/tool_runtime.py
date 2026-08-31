"""Validated read-only tool execution for Agent V2."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from backend.domains.agent_runtime.event_log import AgentEventLog
from backend.domains.agent_runtime.metrics import RuntimeMetrics, json_size_bytes
from backend.domains.agent_runtime.observation import compact_observation
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
    elapsed_ms: int = 0
    result_size_bytes: int = 0
    cache_hit: bool = False

    def model_payload(self) -> dict[str, Any]:
        return compact_value(
            {
                "status": self.status,
                "tool_name": self.tool_name,
                "result_summary": self.result_summary,
                "source_range": self.source_range,
                "data": compact_observation(self.data),
                "error": self.error,
                "duplicate": self.duplicate,
                "elapsed_ms": self.elapsed_ms,
                "result_size_bytes": self.result_size_bytes,
                "cache_hit": self.cache_hit,
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
        metrics: RuntimeMetrics | None = None,
        clock: Callable[[], float] = time.monotonic,
        allowed_tool_names: set[str] | None = None,
    ) -> None:
        self.registry = registry
        self.task_repo = task_repo
        self.event_log = event_log
        self.task_id = task_id
        self.default_filters = default_filters
        self.metrics = metrics
        self.clock = clock
        self.allowed_tool_names = allowed_tool_names
        self._outcomes_by_identity: dict[str, ToolOutcome] = {}

    def seed_outcomes(self, outcomes: list[dict[str, Any]]) -> None:
        """Seed durable completed calls so recovery never executes them twice."""

        for item in outcomes:
            tool_name = str(item.get("tool_name") or "")
            params = item.get("params")
            data = item.get("data")
            if not tool_name or not isinstance(params, dict) or not isinstance(data, dict):
                continue
            outcome = ToolOutcome(
                call_id="recovered",
                tool_name=tool_name,
                status=str(item.get("status") or "error"),
                params=params,
                params_summary=str(item.get("params_summary") or "由事件日志恢复"),
                result_summary=str(item.get("result_summary") or ""),
                source_range=str(item.get("source_range") or ""),
                data=data,
                error=str(item["error"]) if item.get("error") else None,
                result_size_bytes=json_size_bytes(data),
            )
            self._outcomes_by_identity[self.identity(tool_name, params)] = outcome

    def prepare_params(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.allowed_tool_names is not None and tool_name not in self.allowed_tool_names:
            raise ValueError(f"Tool is outside the selected Agent profile: {tool_name}")
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
        started_at = self.clock()
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
                elapsed_ms=round((self.clock() - started_at) * 1000),
            )
            if self.metrics is not None:
                self.metrics.record_tool(
                    elapsed_ms=outcome.elapsed_ms,
                    result_bytes=0,
                )
            self.event_log.append(
                "tool_result",
                {
                    "call_id": call_id,
                    "tool_name": tool_name,
                    "params": params,
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
                elapsed_ms=0,
                result_size_bytes=previous.result_size_bytes,
                cache_hit=True,
            )
            if self.metrics is not None:
                self.metrics.record_tool(
                    elapsed_ms=0,
                    result_bytes=0,
                    cache_hit=True,
                    executed=False,
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
                elapsed_ms=round((self.clock() - started_at) * 1000),
                result_size_bytes=json_size_bytes(data),
                cache_hit=result.get("cache_hit") is True,
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
                elapsed_ms=round((self.clock() - started_at) * 1000),
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
                elapsed_ms=round((self.clock() - started_at) * 1000),
            )

        self._outcomes_by_identity[identity] = outcome
        if self.metrics is not None:
            self.metrics.record_tool(
                elapsed_ms=outcome.elapsed_ms,
                result_bytes=outcome.result_size_bytes,
                cache_hit=outcome.cache_hit,
            )
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
                "params": prepared,
                "outcome": outcome.model_payload(),
            },
            step_index=step_index,
        )
        return outcome

    def _dispatch_prepared(
        self,
        *,
        call_id: str,
        tool_name: str,
        prepared: dict[str, Any],
    ) -> ToolOutcome:
        started_at = self.clock()
        try:
            result = self.registry.dispatch(tool_name, prepared)
            data = result.get("data") if isinstance(result.get("data"), dict) else {}
            return ToolOutcome(
                call_id=call_id,
                tool_name=tool_name,
                status=_result_status(data),
                params=prepared,
                params_summary=str(result.get("params_summary") or ""),
                result_summary=str(result.get("result_summary") or ""),
                source_range=str(result.get("source_range") or ""),
                data=data,
                elapsed_ms=round((self.clock() - started_at) * 1000),
                result_size_bytes=json_size_bytes(data),
                cache_hit=result.get("cache_hit") is True,
            )
        except (ValidationError, ValueError, TypeError, KeyError) as exc:
            summary = "工具参数或调用无效"
            error = str(exc)
        except Exception as exc:
            summary = "工具执行失败"
            error = str(exc) or exc.__class__.__name__
        return ToolOutcome(
            call_id=call_id,
            tool_name=tool_name,
            status="error",
            params=prepared,
            params_summary="",
            result_summary=summary,
            source_range="",
            data={},
            error=error,
            elapsed_ms=round((self.clock() - started_at) * 1000),
        )

    def _persist_parallel_outcome(self, outcome: ToolOutcome, *, step_index: int) -> None:
        identity = self.identity(outcome.tool_name, outcome.params)
        self._outcomes_by_identity[identity] = outcome
        if self.metrics is not None:
            self.metrics.record_tool(
                elapsed_ms=outcome.elapsed_ms,
                result_bytes=outcome.result_size_bytes,
                cache_hit=outcome.cache_hit,
            )
        self.task_repo.add_tool_call_if_not_terminal(
            task_id=self.task_id,
            tool_name=outcome.tool_name,
            status=outcome.status,
            params_summary=outcome.params_summary,
            result_summary=outcome.result_summary,
            source_range=outcome.source_range,
            error=outcome.error,
        )
        self.event_log.append(
            "tool_result",
            {
                "call_id": outcome.call_id,
                "tool_name": outcome.tool_name,
                "params": outcome.params,
                "outcome": outcome.model_payload(),
                "parallel": True,
            },
            step_index=step_index,
        )

    def execute_batch(
        self,
        calls: list[dict[str, Any]],
        *,
        step_index: int,
        max_parallel: int = 2,
    ) -> list[ToolOutcome]:
        """Run independent read-only calls two at a time with stable writeback."""

        if len(calls) < 2 or max_parallel < 2:
            return [
                self.execute(
                    call_id=str(item["call_id"]),
                    tool_name=str(item["tool_name"]),
                    params=item.get("params") or {},
                    step_index=step_index,
                )
                for item in calls
            ]
        prepared_calls: list[dict[str, Any]] = []
        identities: set[str] = set()
        try:
            for item in calls:
                tool_name = str(item["tool_name"])
                definition = self.registry.get(tool_name)
                if not definition.read_only or not definition.supports_parallel:
                    raise ValueError("tool does not support parallel execution")
                prepared = self.prepare_params(tool_name, item.get("params") or {})
                identity = self.identity(tool_name, prepared)
                if identity in identities or identity in self._outcomes_by_identity:
                    raise ValueError("duplicate calls require sequential deduplication")
                identities.add(identity)
                prepared_calls.append(
                    {
                        "call_id": str(item["call_id"]),
                        "tool_name": tool_name,
                        "params": prepared,
                    }
                )
        except (ValidationError, ValueError, TypeError, KeyError):
            return [
                self.execute(
                    call_id=str(item["call_id"]),
                    tool_name=str(item["tool_name"]),
                    params=item.get("params") or {},
                    step_index=step_index,
                )
                for item in calls
            ]

        outcomes: list[ToolOutcome] = []
        self.event_log.append(
            "parallel_tool_batch_started",
            {"call_count": len(prepared_calls), "max_parallel": 2},
            step_index=step_index,
        )
        for offset in range(0, len(prepared_calls), 2):
            chunk = prepared_calls[offset : offset + 2]
            for item in chunk:
                self.event_log.append(
                    "tool_call",
                    {**item, "parallel": True},
                    step_index=step_index,
                )
            with ThreadPoolExecutor(max_workers=min(2, len(chunk))) as executor:
                futures = [
                    executor.submit(
                        self._dispatch_prepared,
                        call_id=item["call_id"],
                        tool_name=item["tool_name"],
                        prepared=item["params"],
                    )
                    for item in chunk
                ]
                chunk_outcomes = [future.result() for future in futures]
            for outcome in chunk_outcomes:
                self._persist_parallel_outcome(outcome, step_index=step_index)
                outcomes.append(outcome)
        self.event_log.append(
            "parallel_tool_batch_ended",
            {"call_count": len(outcomes)},
            step_index=step_index,
        )
        return outcomes
