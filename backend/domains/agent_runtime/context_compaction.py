"""Deterministic long-session compaction for the local data agent."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any


def _revision_items(value: Any, *, prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).endswith("revision") and isinstance(item, (str, int)):
                result[path] = item
            elif isinstance(item, dict):
                result.update(_revision_items(item, prefix=path))
    return result


def compact_session_events(
    events: list[dict[str, Any]],
    *,
    max_facts: int = 12,
    max_recent_messages: int = 6,
    max_chars: int = 6000,
) -> dict[str, Any]:
    """Retain evidence-bearing facts without replaying an unbounded transcript.

    The result intentionally keeps source ranges, revisions and event references;
    it never stores hidden reasoning or arbitrary raw tool payloads.
    """

    facts: list[dict[str, Any]] = []
    recent_messages: list[dict[str, str]] = []
    revisions: dict[str, Any] = {}
    time_ranges: set[str] = set()
    events_by_turn: dict[str, list[int]] = defaultdict(list)

    ordered = sorted(events, key=lambda item: int(item.get("event_id") or 0))
    for event in ordered:
        turn_id = str(event.get("turn_id") or "")
        event_id = int(event.get("event_id") or 0)
        if turn_id:
            events_by_turn[turn_id].append(event_id)
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        if event.get("event_type") == "model_message":
            message = payload.get("message")
            if not isinstance(message, dict):
                continue
            role = message.get("role")
            content = message.get("content")
            if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
                recent_messages.append({"role": str(role), "content": content[:2000]})
            continue
        if event.get("event_type") != "tool_result":
            continue
        outcome = payload.get("outcome")
        if not isinstance(outcome, dict) or outcome.get("status") not in {
            "ok",
            "partial",
            "empty",
        }:
            continue
        source_range = str(outcome.get("source_range") or "")
        if source_range:
            time_ranges.add(source_range)
        data = outcome.get("data")
        revisions.update(_revision_items(data))
        summary = str(outcome.get("result_summary") or "").strip()
        if not summary and outcome.get("status") != "empty":
            continue
        facts.append(
            {
                "tool_name": str(outcome.get("tool_name") or payload.get("tool_name") or ""),
                "status": str(outcome.get("status")),
                "summary": summary[:1000],
                "source_range": source_range,
                "evidence_ref": {
                    "turn_id": turn_id,
                    "event_id": event_id,
                    "call_id": str(payload.get("call_id") or ""),
                },
            }
        )

    compacted: dict[str, Any] = {
        "version": 1,
        "facts": facts[-max_facts:],
        "time_ranges": sorted(time_ranges),
        "revisions": revisions,
        "recent_messages": recent_messages[-max_recent_messages:],
        "turn_refs": [
            {
                "turn_id": turn_id,
                "first_event_id": ids[0],
                "last_event_id": ids[-1],
            }
            for turn_id, ids in list(events_by_turn.items())[-6:]
        ],
    }
    encoded = json.dumps(compacted, ensure_ascii=False, separators=(",", ":"))
    while len(encoded) > max_chars and compacted["facts"]:
        compacted["facts"].pop(0)
        encoded = json.dumps(compacted, ensure_ascii=False, separators=(",", ":"))
    while len(encoded) > max_chars and compacted["recent_messages"]:
        compacted["recent_messages"].pop(0)
        encoded = json.dumps(compacted, ensure_ascii=False, separators=(",", ":"))
    return compacted
