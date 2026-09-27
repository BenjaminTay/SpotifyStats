"""Repository for durable AI task runs, events, and read-only tool traces."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from typing import Any, Union

from backend.domains.ai_tasks.execution_context import current_execution_identity

JsonPayload = Union[dict[str, Any], list[Any]]
TERMINAL_STATUSES = ("done", "error", "cancelled")
TASK_LEASE_SECONDS = 90


def _json_dump(value: JsonPayload | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _json_load(value: str | None) -> JsonPayload | None:
    if not value:
        return None
    return json.loads(value)


def report_request_identity(request: dict[str, Any]) -> str:
    """Canonical identity for one report-generation contract.

    ``force`` controls whether a new run is requested; it is not part of the
    report's data identity. Defaults are materialized so an older omitted
    default still matches the equivalent explicit current request.
    """

    normalized = {
        "report_type": request.get("report_type"),
        "action": "generate",
        "report_mode": request.get("report_mode"),
        "writer_pipeline": request.get("writer_pipeline"),
        "week_start": request.get("week_start"),
        "week_end": request.get("week_end"),
        "month": request.get("month"),
        "year": request.get("year"),
        "min_ms": request.get("min_ms", 30000),
        "music_only": request.get("music_only", True),
        "merge_enabled": request.get("merge_enabled", True),
        "dynamic_threshold": request.get("dynamic_threshold", True),
        "max_merge_gap_minutes": request.get("max_merge_gap_minutes"),
    }
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class AiTaskRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        try:
            columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(ai_task_runs)")}
        except sqlite3.Error:
            columns = set()
        self._supports_leases = {
            "lease_owner",
            "lease_expires_at",
            "attempt_count",
        }.issubset(columns)
        self._supports_v6 = {
            "runtime_version",
            "workflow_version",
            "event_schema_version",
            "generation",
            "lease_generation",
        }.issubset(columns)
        self._supports_state_version = "state_version" in columns
        self._claimed_generation: int | None = None

    @property
    def supports_worker_leases(self) -> bool:
        return self._supports_leases

    @property
    def supports_v6(self) -> bool:
        return self._supports_v6

    @property
    def claimed_lease_generation(self) -> int | None:
        return self._claimed_generation

    def _lease_guard(self, *, alias: str = "") -> tuple[str, tuple[Any, ...]]:
        identity = current_execution_identity()
        prefix = f"{alias}." if alias else ""
        if identity is None or identity.task_id == "" or not self._supports_v6:
            return "", ()
        return (
            f" AND {prefix}task_id = ? AND {prefix}lease_owner = ? "
            f"AND {prefix}lease_generation = ?",
            (identity.task_id, identity.lease_owner, identity.lease_generation),
        )

    def _lease_refresh_sql(self) -> str:
        if not self._supports_leases:
            return ""
        return (
            "lease_expires_at = CASE WHEN lease_owner IS NOT NULL "
            f"THEN datetime('now', '+{TASK_LEASE_SECONDS} seconds') ELSE NULL END,"
        )

    def _state_version_sql(self) -> str:
        return "state_version = state_version + 1," if self._supports_state_version else ""

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
        if self._supports_v6:
            from backend.core.config import AI_AGENT_EXECUTION_PATH

            runtime_version = AI_AGENT_EXECUTION_PATH if task_type.startswith("ai_") else "v5"
            workflow_version = (
                "yearly_v6"
                if task_type == "ai_report_yearly" and runtime_version == "v6"
                else runtime_version
            )
            self.conn.execute(
                """INSERT INTO ai_task_runs
                   (task_id, task_type, status, stage, progress_pct, message, request_json,
                    runtime_version, workflow_version, event_schema_version, generation)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 2, 1)""",
                (
                    task_id,
                    task_type,
                    status,
                    stage,
                    0.0,
                    message,
                    _json_dump(request),
                    runtime_version,
                    workflow_version,
                ),
            )
        else:
            self.conn.execute(
                """INSERT INTO ai_task_runs
                   (task_id, task_type, status, stage, progress_pct, message, request_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (task_id, task_type, status, stage, 0.0, message, _json_dump(request)),
            )
        self.conn.commit()

    def claim_run(
        self,
        task_id: str,
        *,
        lease_owner: str,
        lease_seconds: int = TASK_LEASE_SECONDS,
    ) -> bool:
        if not self._supports_leases:
            row = self.conn.execute(
                "SELECT status FROM ai_task_runs WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            return bool(row and str(row[0]) not in TERMINAL_STATUSES)
        modifier = f"+{max(30, int(lease_seconds))} seconds"
        generation_sql = ", lease_generation = lease_generation + 1" if self._supports_v6 else ""
        cursor = self.conn.execute(
            f"""UPDATE ai_task_runs
               SET lease_owner = ?, lease_expires_at = datetime('now', ?),
                   attempt_count = attempt_count + 1{generation_sql}, updated_at = datetime('now')
               WHERE task_id = ?
                 AND status NOT IN (?, ?, ?)
                 AND (
                     lease_owner IS NULL OR lease_owner = ?
                     OR lease_expires_at IS NULL OR lease_expires_at <= datetime('now')
                 )""",
            (lease_owner, modifier, task_id, *TERMINAL_STATUSES, lease_owner),
        )
        self.conn.commit()
        if cursor.rowcount > 0 and self._supports_v6:
            row = self.conn.execute(
                "SELECT lease_generation FROM ai_task_runs WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            self._claimed_generation = int(row[0]) if row else None
        return cursor.rowcount > 0

    def renew_run(
        self,
        task_id: str,
        *,
        lease_owner: str,
        lease_seconds: int = TASK_LEASE_SECONDS,
    ) -> bool:
        """Extend an active worker lease without changing the attempt counter."""

        if not self._supports_leases:
            return True
        modifier = f"+{max(30, int(lease_seconds))} seconds"
        cursor = self.conn.execute(
            """UPDATE ai_task_runs
               SET lease_expires_at = datetime('now', ?),
                   updated_at = datetime('now')
               WHERE task_id = ? AND lease_owner = ?
                 AND status NOT IN (?, ?, ?)""",
            (modifier, task_id, lease_owner, *TERMINAL_STATUSES),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def release_run(self, task_id: str, *, lease_owner: str) -> bool:
        if not self._supports_leases:
            return True
        cursor = self.conn.execute(
            """UPDATE ai_task_runs
               SET lease_owner = NULL, lease_expires_at = NULL,
                   updated_at = datetime('now')
               WHERE task_id = ? AND lease_owner = ?""",
            (task_id, lease_owner),
        )
        self.conn.commit()
        return cursor.rowcount > 0

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
        guard_sql, guard_params = self._lease_guard()
        self.conn.execute(
            f"""UPDATE ai_task_runs
               SET status = ?, stage = ?, progress_pct = ?, message = ?,
                   result_json = COALESCE(?, result_json),
                   error = ?,
                   {self._state_version_sql()}
                   {self._lease_refresh_sql()}
                   updated_at = datetime('now')
               WHERE task_id = ?{guard_sql}""",
            (
                status,
                stage,
                max(0.0, min(1.0, float(progress_pct))),
                message,
                _json_dump(result),
                error,
                task_id,
                *guard_params,
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
        guard_sql, guard_params = self._lease_guard()
        cursor = self.conn.execute(
            f"""UPDATE ai_task_runs
               SET status = ?, stage = ?, progress_pct = ?, message = ?,
                   result_json = COALESCE(?, result_json),
                   error = ?,
                   {self._state_version_sql()}
                   {self._lease_refresh_sql()}
                   updated_at = datetime('now')
               WHERE task_id = ? AND status NOT IN (?, ?, ?){guard_sql}""",
            (
                status,
                stage,
                max(0.0, min(1.0, float(progress_pct))),
                message,
                _json_dump(result),
                error,
                task_id,
                *TERMINAL_STATUSES,
                *guard_params,
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
            guard_sql, guard_params = self._lease_guard()
            cursor = self.conn.execute(
                f"""UPDATE ai_task_runs
                   SET status = ?, stage = ?, progress_pct = ?, message = ?,
                       result_json = COALESCE(?, result_json),
                       error = ?,
                       {self._state_version_sql()}
                       {self._lease_refresh_sql()}
                       updated_at = datetime('now')
                   WHERE task_id = ? AND status NOT IN (?, ?, ?){guard_sql}""",
                (
                    status,
                    stage,
                    max(0.0, min(1.0, float(progress_pct))),
                    message,
                    _json_dump(result),
                    error,
                    task_id,
                    *TERMINAL_STATUSES,
                    *guard_params,
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
        guard_sql, guard_params = self._lease_guard(alias="r")
        self.conn.execute(
            f"""INSERT INTO ai_task_events
               (task_id, event_type, stage, message, payload_json)
               SELECT ?, ?, ?, ?, ?
               WHERE EXISTS (SELECT 1 FROM ai_task_runs r WHERE r.task_id = ?{guard_sql})""",
            (
                task_id,
                event_type,
                stage,
                message,
                _json_dump(payload),
                task_id,
                *guard_params,
            ),
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

    def add_tool_call_if_not_terminal(
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
    ) -> bool:
        completed_at_expr = "datetime('now')" if completed else "NULL"
        cursor = self.conn.execute(
            f"""INSERT INTO ai_tool_calls
                (task_id, tool_name, status, params_summary, result_summary,
                 source_range, error, completed_at)
                SELECT ?, ?, ?, ?, ?, ?, ?, {completed_at_expr}
                WHERE EXISTS (
                    SELECT 1 FROM ai_task_runs
                    WHERE task_id = ? AND status NOT IN (?, ?, ?)
                )""",
            (
                task_id,
                tool_name,
                status,
                params_summary,
                result_summary,
                source_range,
                error,
                task_id,
                *TERMINAL_STATUSES,
            ),
        )
        self.conn.commit()
        return cursor.rowcount > 0

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

    def find_latest_report_run(
        self,
        *,
        task_type: str,
        request: dict[str, Any],
    ) -> dict[str, Any] | None:
        identity = report_request_identity(request)
        rows = self.conn.execute(
            """SELECT * FROM ai_task_runs
               WHERE task_type = ?
               ORDER BY created_at DESC, rowid DESC
               LIMIT 200""",
            (task_type,),
        ).fetchall()
        for row in rows:
            item = dict(row)
            stored_request = _json_load(item.get("request_json"))
            if not isinstance(stored_request, dict):
                continue
            if stored_request.get("action") != "generate":
                continue
            if report_request_identity(stored_request) != identity:
                continue
            item["request"] = stored_request
            item.pop("request_json", None)
            item["result"] = _json_load(item.pop("result_json", None))
            return item
        return None

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

    def list_agent_turn_events(self, task_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT event_id, task_id, session_id, turn_id, sequence,
                      step_index, event_type, payload_json, created_at
               FROM ai_agent_turn_events
               WHERE task_id = ? ORDER BY event_id ASC""",
            (task_id,),
        ).fetchall()
        events = []
        for row in rows:
            item = dict(row)
            item["payload"] = _json_load(item.pop("payload_json", None)) or {}
            events.append(item)
        return events

    def list_agent_session_events(
        self,
        session_id: int,
        *,
        exclude_task_id: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [session_id]
        predicate = "session_id = ?"
        if exclude_task_id:
            predicate += " AND task_id <> ?"
            params.append(exclude_task_id)
        params.append(max(1, min(limit, 2000)))
        rows = self.conn.execute(
            f"""SELECT event_id, task_id, session_id, turn_id, sequence,
                       step_index, event_type, payload_json, created_at
                FROM ai_agent_turn_events
                WHERE {predicate}
                ORDER BY event_id DESC LIMIT ?""",
            params,
        ).fetchall()
        events = []
        for row in reversed(rows):
            item = dict(row)
            item["payload"] = _json_load(item.pop("payload_json", None)) or {}
            events.append(item)
        return events

    def enqueue_agent_input(
        self,
        *,
        task_id: str,
        session_id: int | None,
        input_type: str,
        content: str,
    ) -> int:
        cursor = self.conn.execute(
            """INSERT INTO ai_agent_session_inbox
               (task_id, session_id, input_type, content)
               VALUES (?, ?, ?, ?)""",
            (task_id, session_id, input_type, content),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def consume_agent_inputs(self, task_id: str, *, limit: int = 8) -> list[dict[str, Any]]:
        """Atomically claim pending steering messages in insertion order."""

        self.conn.execute("BEGIN IMMEDIATE")
        try:
            rows = self.conn.execute(
                """SELECT inbox_id, task_id, session_id, input_type, content, created_at
                   FROM ai_agent_session_inbox
                   WHERE task_id = ? AND status = 'pending'
                   ORDER BY inbox_id ASC LIMIT ?""",
                (task_id, max(1, min(limit, 20))),
            ).fetchall()
            ids = [int(row["inbox_id"]) for row in rows]
            if ids:
                placeholders = ",".join("?" for _ in ids)
                self.conn.execute(
                    f"""UPDATE ai_agent_session_inbox
                        SET status = 'consumed', consumed_at = datetime('now')
                        WHERE inbox_id IN ({placeholders}) AND status = 'pending'""",
                    ids,
                )
            self.conn.commit()
            return [dict(row) for row in rows]
        except Exception:
            self.conn.rollback()
            raise

    def list_recoverable_agent_runs(self) -> list[dict[str, Any]]:
        lease_predicate = (
            """AND (lease_owner IS NULL OR lease_expires_at IS NULL
                     OR lease_expires_at <= datetime('now'))"""
            if self._supports_leases
            else ""
        )
        rows = self.conn.execute(
            f"""SELECT * FROM ai_task_runs
               WHERE task_type IN ('ai_chat_agent', 'ai_report_yearly')
                 AND status IN ('queued', 'running', 'cancelling')
                 {lease_predicate}
               ORDER BY created_at ASC"""
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["request"] = _json_load(item.pop("request_json", None))
            item["result"] = _json_load(item.pop("result_json", None))
            result.append(item)
        return result
