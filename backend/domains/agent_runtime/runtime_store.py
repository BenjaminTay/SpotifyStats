"""Transactional V6 runtime facts and report checkpoint projections."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from typing import Any

from backend.domains.ai_tasks.execution_context import current_execution_identity

EVENT_SCHEMA_VERSION = 2
RUNTIME_VERSION = "v6"


class LostTaskLeaseError(RuntimeError):
    """Raised when a superseded worker tries to commit business output."""


class IncompatibleReportContextError(RuntimeError):
    """Raised when a task cannot safely resume its frozen report generation."""


class PersistentBudgetExceededError(RuntimeError):
    """Raised when a resumed task has already consumed its durable allowance."""


class IncompatibleModelRequestError(RuntimeError):
    """Raised when an immutable request cannot be replayed by this runtime."""


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _load(value: str | None) -> Any:
    if not value:
        return {}
    return json.loads(value)


def _usage_value(usage: dict[str, Any] | None, *keys: str) -> int:
    if usage is None:
        return 0
    for key in keys:
        value = usage.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return max(0, int(value))
    return 0


@dataclass(frozen=True)
class RuntimeTaskIdentity:
    task_id: str
    generation: int
    runtime_version: str
    workflow_version: str


@dataclass(frozen=True)
class PreparedModelRequest:
    """The authoritative request descriptor for one logical model call."""

    call_id: str
    step_id: str
    descriptor: dict[str, Any]
    uncertain_replay: bool


class RuntimeStore:
    """Own the transaction boundary for durable model-visible facts."""

    def __init__(self, conn: sqlite3.Connection, task_id: str) -> None:
        self.conn = conn
        self.task_id = task_id

    def identity(self) -> RuntimeTaskIdentity:
        row = self.conn.execute(
            """SELECT task_id, generation, runtime_version, workflow_version
               FROM ai_task_runs WHERE task_id = ?""",
            (self.task_id,),
        ).fetchone()
        if row is None:
            raise KeyError(self.task_id)
        return RuntimeTaskIdentity(
            task_id=str(row[0]),
            generation=int(row[1]),
            runtime_version=str(row[2]),
            workflow_version=str(row[3]),
        )

    def _assert_lease(self) -> None:
        active = current_execution_identity()
        if active is not None and active.task_id == self.task_id:
            row = self.conn.execute(
                """SELECT 1 FROM ai_task_runs
                   WHERE task_id = ? AND lease_owner = ? AND lease_generation = ?
                     AND status IN ('queued', 'running')""",
                (active.task_id, active.lease_owner, active.lease_generation),
            ).fetchone()
        else:
            row = self.conn.execute(
                """SELECT 1 FROM ai_task_runs
                   WHERE task_id = ? AND status IN ('queued', 'running')""",
                (self.task_id,),
            ).fetchone()
        if row is None:
            raise LostTaskLeaseError(f"task lease lost: {self.task_id}")

    def _append_in_transaction(
        self,
        *,
        generation: int,
        event_type: str,
        payload: dict[str, Any],
        step_id: str | None = None,
        call_id: str | None = None,
    ) -> int:
        self._assert_lease()
        row = self.conn.execute(
            """SELECT COALESCE(MAX(sequence), 0) + 1
               FROM ai_runtime_events WHERE task_id = ? AND generation = ?""",
            (self.task_id, generation),
        ).fetchone()
        sequence = int(row[0])
        cursor = self.conn.execute(
            """INSERT INTO ai_runtime_events
               (task_id, generation, sequence, schema_version, event_type,
                step_id, call_id, payload_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                self.task_id,
                generation,
                sequence,
                EVENT_SCHEMA_VERSION,
                event_type,
                step_id,
                call_id,
                _dump(payload),
            ),
        )
        return int(cursor.lastrowid)

    def append(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        step_id: str | None = None,
        call_id: str | None = None,
    ) -> int:
        identity = self.identity()
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            event_id = self._append_in_transaction(
                generation=identity.generation,
                event_type=event_type,
                payload=payload,
                step_id=step_id,
                call_id=call_id,
            )
            self.conn.commit()
            return event_id
        except Exception:
            self.conn.rollback()
            raise

    def commit_turn_event(
        self,
        *,
        turn_id: str,
        session_id: int | None,
        event_type: str,
        payload: dict[str, Any],
        step_index: int | None,
        step_id: str | None,
        call_id: str | None,
        response_commit_payload: dict[str, Any] | None = None,
    ) -> int:
        """Atomically commit the authoritative event and its V5 projection.

        ``ai_runtime_events`` is authoritative for V6 replay.  The legacy turn
        row remains a compatibility projection, but it is never committed on
        its own.  A model response acknowledgement shares this transaction so
        recovery cannot observe a response without its replayable message (or
        the reverse).
        """

        identity = self.identity()
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self._assert_lease()
            cursor = self.conn.execute(
                """INSERT INTO ai_agent_turn_events
                   (task_id, session_id, turn_id, sequence, step_index,
                    event_type, payload_json)
                   SELECT ?, ?, ?, COALESCE(MAX(sequence), 0) + 1, ?, ?, ?
                   FROM ai_agent_turn_events WHERE turn_id = ?""",
                (
                    self.task_id,
                    session_id,
                    turn_id,
                    step_index,
                    event_type,
                    _dump(payload),
                    turn_id,
                ),
            )
            self._append_in_transaction(
                generation=identity.generation,
                event_type=event_type,
                payload=payload,
                step_id=step_id,
                call_id=call_id,
            )
            if response_commit_payload is not None:
                self._append_in_transaction(
                    generation=identity.generation,
                    event_type="model_response_committed",
                    payload=response_commit_payload,
                    step_id=step_id,
                    call_id=call_id,
                )
                usage = (
                    response_commit_payload.get("usage")
                    if isinstance(response_commit_payload.get("usage"), dict)
                    else None
                )
                self._finalize_model_dispatch_in_transaction(
                    generation=identity.generation,
                    call_id=str(call_id or ""),
                    dispatch_id=str(response_commit_payload.get("dispatch_id") or ""),
                    usage=usage,
                    elapsed_ms=int(response_commit_payload.get("elapsed_ms") or 0),
                )
            self.conn.commit()
            return int(cursor.lastrowid)
        except Exception:
            self.conn.rollback()
            raise

    def list_events(self, *, generation: int | None = None) -> list[dict[str, Any]]:
        selected_generation = generation or self.identity().generation
        rows = self.conn.execute(
            """SELECT event_id, task_id, generation, sequence, schema_version,
                      event_type, step_id, call_id, payload_json, created_at
               FROM ai_runtime_events
               WHERE task_id = ? AND generation = ? ORDER BY sequence""",
            (self.task_id, selected_generation),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["payload"] = _load(item.pop("payload_json", None))
            result.append(item)
        return result

    def get_report_generation_context(
        self,
        *,
        contract_version: str,
        plan_version: str,
        prompt_version: str,
        writer_version: str,
        validator_version: str,
    ) -> dict[str, Any] | None:
        identity = self.identity()
        row = self.conn.execute(
            """SELECT * FROM ai_report_generation_contexts
               WHERE task_id = ? AND generation = ?""",
            (self.task_id, identity.generation),
        ).fetchone()
        if row is None:
            return None
        item = dict(row)
        expected = {
            "contract_version": contract_version,
            "plan_version": plan_version,
            "prompt_version": prompt_version,
            "writer_version": writer_version,
            "validator_version": validator_version,
        }
        mismatches = [key for key, value in expected.items() if str(item.get(key)) != value]
        if mismatches:
            raise IncompatibleReportContextError(
                "年度报告恢复协议已变化，请按当前数据显式重新生成：" + ", ".join(mismatches)
            )
        for key in ("request", "evidence", "context", "precomputed", "plan"):
            item[key] = _load(item.pop(f"{key}_json", None))
        return item

    def has_report_progress(self) -> bool:
        identity = self.identity()
        section = self.conn.execute(
            """SELECT 1 FROM ai_report_sections
               WHERE task_id = ? AND generation = ? LIMIT 1""",
            (self.task_id, identity.generation),
        ).fetchone()
        event = self.conn.execute(
            """SELECT 1 FROM ai_runtime_events
               WHERE task_id = ? AND generation = ?
                 AND event_type IN (
                   'report_research_committed', 'report_section_committed',
                   'model_request_started', 'model_response_committed',
                   'tool_observation_committed'
                 ) LIMIT 1""",
            (self.task_id, identity.generation),
        ).fetchone()
        return section is not None or event is not None

    def commit_report_generation_context(
        self,
        *,
        context_key: str,
        source_key: str,
        contract_version: str,
        plan_version: str,
        prompt_version: str,
        writer_version: str,
        validator_version: str,
        request: dict[str, Any],
        evidence: list[dict[str, Any]],
        context: dict[str, Any],
        precomputed: dict[str, Any],
        plan: list[dict[str, Any]],
    ) -> dict[str, Any]:
        identity = self.identity()
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self._assert_lease()
            existing = self.conn.execute(
                """SELECT context_key, contract_version, plan_version, prompt_version,
                          writer_version, validator_version
                   FROM ai_report_generation_contexts
                   WHERE task_id = ? AND generation = ?""",
                (self.task_id, identity.generation),
            ).fetchone()
            values = (
                context_key,
                contract_version,
                plan_version,
                prompt_version,
                writer_version,
                validator_version,
            )
            if existing is not None:
                if tuple(str(value) for value in existing) != values:
                    raise IncompatibleReportContextError(
                        "同一代年度报告已有不同的固定资料，禁止无声切换来源"
                    )
                self.conn.rollback()
                return {"context_key": context_key, "reused": True}
            self.conn.execute(
                """INSERT INTO ai_report_generation_contexts
                   (task_id, generation, context_key, source_key, contract_version,
                    plan_version, prompt_version, writer_version, validator_version,
                    request_json, evidence_json, context_json, precomputed_json, plan_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    self.task_id,
                    identity.generation,
                    context_key,
                    source_key,
                    contract_version,
                    plan_version,
                    prompt_version,
                    writer_version,
                    validator_version,
                    _dump(request),
                    _dump(evidence),
                    _dump(context),
                    _dump(precomputed),
                    _dump(plan),
                ),
            )
            self._append_in_transaction(
                generation=identity.generation,
                event_type="report_context_frozen",
                payload={
                    "context_key": context_key,
                    "source_key": source_key,
                    "contract_version": contract_version,
                    "plan_version": plan_version,
                    "prompt_version": prompt_version,
                    "writer_version": writer_version,
                    "validator_version": validator_version,
                },
                step_id="report:context",
                call_id=f"context:{context_key}",
            )
            self.conn.commit()
            return {"context_key": context_key, "reused": False}
        except Exception:
            self.conn.rollback()
            raise

    def get_committed_model_response(self, call_id: str) -> dict[str, Any] | None:
        identity = self.identity()
        row = self.conn.execute(
            """SELECT payload_json FROM ai_runtime_events
               WHERE task_id = ? AND generation = ?
                 AND event_type = 'model_response_committed' AND call_id = ?""",
            (self.task_id, identity.generation, call_id),
        ).fetchone()
        return _load(row[0]) if row else None

    def get_prepared_model_request(self, call_id: str) -> PreparedModelRequest | None:
        """Read an immutable request descriptor without charging or mutating it."""

        identity = self.identity()
        row = self.conn.execute(
            """SELECT step_id, payload_json FROM ai_runtime_events
               WHERE task_id = ? AND generation = ?
                 AND event_type = 'model_request_started' AND call_id = ?
               ORDER BY sequence LIMIT 1""",
            (self.task_id, identity.generation, call_id),
        ).fetchone()
        if row is None:
            return None
        descriptor = _load(row["payload_json"])
        version = int(descriptor.get("request_descriptor_version") or 0)
        if version not in {0, 1}:
            raise IncompatibleModelRequestError(f"模型请求 descriptor 版本不受支持：{version}")
        response = self.get_committed_model_response(call_id)
        failure = self.conn.execute(
            """SELECT 1 FROM ai_runtime_events
               WHERE task_id = ? AND generation = ?
                 AND event_type = 'model_step_failed' AND call_id = ?""",
            (self.task_id, identity.generation, call_id),
        ).fetchone()
        return PreparedModelRequest(
            call_id=call_id,
            step_id=str(row["step_id"] or ""),
            descriptor=descriptor,
            uncertain_replay=response is None and failure is None,
        )

    def get_committed_tool_observation(self, call_id: str) -> dict[str, Any] | None:
        identity = self.identity()
        row = self.conn.execute(
            """SELECT payload_json FROM ai_runtime_events
               WHERE task_id = ? AND generation = ?
                 AND event_type = 'tool_observation_committed' AND call_id = ?""",
            (self.task_id, identity.generation, call_id),
        ).fetchone()
        return _load(row[0]) if row else None

    def prepare_model_request(
        self,
        *,
        call_id: str,
        step_id: str,
        payload: dict[str, Any],
        max_steps: int | None = None,
    ) -> PreparedModelRequest:
        """Persist once and return the immutable authoritative descriptor.

        A repeated logical ``call_id`` never replaces its original request.
        Credentials are intentionally absent; callers resolve them at dispatch
        time after confirming the stored provider/model remains available.
        """

        identity = self.identity()
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self._assert_lease()
            existing = self.conn.execute(
                """SELECT step_id, payload_json FROM ai_runtime_events
                   WHERE task_id = ? AND generation = ?
                     AND event_type = 'model_request_started' AND call_id = ?
                   ORDER BY sequence LIMIT 1""",
                (self.task_id, identity.generation, call_id),
            ).fetchone()
            response = self.conn.execute(
                """SELECT 1 FROM ai_runtime_events
                   WHERE task_id = ? AND generation = ?
                     AND event_type = 'model_response_committed' AND call_id = ?""",
                (self.task_id, identity.generation, call_id),
            ).fetchone()
            failure = self.conn.execute(
                """SELECT 1 FROM ai_runtime_events
                   WHERE task_id = ? AND generation = ?
                     AND event_type = 'model_step_failed' AND call_id = ?""",
                (self.task_id, identity.generation, call_id),
            ).fetchone()
            uncertain_replay = existing is not None and response is None and failure is None
            if existing is None:
                descriptor = dict(payload)
                descriptor.setdefault("request_descriptor_version", 1)
                if int(descriptor.get("request_descriptor_version") or 0) != 1:
                    raise IncompatibleModelRequestError("模型请求 descriptor 版本不受支持")
                if max_steps is not None:
                    usage = self.conn.execute(
                        """SELECT step_count FROM ai_runtime_budget_usage
                           WHERE task_id = ? AND generation = ?""",
                        (self.task_id, identity.generation),
                    ).fetchone()
                    consumed = int(usage[0] or 0) if usage else 0
                    if consumed >= max_steps:
                        raise PersistentBudgetExceededError(
                            f"任务步骤累计预算已耗尽：{consumed}/{max_steps}"
                        )
                self._append_in_transaction(
                    generation=identity.generation,
                    event_type="model_request_started",
                    payload=descriptor,
                    step_id=step_id,
                    call_id=call_id,
                )
                self._upsert_budget_in_transaction(step_count=1)
            elif uncertain_replay:
                descriptor = _load(existing["payload_json"])
                version = int(descriptor.get("request_descriptor_version") or 0)
                if version not in {0, 1}:
                    raise IncompatibleModelRequestError(
                        f"模型请求 descriptor 版本不受支持：{version}"
                    )
                self._append_in_transaction(
                    generation=identity.generation,
                    event_type="model_request_retried_after_uncertain_result",
                    payload={"call_id": call_id},
                    step_id=step_id,
                )
            else:
                descriptor = _load(existing["payload_json"])
                version = int(descriptor.get("request_descriptor_version") or 0)
                if version not in {0, 1}:
                    raise IncompatibleModelRequestError(
                        f"模型请求 descriptor 版本不受支持：{version}"
                    )
            self.conn.commit()
            return PreparedModelRequest(
                call_id=call_id,
                step_id=str(existing["step_id"] if existing is not None else step_id),
                descriptor=descriptor,
                uncertain_replay=uncertain_replay,
            )
        except Exception:
            self.conn.rollback()
            raise

    def reserve_model_dispatch(
        self,
        *,
        call_id: str,
        step_id: str,
        provider_id: str,
        max_model_calls: int,
    ) -> str:
        """Atomically authorize and charge one external provider dispatch.

        The committed reservation is the audit boundary: a later cancellation
        acknowledges only after already-reserved dispatches.  No SQLite lock is
        held while the provider performs network I/O.  A crash immediately
        after reservation is conservatively charged as unknown usage.
        """

        identity = self.identity()
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self._assert_lease()
            request_row = self.conn.execute(
                """SELECT 1 FROM ai_runtime_events
                   WHERE task_id = ? AND generation = ?
                     AND event_type = 'model_request_started' AND call_id = ?""",
                (self.task_id, identity.generation, call_id),
            ).fetchone()
            if request_row is None:
                raise IncompatibleModelRequestError(f"模型派发缺少持久请求 descriptor：{call_id}")
            committed = self.conn.execute(
                """SELECT 1 FROM ai_runtime_events
                   WHERE task_id = ? AND generation = ?
                     AND event_type = 'model_response_committed' AND call_id = ?""",
                (self.task_id, identity.generation, call_id),
            ).fetchone()
            if committed is not None:
                raise IncompatibleModelRequestError(f"模型响应已提交，禁止重复派发：{call_id}")
            usage = self.conn.execute(
                """SELECT model_call_count FROM ai_runtime_budget_usage
                   WHERE task_id = ? AND generation = ?""",
                (self.task_id, identity.generation),
            ).fetchone()
            consumed = int(usage[0] or 0) if usage else 0
            if consumed >= max_model_calls:
                raise PersistentBudgetExceededError(
                    f"任务模型调用累计预算已耗尽：{consumed}/{max_model_calls}"
                )
            row = self.conn.execute(
                """SELECT COALESCE(MAX(attempt_index), 0) + 1
                   FROM ai_model_dispatch_attempts
                   WHERE task_id = ? AND generation = ? AND call_id = ?""",
                (self.task_id, identity.generation, call_id),
            ).fetchone()
            attempt_index = int(row[0])
            dispatch_id = f"{call_id}:dispatch:{attempt_index}:{uuid.uuid4().hex[:8]}"
            self.conn.execute(
                """INSERT INTO ai_model_dispatch_attempts
                   (task_id, generation, dispatch_id, call_id, attempt_index, provider_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    self.task_id,
                    identity.generation,
                    dispatch_id,
                    call_id,
                    attempt_index,
                    provider_id,
                ),
            )
            self._append_in_transaction(
                generation=identity.generation,
                event_type="model_dispatch_reserved",
                payload={
                    "dispatch_id": dispatch_id,
                    "logical_call_id": call_id,
                    "attempt_index": attempt_index,
                    "provider_id": provider_id,
                    "usage": "unknown_until_response_commit",
                },
                step_id=step_id,
                call_id=dispatch_id,
            )
            self._upsert_budget_in_transaction(
                model_call_count=1,
                model_retry_count=1 if attempt_index > 1 else 0,
                usage_unknown_count=1,
            )
            self.conn.commit()
            return dispatch_id
        except Exception:
            self.conn.rollback()
            raise

    def mark_model_dispatch_failed(
        self,
        *,
        dispatch_id: str,
        error_type: str,
        elapsed_ms: int,
    ) -> None:
        """Record a completed failed attempt without changing its charged usage."""

        identity = self.identity()
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self._assert_lease()
            row = self.conn.execute(
                """SELECT call_id, status FROM ai_model_dispatch_attempts
                   WHERE task_id = ? AND generation = ? AND dispatch_id = ?""",
                (self.task_id, identity.generation, dispatch_id),
            ).fetchone()
            if row is None:
                raise IncompatibleModelRequestError(f"模型派发记录不存在：{dispatch_id}")
            if str(row["status"]) != "reserved":
                self.conn.rollback()
                return
            self.conn.execute(
                """UPDATE ai_model_dispatch_attempts
                   SET status = CASE WHEN status = 'reserved' THEN 'failed' ELSE status END,
                       error_type = CASE WHEN status = 'reserved' THEN ? ELSE error_type END,
                       elapsed_ms = CASE WHEN status = 'reserved' THEN ? ELSE elapsed_ms END,
                       completed_at = CASE WHEN status = 'reserved' THEN datetime('now') ELSE completed_at END
                   WHERE task_id = ? AND generation = ? AND dispatch_id = ?""",
                (
                    error_type,
                    max(0, int(elapsed_ms)),
                    self.task_id,
                    identity.generation,
                    dispatch_id,
                ),
            )
            self._append_in_transaction(
                generation=identity.generation,
                event_type="model_dispatch_failed",
                payload={
                    "dispatch_id": dispatch_id,
                    "logical_call_id": str(row["call_id"]),
                    "error_type": error_type,
                    "elapsed_ms": max(0, int(elapsed_ms)),
                },
                call_id=dispatch_id,
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def commit_model_failure(
        self,
        *,
        call_id: str,
        step_id: str,
        attempts: list[dict[str, Any]],
        elapsed_ms: int,
    ) -> None:
        """Persist exhausted provider attempts once, including unknown usage."""

        identity = self.identity()
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self._assert_lease()
            existing = self.conn.execute(
                """SELECT 1 FROM ai_runtime_events
                   WHERE task_id = ? AND generation = ?
                     AND event_type = 'model_step_failed' AND call_id = ?""",
                (self.task_id, identity.generation, call_id),
            ).fetchone()
            if existing:
                self.conn.rollback()
                return
            self._append_in_transaction(
                generation=identity.generation,
                event_type="model_step_failed",
                payload={"attempts": attempts, "elapsed_ms": max(0, int(elapsed_ms))},
                step_id=step_id,
                call_id=call_id,
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def commit_model_response(
        self,
        *,
        call_id: str,
        step_id: str,
        payload: dict[str, Any],
        elapsed_ms: int,
        attempt_count: int,
        section_retry: bool = False,
        successful_dispatch_id: str | None = None,
    ) -> dict[str, Any]:
        identity = self.identity()
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self._assert_lease()
            existing = self.conn.execute(
                """SELECT payload_json FROM ai_runtime_events
                   WHERE task_id = ? AND generation = ?
                     AND event_type = 'model_response_committed' AND call_id = ?""",
                (self.task_id, identity.generation, call_id),
            ).fetchone()
            if existing:
                self.conn.rollback()
                return _load(existing[0])
            self._append_in_transaction(
                generation=identity.generation,
                event_type="model_response_committed",
                payload=payload,
                step_id=step_id,
                call_id=call_id,
            )
            usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else None
            self._finalize_model_dispatch_in_transaction(
                generation=identity.generation,
                call_id=call_id,
                dispatch_id=str(successful_dispatch_id or ""),
                usage=usage,
                elapsed_ms=elapsed_ms,
            )
            if section_retry:
                self._upsert_budget_in_transaction(section_retry_count=1)
            self.conn.commit()
            return payload
        except Exception:
            self.conn.rollback()
            raise

    def _finalize_model_dispatch_in_transaction(
        self,
        *,
        generation: int,
        call_id: str,
        dispatch_id: str,
        usage: dict[str, Any] | None,
        elapsed_ms: int,
    ) -> None:
        if not dispatch_id:
            raise IncompatibleModelRequestError(
                f"模型响应缺少成功派发标识，不能安全核销预算：{call_id}"
            )
        row = self.conn.execute(
            """SELECT status, call_id FROM ai_model_dispatch_attempts
               WHERE task_id = ? AND generation = ? AND dispatch_id = ?""",
            (self.task_id, generation, dispatch_id),
        ).fetchone()
        if row is None or str(row["call_id"]) != call_id:
            raise IncompatibleModelRequestError(
                f"模型响应与派发记录不匹配：{call_id}/{dispatch_id}"
            )
        if str(row["status"]) == "committed":
            return
        self.conn.execute(
            """UPDATE ai_model_dispatch_attempts
               SET status = 'committed', error_type = NULL, elapsed_ms = ?,
                   usage_json = ?, completed_at = datetime('now')
               WHERE task_id = ? AND generation = ? AND dispatch_id = ?""",
            (
                max(0, int(elapsed_ms)),
                _dump(usage or {}),
                self.task_id,
                generation,
                dispatch_id,
            ),
        )
        self.conn.execute(
            """UPDATE ai_runtime_budget_usage
               SET input_tokens = input_tokens + ?,
                   output_tokens = output_tokens + ?,
                   usage_unknown_count = MAX(0, usage_unknown_count - CASE WHEN ? THEN 1 ELSE 0 END),
                   updated_at = datetime('now')
               WHERE task_id = ? AND generation = ?""",
            (
                _usage_value(usage, "input_tokens", "prompt_tokens"),
                _usage_value(usage, "output_tokens", "completion_tokens"),
                1 if usage else 0,
                self.task_id,
                generation,
            ),
        )

    def get_budget_usage(self) -> dict[str, Any]:
        identity = self.identity()
        row = self.conn.execute(
            """SELECT * FROM ai_runtime_budget_usage
               WHERE task_id = ? AND generation = ?""",
            (self.task_id, identity.generation),
        ).fetchone()
        if row is None:
            return {
                "step_count": 0,
                "model_call_count": 0,
                "tool_call_count": 0,
                "model_retry_count": 0,
                "section_retry_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "usage_unknown_count": 0,
                "active_elapsed_ms": 0,
                "waiting_input_elapsed_ms": 0,
                "queued_elapsed_ms": 0,
            }
        usage = dict(row)
        if usage.get("active_started_at"):
            live_row = self.conn.execute(
                """SELECT MAX(0, CAST(ROUND(
                       (julianday('now') - julianday(?)) * 86400000
                   ) AS INTEGER))""",
                (usage["active_started_at"],),
            ).fetchone()
            usage["active_elapsed_ms"] = int(usage.get("active_elapsed_ms") or 0) + int(
                live_row[0] or 0
            )
        return usage

    def record_execution_started(
        self,
        *,
        queued_since: str | None,
        previous_active_until: str | None = None,
    ) -> None:
        """Start a durable active-time segment and close queue/wait segments.

        A recovered worker deliberately starts a fresh active segment. Time for
        which no worker held the lease is never charged to the execution cap.
        """

        identity = self.identity()
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self._assert_lease()
            self._upsert_budget_in_transaction()
            if previous_active_until:
                # A crashed worker cannot close its segment. Charge the
                # already-issued lease window through its expiry before the
                # takeover starts a fresh segment. This is fail-closed for the
                # cumulative timeout and does not include later queue/user wait.
                self.conn.execute(
                    """UPDATE ai_runtime_budget_usage
                       SET active_elapsed_ms = active_elapsed_ms +
                             CASE WHEN active_started_at IS NULL THEN 0 ELSE
                               MAX(0, CAST(ROUND(
                                 (julianday(?) - julianday(active_started_at)) * 86400000
                               ) AS INTEGER)) END,
                           active_started_at = NULL,
                           updated_at = datetime('now')
                       WHERE task_id = ? AND generation = ?""",
                    (previous_active_until, self.task_id, identity.generation),
                )
            row = self.conn.execute(
                """SELECT waiting_started_at FROM ai_runtime_budget_usage
                   WHERE task_id = ? AND generation = ?""",
                (self.task_id, identity.generation),
            ).fetchone()
            if row and row[0]:
                self.conn.execute(
                    """UPDATE ai_runtime_budget_usage
                       SET waiting_input_elapsed_ms = waiting_input_elapsed_ms +
                             MAX(0, CAST(ROUND(
                               (julianday('now') - julianday(waiting_started_at)) * 86400000
                             ) AS INTEGER)),
                           waiting_started_at = NULL,
                           updated_at = datetime('now')
                       WHERE task_id = ? AND generation = ?""",
                    (self.task_id, identity.generation),
                )
            if queued_since:
                self.conn.execute(
                    """UPDATE ai_runtime_budget_usage
                       SET queued_elapsed_ms = queued_elapsed_ms +
                             MAX(0, CAST(ROUND(
                               (julianday('now') - julianday(?)) * 86400000
                             ) AS INTEGER)),
                           updated_at = datetime('now')
                       WHERE task_id = ? AND generation = ?""",
                    (queued_since, self.task_id, identity.generation),
                )
            self.conn.execute(
                """UPDATE ai_runtime_budget_usage
                   SET active_started_at = datetime('now'), updated_at = datetime('now')
                   WHERE task_id = ? AND generation = ?""",
                (self.task_id, identity.generation),
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def mark_waiting_for_input(self) -> None:
        """Close active execution and begin an excluded user-wait segment."""

        identity = self.identity()
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self._assert_lease()
            self._close_active_segment_in_transaction(identity.generation)
            self.conn.execute(
                """UPDATE ai_runtime_budget_usage
                   SET waiting_started_at = COALESCE(waiting_started_at, datetime('now')),
                       updated_at = datetime('now')
                   WHERE task_id = ? AND generation = ?""",
                (self.task_id, identity.generation),
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def record_execution_stopped(self) -> None:
        """Persist the current active segment, including after terminal status."""

        identity = self.identity()
        active = current_execution_identity()
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            if active is not None and active.task_id == self.task_id:
                owned = self.conn.execute(
                    """SELECT 1 FROM ai_task_runs
                       WHERE task_id = ? AND lease_owner = ? AND lease_generation = ?""",
                    (active.task_id, active.lease_owner, active.lease_generation),
                ).fetchone()
                if owned is None:
                    raise LostTaskLeaseError(f"task lease lost: {self.task_id}")
            self._close_active_segment_in_transaction(identity.generation)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def _close_active_segment_in_transaction(self, generation: int) -> None:
        self.conn.execute(
            """UPDATE ai_runtime_budget_usage
               SET active_elapsed_ms = active_elapsed_ms +
                     CASE WHEN active_started_at IS NULL THEN 0 ELSE
                       MAX(0, CAST(ROUND(
                         (julianday('now') - julianday(active_started_at)) * 86400000
                       ) AS INTEGER)) END,
                   active_started_at = NULL,
                   updated_at = datetime('now')
               WHERE task_id = ? AND generation = ?""",
            (self.task_id, generation),
        )

    def assert_budget_available(
        self,
        *,
        max_steps: int,
        max_model_calls: int,
        max_tool_calls: int,
        max_active_elapsed_ms: int,
        check_tool_calls: bool = True,
        check_steps: bool = True,
    ) -> None:
        usage = self.get_budget_usage()
        checks = []
        if check_steps:
            checks.append(("步骤", int(usage.get("step_count") or 0), max_steps))
        checks.extend(
            [
                ("模型调用", int(usage.get("model_call_count") or 0), max_model_calls),
                (
                    "有效执行时间",
                    int(usage.get("active_elapsed_ms") or 0),
                    max_active_elapsed_ms,
                ),
            ]
        )
        if check_tool_calls:
            checks.insert(
                2,
                ("工具调用", int(usage.get("tool_call_count") or 0), max_tool_calls),
            )
        for label, consumed, limit in checks:
            if consumed >= limit:
                raise PersistentBudgetExceededError(
                    f"任务{label}累计预算已耗尽：{consumed}/{limit}"
                )

    def commit_report_tool_observation(
        self,
        *,
        call_id: str,
        step_id: str,
        tool_name: str,
        params: dict[str, Any],
        outcome: dict[str, Any],
        elapsed_ms: int,
        counted: bool = True,
    ) -> dict[str, Any]:
        identity = self.identity()
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self._assert_lease()
            existing = self.conn.execute(
                """SELECT payload_json FROM ai_runtime_events
                   WHERE task_id = ? AND generation = ?
                     AND event_type = 'tool_observation_committed' AND call_id = ?""",
                (self.task_id, identity.generation, call_id),
            ).fetchone()
            if existing:
                self.conn.rollback()
                return _load(existing[0])
            payload = {"tool_name": tool_name, "params": params, "outcome": outcome}
            self.conn.execute(
                """INSERT INTO ai_tool_calls
                   (task_id, tool_name, status, params_summary, result_summary,
                    source_range, error, completed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (
                    self.task_id,
                    tool_name,
                    str(outcome.get("status") or "error"),
                    _dump(params),
                    str(outcome.get("result_summary") or ""),
                    str(outcome.get("source_range") or ""),
                    outcome.get("error"),
                ),
            )
            self._append_in_transaction(
                generation=identity.generation,
                event_type="tool_observation_committed",
                payload=payload,
                step_id=step_id,
                call_id=call_id,
            )
            self._upsert_budget_in_transaction(
                tool_call_count=1 if counted else 0,
            )
            self.conn.commit()
            return payload
        except Exception:
            self.conn.rollback()
            raise

    def _upsert_budget_in_transaction(self, **increments: int) -> None:
        identity = self.identity()
        fields = (
            "step_count",
            "model_call_count",
            "tool_call_count",
            "model_retry_count",
            "section_retry_count",
            "input_tokens",
            "output_tokens",
            "usage_unknown_count",
            "active_elapsed_ms",
            "waiting_input_elapsed_ms",
            "queued_elapsed_ms",
        )
        values = [max(0, int(increments.get(field, 0))) for field in fields]
        update = ", ".join(f"{field}={field}+excluded.{field}" for field in fields)
        self.conn.execute(
            f"""INSERT INTO ai_runtime_budget_usage
                (task_id, generation, {", ".join(fields)})
                VALUES (?, ?, {", ".join("?" for _ in fields)})
                ON CONFLICT(task_id, generation) DO UPDATE SET
                  {update}, updated_at=datetime('now')""",
            (self.task_id, identity.generation, *values),
        )

    def get_report_research(
        self,
        *,
        context_key: str,
        research_version: str,
    ) -> dict[str, Any] | None:
        identity = self.identity()
        row = self.conn.execute(
            """SELECT payload_json FROM ai_runtime_events
               WHERE task_id = ? AND generation = ?
                 AND event_type = 'report_research_committed'
                 AND call_id = ?
               ORDER BY sequence DESC LIMIT 1""",
            (
                self.task_id,
                identity.generation,
                f"research:{research_version}:{context_key}",
            ),
        ).fetchone()
        return _load(row[0]) if row else None

    def commit_report_research(
        self,
        *,
        context_key: str,
        research_version: str,
        research_summary: str,
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        identity = self.identity()
        call_id = f"research:{research_version}:{context_key}"
        payload = {
            "context_key": context_key,
            "research_version": research_version,
            "research_summary": research_summary,
            "evidence": evidence,
        }
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self._assert_lease()
            existing = self.conn.execute(
                """SELECT payload_json FROM ai_runtime_events
                   WHERE task_id = ? AND generation = ?
                     AND event_type = 'report_research_committed' AND call_id = ?""",
                (self.task_id, identity.generation, call_id),
            ).fetchone()
            if existing:
                self.conn.rollback()
                return _load(existing[0])
            self._append_in_transaction(
                generation=identity.generation,
                event_type="report_research_committed",
                payload=payload,
                step_id="report:research",
                call_id=call_id,
            )
            self.conn.commit()
            return payload
        except Exception:
            self.conn.rollback()
            raise

    def commit_tool_observation(
        self,
        *,
        call_id: str,
        step_id: str,
        turn_id: str,
        session_id: int | None,
        step_index: int,
        tool_name: str,
        params: dict[str, Any],
        outcome: dict[str, Any],
        legacy_payload: dict[str, Any],
    ) -> bool:
        """Atomically persist trace, recovery fact, and model-visible observation."""

        identity = self.identity()
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self._assert_lease()
            duplicate = self.conn.execute(
                """SELECT 1 FROM ai_runtime_events
                   WHERE task_id = ? AND generation = ?
                     AND event_type = 'tool_observation_committed' AND call_id = ?""",
                (self.task_id, identity.generation, call_id),
            ).fetchone()
            if duplicate:
                self.conn.rollback()
                return False
            self.conn.execute(
                """INSERT INTO ai_tool_calls
                   (task_id, tool_name, status, params_summary, result_summary,
                    source_range, error, completed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (
                    self.task_id,
                    tool_name,
                    str(outcome.get("status") or "error"),
                    _dump(params),
                    str(outcome.get("result_summary") or ""),
                    str(outcome.get("source_range") or ""),
                    outcome.get("error"),
                ),
            )
            self.conn.execute(
                """INSERT INTO ai_agent_turn_events
                   (task_id, session_id, turn_id, sequence, step_index,
                    event_type, payload_json)
                   SELECT ?, ?, ?, COALESCE(MAX(sequence), 0) + 1, ?,
                          'tool_result', ?
                   FROM ai_agent_turn_events WHERE turn_id = ?""",
                (
                    self.task_id,
                    session_id,
                    turn_id,
                    step_index,
                    _dump(legacy_payload),
                    turn_id,
                ),
            )
            self._append_in_transaction(
                generation=identity.generation,
                event_type="tool_observation_committed",
                payload={"tool_name": tool_name, "params": params, "outcome": outcome},
                step_id=step_id,
                call_id=call_id,
            )
            self._upsert_budget_in_transaction(
                tool_call_count=0 if bool(outcome.get("duplicate")) else 1,
            )
            self.conn.commit()
            return True
        except Exception:
            self.conn.rollback()
            raise

    def upsert_report_section(
        self,
        *,
        section_id: str,
        section_order: int,
        status: str,
        context_key: str,
        plan_version: str,
        writer_version: str,
        validator_version: str,
        source_kind: str,
        section: dict[str, Any] | None,
        audit: dict[str, Any],
        usage: dict[str, Any],
        attempt_count: int,
        fallback_reason: str | None = None,
    ) -> dict[str, Any]:
        identity = self.identity()
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self._assert_lease()
            existing = self.conn.execute(
                """SELECT section_version, status, context_key, writer_version,
                          validator_version FROM ai_report_sections
                   WHERE task_id = ? AND generation = ? AND section_id = ?""",
                (self.task_id, identity.generation, section_id),
            ).fetchone()
            if (
                existing
                and str(existing[1]) == "validated"
                and (str(existing[2]), str(existing[3]), str(existing[4]))
                == (context_key, writer_version, validator_version)
            ):
                self.conn.rollback()
                return self.get_report_section(section_id) or {}
            version = int(existing[0]) + 1 if existing else 1
            self.conn.execute(
                """INSERT INTO ai_report_sections
                   (task_id, generation, section_id, section_order, section_version,
                    status, context_key, plan_version, writer_version, validator_version,
                    source_kind, section_json, audit_json, usage_json, attempt_count,
                    fallback_reason, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                   ON CONFLICT(task_id, generation, section_id) DO UPDATE SET
                     section_order=excluded.section_order,
                     section_version=excluded.section_version,
                     status=excluded.status,
                     context_key=excluded.context_key,
                     plan_version=excluded.plan_version,
                     writer_version=excluded.writer_version,
                     validator_version=excluded.validator_version,
                     source_kind=excluded.source_kind,
                     section_json=excluded.section_json,
                     audit_json=excluded.audit_json,
                     usage_json=excluded.usage_json,
                     attempt_count=excluded.attempt_count,
                     fallback_reason=excluded.fallback_reason,
                     updated_at=datetime('now')""",
                (
                    self.task_id,
                    identity.generation,
                    section_id,
                    section_order,
                    version,
                    status,
                    context_key,
                    plan_version,
                    writer_version,
                    validator_version,
                    source_kind,
                    _dump(section) if section is not None else None,
                    _dump(audit),
                    _dump(usage),
                    attempt_count,
                    fallback_reason,
                ),
            )
            self._append_in_transaction(
                generation=identity.generation,
                event_type="report_section_committed",
                payload={
                    "section_id": section_id,
                    "section_order": section_order,
                    "section_version": version,
                    "status": status,
                    "source_kind": source_kind,
                },
                step_id=f"section:{section_id}",
                call_id=f"section:{section_id}:v{version}",
            )
            self.conn.commit()
            return self.get_report_section(section_id) or {}
        except Exception:
            self.conn.rollback()
            raise

    def get_report_section(self, section_id: str) -> dict[str, Any] | None:
        identity = self.identity()
        row = self.conn.execute(
            """SELECT * FROM ai_report_sections
               WHERE task_id = ? AND generation = ? AND section_id = ?""",
            (self.task_id, identity.generation, section_id),
        ).fetchone()
        return self._section_row(row) if row else None

    def list_report_sections(self, *, validated_only: bool = False) -> list[dict[str, Any]]:
        identity = self.identity()
        predicate = " AND status = 'validated'" if validated_only else ""
        rows = self.conn.execute(
            f"""SELECT * FROM ai_report_sections
                WHERE task_id = ? AND generation = ?{predicate}
                ORDER BY section_order, section_id""",
            (self.task_id, identity.generation),
        ).fetchall()
        return [self._section_row(row) for row in rows]

    def report_section_watermark(self) -> int:
        identity = self.identity()
        row = self.conn.execute(
            """SELECT COALESCE(MAX(sequence), 0) FROM ai_runtime_events
               WHERE task_id = ? AND generation = ?
                 AND event_type IN ('report_section_committed', 'report_section_invalidated')""",
            (self.task_id, identity.generation),
        ).fetchone()
        return int(row[0] or 0)

    def list_report_section_changes(self, *, after_sequence: int = 0) -> list[dict[str, Any]]:
        identity = self.identity()
        rows = self.conn.execute(
            """SELECT sequence, payload_json FROM ai_runtime_events
               WHERE task_id = ? AND generation = ?
                 AND event_type IN ('report_section_committed', 'report_section_invalidated')
                 AND sequence > ?
               ORDER BY sequence""",
            (self.task_id, identity.generation, max(0, int(after_sequence))),
        ).fetchall()
        changes: list[dict[str, Any]] = []
        for row in rows:
            payload = _load(row["payload_json"])
            section_id = str(payload.get("section_id") or "")
            section = self.get_report_section(section_id)
            if section is not None:
                changes.append({"sequence": int(row["sequence"]), **section})
        return changes

    @staticmethod
    def _section_row(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["section"] = (
            _load(item.pop("section_json", None)) if item.get("section_json") else None
        )
        item["audit"] = _load(item.pop("audit_json", None))
        item["usage"] = _load(item.pop("usage_json", None))
        return item

    def publish_artifact(
        self,
        *,
        artifact_id: str,
        context_key: str,
        artifact: dict[str, Any],
        publication: dict[str, Any],
    ) -> None:
        """Commit immutable candidate and publication fact in one local transaction."""

        identity = self.identity()
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self._assert_lease()
            self.conn.execute(
                """INSERT INTO ai_report_artifacts
                   (task_id, generation, artifact_id, context_key, status,
                    artifact_json, publication_json, published_at)
                   VALUES (?, ?, ?, ?, 'published', ?, ?, datetime('now'))
                   ON CONFLICT(task_id, generation, artifact_id) DO UPDATE SET
                     status='published', publication_json=excluded.publication_json,
                     published_at=COALESCE(ai_report_artifacts.published_at, datetime('now'))""",
                (
                    self.task_id,
                    identity.generation,
                    artifact_id,
                    context_key,
                    _dump(artifact),
                    _dump(publication),
                ),
            )
            self._append_in_transaction(
                generation=identity.generation,
                event_type="report_published",
                payload={"artifact_id": artifact_id, "context_key": context_key},
                step_id="report:publish",
                call_id=artifact_id,
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def invalidate_report_sections(self, *, reason: str) -> int:
        identity = self.identity()
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self._assert_lease()
            rows = self.conn.execute(
                """SELECT section_id, section_version FROM ai_report_sections
                   WHERE task_id = ? AND generation = ? AND status = 'validated'""",
                (self.task_id, identity.generation),
            ).fetchall()
            self.conn.execute(
                """UPDATE ai_report_sections
                   SET status = 'invalidated', section_version = section_version + 1,
                       updated_at = datetime('now')
                   WHERE task_id = ? AND generation = ? AND status = 'validated'""",
                (self.task_id, identity.generation),
            )
            for row in rows:
                self._append_in_transaction(
                    generation=identity.generation,
                    event_type="report_section_invalidated",
                    payload={
                        "section_id": str(row["section_id"]),
                        "section_version": int(row["section_version"]) + 1,
                        "reason": reason,
                    },
                    step_id=f"section:{row['section_id']}",
                )
            self.conn.commit()
            return len(rows)
        except Exception:
            self.conn.rollback()
            raise
