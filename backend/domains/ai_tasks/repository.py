"""Repository for durable AI task runs, events, and read-only tool traces."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from typing import Any, Union

JsonPayload = Union[dict[str, Any], list[Any]]
TERMINAL_STATUSES = ("done", "error", "cancelled")


def _json_dump(value: JsonPayload | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _json_load(value: str | None) -> JsonPayload | None:
    if not value:
        return None
    return json.loads(value)


class AiTaskRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_run(
        self,
        *,
        task_id: str,
        task_type: str,
        status: str,
        stage: str,
        message: str = "",
        request: JsonPayload | None = None,
    ) -> None:
        self.conn.execute(
            """INSERT INTO ai_task_runs
               (task_id, task_type, status, stage, progress_pct, message, request_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (task_id, task_type, status, stage, 0.0, message, _json_dump(request)),
        )
        self.conn.commit()

    def update_run(
        self,
        *,
        task_id: str,
        status: str,
        stage: str,
        progress_pct: float,
        message: str,
        result: JsonPayload | None = None,
        error: str | None = None,
    ) -> None:
        self.conn.execute(
            """UPDATE ai_task_runs
               SET status = ?, stage = ?, progress_pct = ?, message = ?,
                   result_json = COALESCE(?, result_json),
                   error = ?,
                   updated_at = datetime('now')
               WHERE task_id = ?""",
            (
                status,
                stage,
                max(0.0, min(1.0, float(progress_pct))),
                message,
                _json_dump(result),
                error,
                task_id,
            ),
        )
        self.conn.commit()

    def update_run_if_not_terminal(
        self,
        *,
        task_id: str,
        status: str,
        stage: str,
        progress_pct: float,
        message: str,
        result: JsonPayload | None = None,
        error: str | None = None,
    ) -> bool:
        cursor = self.conn.execute(
            """UPDATE ai_task_runs
               SET status = ?, stage = ?, progress_pct = ?, message = ?,
                   result_json = COALESCE(?, result_json),
                   error = ?,
                   updated_at = datetime('now')
               WHERE task_id = ? AND status NOT IN (?, ?, ?)""",
            (
                status,
                stage,
                max(0.0, min(1.0, float(progress_pct))),
                message,
                _json_dump(result),
                error,
                task_id,
                *TERMINAL_STATUSES,
            ),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def update_run_if_not_terminal_with_write(
        self,
        *,
        task_id: str,
        status: str,
        stage: str,
        progress_pct: float,
        message: str,
        result: JsonPayload | None = None,
        error: str | None = None,
        write: Callable[[sqlite3.Connection], None] | None = None,
    ) -> bool:
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            cursor = self.conn.execute(
                """UPDATE ai_task_runs
                   SET status = ?, stage = ?, progress_pct = ?, message = ?,
                       result_json = COALESCE(?, result_json),
                       error = ?,
                       updated_at = datetime('now')
                   WHERE task_id = ? AND status NOT IN (?, ?, ?)""",
                (
                    status,
                    stage,
                    max(0.0, min(1.0, float(progress_pct))),
                    message,
                    _json_dump(result),
                    error,
                    task_id,
                    *TERMINAL_STATUSES,
                ),
            )
            if cursor.rowcount == 0:
                self.conn.rollback()
                return False
            if write is not None:
                write(self.conn)
            self.conn.commit()
            return True
        except Exception:
            self.conn.rollback()
            raise

    def add_event(
        self,
        *,
        task_id: str,
        event_type: str,
        stage: str,
        message: str = "",
        payload: JsonPayload | None = None,
    ) -> None:
        self.conn.execute(
            """INSERT INTO ai_task_events
               (task_id, event_type, stage, message, payload_json)
               VALUES (?, ?, ?, ?, ?)""",
            (task_id, event_type, stage, message, _json_dump(payload)),
        )
        self.conn.commit()

    def add_tool_call(
        self,
        *,
        task_id: str,
        tool_name: str,
        status: str,
        params_summary: str,
        result_summary: str = "",
        source_range: str = "",
        error: str | None = None,
        completed: bool = True,
    ) -> None:
        completed_at_expr = "datetime('now')" if completed else "NULL"
        self.conn.execute(
            f"""INSERT INTO ai_tool_calls
                (task_id, tool_name, status, params_summary, result_summary,
                 source_range, error, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, {completed_at_expr})""",
            (
                task_id,
                tool_name,
                status,
                params_summary,
                result_summary,
                source_range,
                error,
            ),
        )
        self.conn.commit()

    def get_run(self, task_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM ai_task_runs WHERE task_id = ?", (task_id,)
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["request"] = _json_load(result.pop("request_json", None))
        result["result"] = _json_load(result.pop("result_json", None))
        return result

    def list_events(self, task_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM ai_task_events WHERE task_id = ? ORDER BY event_id ASC",
            (task_id,),
        ).fetchall()
        events = []
        for row in rows:
            item = dict(row)
            item["payload"] = _json_load(item.pop("payload_json", None))
            events.append(item)
        return events

    def list_tool_calls(self, task_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM ai_tool_calls WHERE task_id = ? ORDER BY tool_call_id ASC",
            (task_id,),
        ).fetchall()
        return [dict(row) for row in rows]
