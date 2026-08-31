from __future__ import annotations

import time
from typing import Any

import pytest
from pydantic import BaseModel

from backend.domains.agent_runtime.context_compaction import compact_session_events
from backend.domains.agent_runtime.tool_runtime import ToolRuntime
from backend.domains.ai_agent.tool_cache import AgentToolCacheKey, AgentToolRevisionCache
from backend.domains.ai_agent.tool_registry import (
    AgentToolDefinition,
    AgentToolRegistry,
    AgentToolResult,
)

pytestmark = pytest.mark.unit


class Params(BaseModel):
    value: int = 1


class CapturingLog:
    def __init__(self) -> None:
        self.turn_id = "turn-cache"
        self.events: list[dict[str, Any]] = []

    def append(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        step_index: int | None = None,
    ) -> int:
        event_id = len(self.events) + 1
        self.events.append(
            {
                "event_id": event_id,
                "turn_id": "turn-cache",
                "event_type": event_type,
                "step_index": step_index,
                "payload": payload or {},
            }
        )
        return event_id


class CapturingRepo:
    def __init__(self) -> None:
        self.tool_calls: list[dict[str, Any]] = []

    def add_tool_call_if_not_terminal(self, **kwargs: Any) -> bool:
        self.tool_calls.append(kwargs)
        return True


def _runtime(registry: AgentToolRegistry, log: CapturingLog | None = None) -> ToolRuntime:
    return ToolRuntime(
        registry=registry,
        task_repo=CapturingRepo(),  # type: ignore[arg-type]
        event_log=log or CapturingLog(),  # type: ignore[arg-type]
        task_id="task-cache",
        default_filters={},
    )


def test_revision_cache_does_not_store_error_status_and_preserves_evidence_fields() -> None:
    cache = AgentToolRevisionCache(max_entries=2)
    key = AgentToolCacheKey(
        tool_name="analysis_stats",
        database_path="/tmp/test.db",
        database_device=1,
        database_inode=2,
        revision=(1, 2, 3),
        normalized_params='{"period":"lifetime"}',
    )
    cache.put(
        key,
        AgentToolResult(
            data={"status": "error", "message": "temporary"},
            result_summary="temporary failure",
            source_range="lifetime",
        ),
    )
    assert cache.get(key) is None

    cache.put(
        key,
        AgentToolResult(
            data={"status": "ok", "database_revision": "rev-1", "plays": 12},
            result_summary="plays=12",
            source_range="2026-01-01..2026-08-31",
        ),
    )
    cached = cache.get(key)

    assert cached is not None
    assert cached.cache_hit is True
    assert cached.source_range == "2026-01-01..2026-08-31"
    assert cached.data["database_revision"] == "rev-1"


def test_tool_runtime_retries_error_instead_of_deduplicating_it() -> None:
    calls = 0

    def flaky(_params: BaseModel) -> AgentToolResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary")
        return AgentToolResult(
            data={"found": True, "database_revision": "rev-1"},
            result_summary="recovered",
            source_range="lifetime",
        )

    registry = AgentToolRegistry()
    registry.register(
        AgentToolDefinition(
            name="analysis_stats",
            description="stats",
            read_only=True,
            params_model=Params,
            handler=flaky,
        )
    )
    runtime = _runtime(registry)

    first = runtime.execute(
        call_id="first",
        tool_name="analysis_stats",
        params={"value": 1},
        step_index=1,
    )
    second = runtime.execute(
        call_id="second",
        tool_name="analysis_stats",
        params={"value": 1},
        step_index=2,
    )

    assert first.status == "error"
    assert second.status == "ok"
    assert second.duplicate is False
    assert calls == 2


def test_parallel_writeback_is_stable_and_retains_fresh_evidence_references() -> None:
    def handler(label: str, delay: float):
        def execute(_params: BaseModel) -> AgentToolResult:
            time.sleep(delay)
            return AgentToolResult(
                data={"found": True, "database_revision": "rev-1", "label": label},
                result_summary=label,
                source_range="2026",
                cache_hit=True,
            )

        return execute

    registry = AgentToolRegistry()
    registry.register(
        AgentToolDefinition(
            name="slow_first",
            description="slow",
            read_only=True,
            params_model=Params,
            handler=handler("first", 0.02),
            supports_parallel=True,
        )
    )
    registry.register(
        AgentToolDefinition(
            name="fast_second",
            description="fast",
            read_only=True,
            params_model=Params,
            handler=handler("second", 0),
            supports_parallel=True,
        )
    )
    log = CapturingLog()
    runtime = _runtime(registry, log)

    outcomes = runtime.execute_batch(
        [
            {"call_id": "call-a", "tool_name": "slow_first", "params": {}},
            {"call_id": "call-b", "tool_name": "fast_second", "params": {}},
        ],
        step_index=1,
    )

    tool_results = [event for event in log.events if event["event_type"] == "tool_result"]
    compacted = compact_session_events(tool_results)
    assert [outcome.call_id for outcome in outcomes] == ["call-a", "call-b"]
    assert [event["payload"]["call_id"] for event in tool_results] == ["call-a", "call-b"]
    assert [fact["evidence_ref"]["call_id"] for fact in compacted["facts"]] == [
        "call-a",
        "call-b",
    ]
    assert all(outcome.cache_hit for outcome in outcomes)
