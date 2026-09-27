"""Append-only Agent V2 turn event log."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "access_token",
    "refresh_token",
    "secret",
}
_BEARER_PATTERN = re.compile(r"(?i)bearer\s+[a-z0-9._~+/-]+")
_API_KEY_PATTERN = re.compile(r"(?i)\b(?:sk|ds|key)-[a-z0-9_-]{12,}\b")


def _sanitize_payload(value: Any, *, key: str = "") -> Any:
    """Redact credentials while preserving replayable local evidence."""

    if key.casefold() in _SENSITIVE_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(item_key): _sanitize_payload(item, key=str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_payload(item) for item in value]
    if isinstance(value, str):
        return _API_KEY_PATTERN.sub("[REDACTED]", _BEARER_PATTERN.sub("Bearer [REDACTED]", value))
    return value


class AgentEventLog:
    """Persist every state transition and every model-visible message."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        task_id: str,
        turn_id: str,
        session_id: int | None,
    ) -> None:
        self.conn = conn
        self.task_id = task_id
        self.turn_id = turn_id
        self.session_id = session_id
        has_v6_table = (
            self.conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_runtime_events'"
            ).fetchone()
            is not None
        )
        runtime_row = (
            self.conn.execute(
                "SELECT runtime_version FROM ai_task_runs WHERE task_id = ?",
                (self.task_id,),
            ).fetchone()
            if has_v6_table
            else None
        )
        self._supports_v6 = bool(runtime_row and str(runtime_row[0]) == "v6")

    def append(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        step_index: int | None = None,
        call_id: str | None = None,
        response_commit_payload: dict[str, Any] | None = None,
    ) -> int:
        sanitized = _sanitize_payload(payload or {})
        if self._supports_v6:
            from backend.domains.agent_runtime.runtime_store import RuntimeStore

            return RuntimeStore(self.conn, self.task_id).commit_turn_event(
                turn_id=self.turn_id,
                session_id=self.session_id,
                event_type=event_type,
                payload=sanitized,
                step_index=step_index,
                step_id=(
                    f"turn:{self.turn_id}:step:{step_index}"
                    if step_index is not None
                    else f"turn:{self.turn_id}"
                ),
                call_id=call_id
                or (
                    str(
                        (payload or {}).get("model_call_id") or (payload or {}).get("call_id") or ""
                    )
                    or None
                ),
                response_commit_payload=response_commit_payload,
            )
        cursor = self.conn.execute(
            """INSERT INTO ai_agent_turn_events
               (task_id, session_id, turn_id, sequence, step_index, event_type, payload_json)
               SELECT ?, ?, ?, COALESCE(MAX(sequence), 0) + 1, ?, ?, ?
               FROM ai_agent_turn_events WHERE turn_id = ?""",
            (
                self.task_id,
                self.session_id,
                self.turn_id,
                step_index,
                event_type,
                json.dumps(sanitized, ensure_ascii=False),
                self.turn_id,
            ),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def append_model_message(
        self,
        message: dict[str, Any],
        *,
        step_index: int | None = None,
        origin: str,
        call_id: str | None = None,
        usage: dict[str, Any] | None = None,
        attempt_count: int = 1,
        elapsed_ms: int = 0,
        dispatch_id: str | None = None,
    ) -> None:
        sanitized_message = _sanitize_payload(message)
        self.append(
            "model_message",
            {"origin": origin, "message": sanitized_message},
            step_index=step_index,
            call_id=call_id,
            response_commit_payload=(
                {
                    "origin": origin,
                    "message": sanitized_message,
                    "usage": _sanitize_payload(usage) if usage else None,
                    "attempt_count": max(1, int(attempt_count)),
                    "elapsed_ms": max(0, int(elapsed_ms)),
                    "dispatch_id": dispatch_id,
                }
                if self._supports_v6 and origin == "model_response" and call_id
                else None
            ),
        )

    def list_events(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT event_id, task_id, session_id, turn_id, sequence,
                      step_index, event_type, payload_json, created_at
               FROM ai_agent_turn_events
               WHERE turn_id = ? ORDER BY sequence ASC""",
            (self.turn_id,),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json") or "{}")
            result.append(item)
        return result

    def reconstruct_messages(self) -> list[dict[str, Any]]:
        messages = []
        events = self.list_events()
        if self._supports_v6:
            from backend.domains.agent_runtime.runtime_store import RuntimeStore

            events = RuntimeStore(self.conn, self.task_id).list_events()
        for event in events:
            if event["event_type"] != "model_message":
                continue
            message = event["payload"].get("message")
            if isinstance(message, dict):
                messages.append(message)
        return messages
