"""Append-only Agent V2 turn event log."""

from __future__ import annotations

import json
import sqlite3
from typing import Any


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

    def append(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        step_index: int | None = None,
    ) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM ai_agent_turn_events WHERE turn_id = ?",
            (self.turn_id,),
        ).fetchone()
        sequence = int(row[0])
        cursor = self.conn.execute(
            """INSERT INTO ai_agent_turn_events
               (task_id, session_id, turn_id, sequence, step_index, event_type, payload_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                self.task_id,
                self.session_id,
                self.turn_id,
                sequence,
                step_index,
                event_type,
                json.dumps(payload or {}, ensure_ascii=False),
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
    ) -> None:
        self.append(
            "model_message",
            {"origin": origin, "message": message},
            step_index=step_index,
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
        for event in self.list_events():
            if event["event_type"] != "model_message":
                continue
            message = event["payload"].get("message")
            if isinstance(message, dict):
                messages.append(message)
        return messages
