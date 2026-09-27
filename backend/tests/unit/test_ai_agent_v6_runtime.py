from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest

from backend.core.migrations import migrate_080, migrate_081, migrate_082
from backend.domains.agent_runtime.event_log import AgentEventLog
from backend.domains.agent_runtime.runtime_store import (
    IncompatibleModelRequestError,
    IncompatibleReportContextError,
    LostTaskLeaseError,
    PersistentBudgetExceededError,
    RuntimeStore,
)
from backend.domains.ai_tasks.execution_context import (
    TaskExecutionIdentity,
    bind_execution_identity,
    reset_execution_identity,
)


def _init_runtime_schema(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE ai_task_runs (
            task_id TEXT PRIMARY KEY,
            task_type TEXT NOT NULL,
            status TEXT NOT NULL,
            stage TEXT NOT NULL,
            progress_pct REAL NOT NULL DEFAULT 0,
            message TEXT NOT NULL DEFAULT '',
            request_json TEXT,
            result_json TEXT,
            error TEXT,
            lease_owner TEXT,
            lease_expires_at TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE ai_tool_calls (
            tool_call_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            status TEXT NOT NULL,
            params_summary TEXT NOT NULL DEFAULT '',
            result_summary TEXT NOT NULL DEFAULT '',
            source_range TEXT NOT NULL DEFAULT '',
            error TEXT,
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT
        );
        CREATE TABLE ai_agent_turn_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            session_id INTEGER,
            turn_id TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            step_index INTEGER,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(turn_id, sequence)
        );
        """
    )
    migrate_080(conn)
    migrate_081(conn)
    migrate_082(conn)
    conn.execute(
        """INSERT INTO ai_task_runs
           (task_id, task_type, status, stage, runtime_version, workflow_version,
            event_schema_version, generation, lease_owner, lease_generation)
           VALUES ('task-v6', 'ai_report_yearly', 'running', 'writing_sections',
                   'v6', 'yearly_v6', 2, 1, 'worker:new', 2)"""
    )
    conn.commit()


@pytest.fixture
def runtime_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(":memory:")
    _init_runtime_schema(conn)
    yield conn
    conn.close()


def test_tool_observation_and_trace_commit_atomically(runtime_conn: sqlite3.Connection) -> None:
    store = RuntimeStore(runtime_conn, "task-v6")
    assert store.commit_tool_observation(
        call_id="call-1",
        step_id="step-1",
        turn_id="turn-1",
        session_id=1,
        step_index=1,
        tool_name="yearly_overview",
        params={"year": 2025},
        outcome={"status": "ok", "result_summary": "ready", "data": {"plays": 3}},
        legacy_payload={"call_id": "call-1", "outcome": {"status": "ok"}},
    )
    assert not store.commit_tool_observation(
        call_id="call-1",
        step_id="step-1",
        turn_id="turn-1",
        session_id=1,
        step_index=1,
        tool_name="yearly_overview",
        params={"year": 2025},
        outcome={"status": "ok", "result_summary": "ready", "data": {"plays": 3}},
        legacy_payload={"call_id": "call-1", "outcome": {"status": "ok"}},
    )
    assert runtime_conn.execute("SELECT COUNT(*) FROM ai_tool_calls").fetchone()[0] == 1
    legacy = runtime_conn.execute(
        "SELECT event_type, payload_json FROM ai_agent_turn_events"
    ).fetchall()
    assert [row["event_type"] for row in legacy] == ["tool_result"]
    events = store.list_events()
    assert [event["event_type"] for event in events] == ["tool_observation_committed"]


def test_tool_observation_transaction_rolls_back_every_projection(
    runtime_conn: sqlite3.Connection,
) -> None:
    runtime_conn.execute(
        """CREATE TRIGGER fail_tool_observation BEFORE INSERT ON ai_runtime_events
           WHEN NEW.event_type = 'tool_observation_committed'
           BEGIN SELECT RAISE(ABORT, 'injected failure'); END"""
    )
    with pytest.raises(sqlite3.IntegrityError, match="injected failure"):
        RuntimeStore(runtime_conn, "task-v6").commit_tool_observation(
            call_id="call-fail",
            step_id="step-fail",
            turn_id="turn-fail",
            session_id=1,
            step_index=1,
            tool_name="yearly_overview",
            params={"year": 2025},
            outcome={"status": "ok", "result_summary": "ready"},
            legacy_payload={"call_id": "call-fail", "outcome": {"status": "ok"}},
        )

    assert runtime_conn.execute("SELECT COUNT(*) FROM ai_tool_calls").fetchone()[0] == 0
    assert runtime_conn.execute("SELECT COUNT(*) FROM ai_agent_turn_events").fetchone()[0] == 0
    assert RuntimeStore(runtime_conn, "task-v6").list_events() == []


def test_late_worker_cannot_overwrite_new_generation(runtime_conn: sqlite3.Connection) -> None:
    token = bind_execution_identity(TaskExecutionIdentity("task-v6", "worker:old", 1))
    try:
        with pytest.raises(LostTaskLeaseError):
            RuntimeStore(runtime_conn, "task-v6").append("model_response_committed", {})
    finally:
        reset_execution_identity(token)
    assert RuntimeStore(runtime_conn, "task-v6").list_events() == []


def test_two_connections_block_takeover_worker_and_post_cancel_writes(tmp_path) -> None:
    db_path = tmp_path / "runtime-takeover.sqlite"
    old_conn = sqlite3.connect(db_path)
    new_conn = sqlite3.connect(db_path)
    old_conn.row_factory = sqlite3.Row
    new_conn.row_factory = sqlite3.Row
    try:
        _init_runtime_schema(old_conn)
        old_token = bind_execution_identity(TaskExecutionIdentity("task-v6", "worker:new", 2))
        try:
            new_conn.execute(
                """UPDATE ai_task_runs
                   SET lease_owner='worker:replacement', lease_generation=3
                   WHERE task_id='task-v6'"""
            )
            new_conn.commit()
            with pytest.raises(LostTaskLeaseError):
                RuntimeStore(old_conn, "task-v6").append("stale_output", {})
        finally:
            reset_execution_identity(old_token)

        new_token = bind_execution_identity(
            TaskExecutionIdentity("task-v6", "worker:replacement", 3)
        )
        try:
            new_conn.execute("UPDATE ai_task_runs SET status='cancelling' WHERE task_id='task-v6'")
            new_conn.commit()
            with pytest.raises(LostTaskLeaseError):
                RuntimeStore(old_conn, "task-v6").append("post_cancel_output", {})
        finally:
            reset_execution_identity(new_token)
        assert old_conn.execute("SELECT COUNT(*) FROM ai_runtime_events").fetchone()[0] == 0
    finally:
        old_conn.close()
        new_conn.close()


def test_late_worker_cannot_pollute_legacy_model_projection(
    runtime_conn: sqlite3.Connection,
) -> None:
    log = AgentEventLog(
        runtime_conn,
        task_id="task-v6",
        turn_id="probe-turn",
        session_id=None,
    )
    token = bind_execution_identity(TaskExecutionIdentity("task-v6", "worker:old", 1))
    try:
        with pytest.raises(LostTaskLeaseError):
            log.append_model_message(
                {"role": "assistant", "content": "STALE_WORKER_RESPONSE"},
                origin="model_response",
                step_index=1,
                call_id="old-call",
            )
    finally:
        reset_execution_identity(token)

    assert runtime_conn.execute("SELECT COUNT(*) FROM ai_agent_turn_events").fetchone()[0] == 0
    assert runtime_conn.execute("SELECT COUNT(*) FROM ai_runtime_events").fetchone()[0] == 0
    assert log.reconstruct_messages() == []


def test_model_message_rolls_back_legacy_projection_when_runtime_commit_fails(
    runtime_conn: sqlite3.Connection,
) -> None:
    runtime_conn.execute(
        """CREATE TRIGGER fail_model_response BEFORE INSERT ON ai_runtime_events
           WHEN NEW.event_type = 'model_response_committed'
           BEGIN SELECT RAISE(ABORT, 'injected model response failure'); END"""
    )
    log = AgentEventLog(
        runtime_conn,
        task_id="task-v6",
        turn_id="failure-turn",
        session_id=None,
    )

    with pytest.raises(sqlite3.IntegrityError, match="injected model response failure"):
        log.append_model_message(
            {"role": "assistant", "content": "must rollback"},
            origin="model_response",
            step_index=2,
            call_id="response-failure",
        )

    assert runtime_conn.execute("SELECT COUNT(*) FROM ai_agent_turn_events").fetchone()[0] == 0
    assert runtime_conn.execute("SELECT COUNT(*) FROM ai_runtime_events").fetchone()[0] == 0
    assert log.reconstruct_messages() == []


def test_v5_task_does_not_silently_switch_to_v6_event_contract(
    runtime_conn: sqlite3.Connection,
) -> None:
    runtime_conn.execute(
        """INSERT INTO ai_task_runs
           (task_id, task_type, status, stage, runtime_version, workflow_version,
            event_schema_version, generation, lease_generation)
           VALUES ('task-v5', 'ai_chat_agent', 'running', 'agent_running',
                   'v5', 'v5', 1, 1, 0)"""
    )
    runtime_conn.commit()

    log = AgentEventLog(
        runtime_conn,
        task_id="task-v5",
        turn_id="turn-v5",
        session_id=None,
    )
    log.append("turn_started", {"runtime": "v5"})

    assert len(log.list_events()) == 1
    assert (
        runtime_conn.execute(
            "SELECT COUNT(*) FROM ai_runtime_events WHERE task_id='task-v5'"
        ).fetchone()[0]
        == 0
    )


def test_report_research_checkpoint_is_idempotent(runtime_conn: sqlite3.Connection) -> None:
    store = RuntimeStore(runtime_conn, "task-v6")
    first = store.commit_report_research(
        context_key="context-a",
        research_version="research-v1",
        research_summary="第一次研究",
        evidence=[{"tool_name": "yearly_overview", "data": {"plays": 3}}],
    )
    reused = store.commit_report_research(
        context_key="context-a",
        research_version="research-v1",
        research_summary="不应覆盖",
        evidence=[],
    )

    assert reused == first
    assert (
        store.get_report_research(
            context_key="context-a",
            research_version="research-v1",
        )
        == first
    )
    assert [event["event_type"] for event in store.list_events()] == ["report_research_committed"]


def test_frozen_report_context_is_immutable_and_version_checked(
    runtime_conn: sqlite3.Connection,
) -> None:
    store = RuntimeStore(runtime_conn, "task-v6")
    store.commit_report_generation_context(
        context_key="context-rev-1",
        source_key="source-rev-1",
        contract_version="contract-v1",
        plan_version="plan-v1",
        prompt_version="prompt-v1",
        writer_version="writer-v1",
        validator_version="validator-v1",
        request={"year": 2025},
        evidence=[{"tool_name": "yearly_overview", "plays": 3}],
        context={"hero": {"total_plays": 3}},
        precomputed={"chart_data": {"calendar": {"plays": 3}}},
        plan=[{"id": "opening", "heading": "开场"}],
    )

    frozen = store.get_report_generation_context(
        contract_version="contract-v1",
        plan_version="plan-v1",
        prompt_version="prompt-v1",
        writer_version="writer-v1",
        validator_version="validator-v1",
    )
    assert frozen["source_key"] == "source-rev-1"
    assert frozen["context"]["hero"]["total_plays"] == 3
    with pytest.raises(IncompatibleReportContextError, match="prompt_version"):
        store.get_report_generation_context(
            contract_version="contract-v1",
            plan_version="plan-v1",
            prompt_version="prompt-v2",
            writer_version="writer-v1",
            validator_version="validator-v1",
        )
    with pytest.raises(IncompatibleReportContextError, match="禁止无声切换来源"):
        store.commit_report_generation_context(
            context_key="context-rev-2",
            source_key="source-rev-2",
            contract_version="contract-v1",
            plan_version="plan-v1",
            prompt_version="prompt-v1",
            writer_version="writer-v1",
            validator_version="validator-v1",
            request={"year": 2025},
            evidence=[],
            context={"hero": {"total_plays": 99}},
            precomputed={},
            plan=[],
        )


def test_budget_usage_survives_connection_restart_and_distinguishes_unknown_usage(
    tmp_path,
) -> None:
    db_path = tmp_path / "runtime-budget.sqlite"
    first = sqlite3.connect(db_path)
    first.row_factory = sqlite3.Row
    _init_runtime_schema(first)
    first_store = RuntimeStore(first, "task-v6")
    first_store.record_execution_started(queued_since=None)
    first_store.prepare_model_request(
        call_id="model-1",
        step_id="step-1",
        payload={
            "messages": [{"role": "user", "content": "test"}],
            "tool_schemas": [],
            "provider_id": "fake:model",
            "parameters": {},
            "prompt_version": "test-v1",
        },
        max_steps=2,
    )
    dispatch_1 = first_store.reserve_model_dispatch(
        call_id="model-1",
        step_id="step-1",
        provider_id="fake:model",
        max_model_calls=4,
    )
    first_store.mark_model_dispatch_failed(
        dispatch_id=dispatch_1,
        error_type="ProviderNetworkError",
        elapsed_ms=10,
    )
    dispatch_2 = first_store.reserve_model_dispatch(
        call_id="model-1",
        step_id="step-1",
        provider_id="fake:model",
        max_model_calls=4,
    )
    first_store.commit_model_response(
        call_id="model-1",
        step_id="step-1",
        payload={"content": "ok", "usage": {"input_tokens": 4, "output_tokens": 2}},
        elapsed_ms=25,
        attempt_count=2,
        successful_dispatch_id=dispatch_2,
    )
    first.execute(
        """UPDATE ai_runtime_budget_usage
           SET active_started_at=datetime('now', '-2 seconds')
           WHERE task_id='task-v6'"""
    )
    first.commit()
    first_store.mark_waiting_for_input()
    first.execute(
        """UPDATE ai_runtime_budget_usage
           SET waiting_started_at=datetime('now', '-3 seconds')
           WHERE task_id='task-v6'"""
    )
    first.commit()
    first_store.record_execution_started(queued_since="2000-01-01 00:00:00")
    first.execute(
        """UPDATE ai_runtime_budget_usage
           SET active_started_at=datetime('now', '-2 seconds'),
               queued_elapsed_ms=1000
           WHERE task_id='task-v6'"""
    )
    first.commit()
    first_store.record_execution_stopped()
    first.close()

    resumed = sqlite3.connect(db_path)
    resumed.row_factory = sqlite3.Row
    try:
        store = RuntimeStore(resumed, "task-v6")
        usage = store.get_budget_usage()
        assert usage["step_count"] == 1
        assert usage["model_call_count"] == 2
        assert usage["model_retry_count"] == 1
        assert usage["usage_unknown_count"] == 1
        assert usage["active_elapsed_ms"] >= 4000
        assert usage["waiting_input_elapsed_ms"] >= 3000
        assert usage["queued_elapsed_ms"] == 1000
        with pytest.raises(PersistentBudgetExceededError, match="步骤"):
            store.assert_budget_available(
                max_steps=1,
                max_model_calls=4,
                max_tool_calls=4,
                max_active_elapsed_ms=1000,
            )

        resumed.execute(
            """UPDATE ai_runtime_budget_usage
               SET step_count=0, tool_call_count=4, active_elapsed_ms=0
               WHERE task_id='task-v6'"""
        )
        resumed.commit()
        store.assert_budget_available(
            max_steps=2,
            max_model_calls=4,
            max_tool_calls=4,
            max_active_elapsed_ms=1000,
            check_tool_calls=False,
        )
        with pytest.raises(PersistentBudgetExceededError, match="工具调用"):
            store.assert_budget_available(
                max_steps=2,
                max_model_calls=4,
                max_tool_calls=4,
                max_active_elapsed_ms=1000,
            )
    finally:
        resumed.close()


def test_uncertain_dispatch_consumes_call_budget_across_restarts(tmp_path) -> None:
    db_path = tmp_path / "uncertain-budget.sqlite"
    first = sqlite3.connect(db_path)
    first.row_factory = sqlite3.Row
    _init_runtime_schema(first)
    store = RuntimeStore(first, "task-v6")
    prepared = store.prepare_model_request(
        call_id="uncertain",
        step_id="step-1",
        payload={
            "messages": [{"role": "user", "content": "ORIGINAL"}],
            "tool_schemas": [],
            "provider_id": "fake:model",
            "parameters": {"thinking": False},
            "prompt_version": "test-v1",
        },
        max_steps=1,
    )
    assert prepared.descriptor["messages"][0]["content"] == "ORIGINAL"
    first_dispatch = store.reserve_model_dispatch(
        call_id="uncertain",
        step_id="step-1",
        provider_id="fake:model",
        max_model_calls=1,
    )
    assert first_dispatch
    first.close()

    resumed = sqlite3.connect(db_path)
    resumed.row_factory = sqlite3.Row
    try:
        resumed_store = RuntimeStore(resumed, "task-v6")
        replay = resumed_store.prepare_model_request(
            call_id="uncertain",
            step_id="step-1",
            payload={
                "messages": [{"role": "user", "content": "CHANGED"}],
                "tool_schemas": [],
                "provider_id": "other:model",
                "parameters": {"thinking": True},
                "prompt_version": "test-v2",
            },
            max_steps=1,
        )
        assert replay.uncertain_replay is True
        assert replay.descriptor["messages"][0]["content"] == "ORIGINAL"
        assert replay.descriptor["provider_id"] == "fake:model"
        with pytest.raises(PersistentBudgetExceededError, match="模型调用"):
            resumed_store.reserve_model_dispatch(
                call_id="uncertain",
                step_id="step-1",
                provider_id="fake:model",
                max_model_calls=1,
            )
        usage = resumed_store.get_budget_usage()
        assert usage["model_call_count"] == 1
        assert usage["usage_unknown_count"] == 1
    finally:
        resumed.close()


def test_response_commit_is_idempotent_and_requires_reserved_dispatch(runtime_conn) -> None:
    store = RuntimeStore(runtime_conn, "task-v6")
    store.prepare_model_request(
        call_id="model-idempotent",
        step_id="step-idempotent",
        payload={
            "messages": [{"role": "user", "content": "same"}],
            "tool_schemas": [],
            "provider_id": "fake:model",
            "parameters": {},
            "prompt_version": "test-v1",
        },
        max_steps=2,
    )
    dispatch_id = store.reserve_model_dispatch(
        call_id="model-idempotent",
        step_id="step-idempotent",
        provider_id="fake:model",
        max_model_calls=2,
    )
    payload = {"content": "ok", "usage": {"input_tokens": 3, "output_tokens": 2}}
    first = store.commit_model_response(
        call_id="model-idempotent",
        step_id="step-idempotent",
        payload=payload,
        elapsed_ms=5,
        attempt_count=1,
        successful_dispatch_id=dispatch_id,
    )
    second = store.commit_model_response(
        call_id="model-idempotent",
        step_id="step-idempotent",
        payload={"content": "different", "usage": {"input_tokens": 99}},
        elapsed_ms=99,
        attempt_count=4,
        successful_dispatch_id=dispatch_id,
    )
    assert first == second == payload
    usage = store.get_budget_usage()
    assert usage["model_call_count"] == 1
    assert usage["input_tokens"] == 3
    assert usage["output_tokens"] == 2
    assert usage["usage_unknown_count"] == 0

    store.prepare_model_request(
        call_id="missing-dispatch",
        step_id="step-2",
        payload={
            "messages": [],
            "tool_schemas": [],
            "provider_id": "fake:model",
            "parameters": {},
            "prompt_version": "test-v1",
        },
        max_steps=3,
    )
    with pytest.raises(IncompatibleModelRequestError, match="缺少成功派发标识"):
        store.commit_model_response(
            call_id="missing-dispatch",
            step_id="step-2",
            payload={"content": "unsafe", "usage": {}},
            elapsed_ms=1,
            attempt_count=1,
        )


def test_takeover_charges_unclosed_active_segment_through_previous_lease(
    runtime_conn: sqlite3.Connection,
) -> None:
    store = RuntimeStore(runtime_conn, "task-v6")
    store.record_execution_started(queued_since=None)
    runtime_conn.execute(
        """UPDATE ai_runtime_budget_usage
           SET active_started_at=datetime('now', '-8 seconds')
           WHERE task_id='task-v6'"""
    )
    runtime_conn.commit()

    lease_until = runtime_conn.execute("SELECT datetime('now', '-3 seconds')").fetchone()[0]
    store.record_execution_started(
        queued_since=None,
        previous_active_until=str(lease_until),
    )

    persisted_ms = runtime_conn.execute(
        """SELECT active_elapsed_ms FROM ai_runtime_budget_usage
           WHERE task_id='task-v6'"""
    ).fetchone()[0]
    assert 4900 <= persisted_ms <= 5100


def test_validated_section_is_reused_and_invalidation_is_streamable(
    runtime_conn: sqlite3.Connection,
) -> None:
    store = RuntimeStore(runtime_conn, "task-v6")
    first = store.upsert_report_section(
        section_id="opening",
        section_order=0,
        status="validated",
        context_key="context-a",
        plan_version="plan-v1",
        writer_version="writer-v1",
        validator_version="validator-v1",
        source_kind="model",
        section={"heading": "开场", "prose": "已审核正文"},
        audit={"status": "pass"},
        usage={"total_tokens": 20},
        attempt_count=1,
    )
    reused = store.upsert_report_section(
        section_id="opening",
        section_order=0,
        status="validated",
        context_key="context-a",
        plan_version="plan-v1",
        writer_version="writer-v1",
        validator_version="validator-v1",
        source_kind="model",
        section={"heading": "不应覆盖", "prose": "不应重写"},
        audit={},
        usage={},
        attempt_count=2,
    )
    assert reused["section_version"] == first["section_version"] == 1
    assert reused["section"]["heading"] == "开场"

    assert store.invalidate_report_sections(reason="final_audit_failed") == 1
    changes = store.list_report_section_changes(after_sequence=0)
    assert [item["status"] for item in changes] == ["invalidated", "invalidated"]
    assert [item["section_version"] for item in changes] == [2, 2]
    assert store.report_section_watermark() == changes[-1]["sequence"]
    assert store.list_report_sections(validated_only=True) == []
