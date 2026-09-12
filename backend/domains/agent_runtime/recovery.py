"""Crash-recovery checkpoints derived exclusively from durable turn events."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from backend.domains.agent_runtime.projections import project_turn


@dataclass(frozen=True)
class PendingToolCall:
    call_id: str
    tool_name: str
    params: dict[str, Any]


@dataclass
class AgentResumeCheckpoint:
    resumable: bool
    reason: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    next_step: int = 1
    completed_call_ids: set[str] = field(default_factory=set)
    pending_tool_calls: list[PendingToolCall] = field(default_factory=list)
    recovered_tool_results: list[dict[str, Any]] = field(default_factory=list)


def _parse_arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def build_resume_checkpoint(events: list[dict[str, Any]]) -> AgentResumeCheckpoint:
    """Plan an idempotent resume without re-running completed read-only calls."""

    projection = project_turn(events)
    if projection.status in {"done", "cancelled", "error"}:
        return AgentResumeCheckpoint(
            resumable=False,
            reason=f"turn_{projection.status}",
            messages=projection.messages,
            next_step=projection.current_step + 1,
            completed_call_ids=projection.completed_call_ids,
        )
    if not projection.messages:
        return AgentResumeCheckpoint(resumable=False, reason="missing_context")

    calls: dict[str, PendingToolCall] = {}
    for message in projection.messages:
        if message.get("role") != "assistant":
            continue
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for item in tool_calls:
            if not isinstance(item, dict):
                continue
            function = item.get("function")
            if not isinstance(function, dict):
                continue
            call_id = str(item.get("id") or "")
            tool_name = str(function.get("name") or "")
            if call_id and tool_name:
                calls[call_id] = PendingToolCall(
                    call_id=call_id,
                    tool_name=tool_name,
                    params=_parse_arguments(function.get("arguments")),
                )

    executed_params: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("event_type") != "tool_call":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        call_id = str(payload.get("call_id") or "")
        params = payload.get("params")
        if call_id and isinstance(params, dict):
            executed_params[call_id] = params

    recovered_tool_results: list[dict[str, Any]] = []
    recovered_model_messages: list[dict[str, Any]] = []
    existing_tool_message_ids = {
        str(message.get("tool_call_id") or "")
        for message in projection.messages
        if message.get("role") == "tool"
    }
    for event in events:
        if event.get("event_type") != "tool_result":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        outcome = payload.get("outcome")
        if not isinstance(outcome, dict):
            continue
        call_id = str(payload.get("call_id") or "")
        recovered_tool_results.append(
            {
                "tool_name": str(outcome.get("tool_name") or payload.get("tool_name") or ""),
                "status": str(outcome.get("status") or "error"),
                "params": executed_params.get(call_id, {}),
                "params_summary": "由事件日志恢复",
                "result_summary": str(outcome.get("result_summary") or ""),
                "source_range": str(outcome.get("source_range") or ""),
                "data": outcome.get("data") if isinstance(outcome.get("data"), dict) else {},
                "error": outcome.get("error"),
            }
        )
        if call_id and call_id not in existing_tool_message_ids:
            recovered_model_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": str(outcome.get("tool_name") or payload.get("tool_name") or ""),
                    "content": json.dumps(outcome, ensure_ascii=False, separators=(",", ":")),
                }
            )

    pending = [
        call for call_id, call in calls.items() if call_id not in projection.completed_call_ids
    ]
    return AgentResumeCheckpoint(
        resumable=True,
        reason="incomplete_turn",
        messages=[*projection.messages, *recovered_model_messages],
        next_step=max(1, projection.current_step + 1),
        completed_call_ids=projection.completed_call_ids,
        pending_tool_calls=pending,
        recovered_tool_results=recovered_tool_results,
    )
