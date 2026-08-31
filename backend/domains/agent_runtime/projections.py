"""Deterministic projections derived from the append-only Agent event log."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal

ContextSource = Literal["memory", "event_log"]


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def projection_hash(value: Any) -> str:
    """Return a stable, content-only digest suitable for shadow comparison."""

    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _integer(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


@dataclass
class AgentTurnProjection:
    """Replayable state used by context recovery and observability endpoints."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    transcript: list[dict[str, Any]] = field(default_factory=list)
    status: str = "new"
    stop_reason: str | None = None
    current_step: int = 0
    model_call_count: int = 0
    tool_call_count: int = 0
    completed_call_ids: set[str] = field(default_factory=set)
    usage: dict[str, int] = field(
        default_factory=lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "messages": self.messages,
            "transcript": self.transcript,
            "turn_state": {
                "status": self.status,
                "stop_reason": self.stop_reason,
                "current_step": self.current_step,
                "model_call_count": self.model_call_count,
                "tool_call_count": self.tool_call_count,
                "completed_call_ids": sorted(self.completed_call_ids),
            },
            "usage": self.usage,
        }


def _append_transcript(
    transcript: list[dict[str, Any]],
    message: dict[str, Any],
) -> None:
    role = message.get("role")
    if role not in {"user", "assistant", "tool"}:
        return
    item: dict[str, Any] = {"role": role}
    if isinstance(message.get("content"), str):
        item["content"] = message["content"]
    if role == "tool":
        item["tool_call_id"] = message.get("tool_call_id")
        item["name"] = message.get("name")
    transcript.append(item)


def project_turn(events: list[dict[str, Any]]) -> AgentTurnProjection:
    """Fold persisted events into model messages, transcript, state and usage."""

    projection = AgentTurnProjection()
    ordered = sorted(events, key=lambda item: int(item.get("sequence") or 0))
    for event in ordered:
        event_type = str(event.get("event_type") or "")
        payload = event.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        step_index = _integer(event.get("step_index"))
        projection.current_step = max(projection.current_step, step_index)

        if event_type == "turn_started":
            projection.status = "running"
        elif event_type == "step_started":
            projection.status = "running"
        elif event_type == "model_request":
            projection.model_call_count += 1
        elif event_type == "model_message":
            message = payload.get("message")
            if isinstance(message, dict):
                projection.messages.append(message)
                _append_transcript(projection.transcript, message)
        elif event_type == "assistant_message":
            usage = payload.get("usage")
            if isinstance(usage, dict):
                input_tokens = _integer(usage.get("input_tokens", usage.get("prompt_tokens")))
                output_tokens = _integer(usage.get("output_tokens", usage.get("completion_tokens")))
                total_tokens = _integer(usage.get("total_tokens"))
                projection.usage["input_tokens"] += input_tokens
                projection.usage["output_tokens"] += output_tokens
                projection.usage["total_tokens"] += total_tokens or (input_tokens + output_tokens)
        elif event_type == "tool_call":
            projection.tool_call_count += 1
        elif event_type == "tool_result":
            call_id = payload.get("call_id")
            if isinstance(call_id, str) and call_id:
                projection.completed_call_ids.add(call_id)
        elif event_type == "turn_ended":
            projection.status = "done"
            stop_reason = payload.get("stop_reason")
            projection.stop_reason = str(stop_reason) if stop_reason else "completed"
        elif event_type == "run_cancelled":
            projection.status = "cancelled"
            projection.stop_reason = "cancelled"
        elif event_type == "run_failed":
            projection.status = "error"
            projection.stop_reason = "error"
    return projection


def select_context_messages(
    *,
    memory_messages: list[dict[str, Any]],
    events: list[dict[str, Any]],
    source: ContextSource,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select runtime context and always emit a non-sensitive shadow verdict."""

    replayed = project_turn(events).messages
    memory_digest = projection_hash(memory_messages)
    event_digest = projection_hash(replayed)
    selected = replayed if source == "event_log" else memory_messages
    return selected, {
        "source": source,
        "matches": memory_digest == event_digest,
        "memory_hash": memory_digest,
        "event_log_hash": event_digest,
        "memory_message_count": len(memory_messages),
        "event_log_message_count": len(replayed),
    }
