from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from backend.services import ai_task_service

pytestmark = pytest.mark.unit


class SyncThread:
    def __init__(
        self,
        *,
        target: Callable[..., None],
        args: tuple[Any, ...] = (),
        daemon: bool | None = None,
        name: str | None = None,
    ):
        self.target = target
        self.args = args
        self.daemon = daemon
        self.name = name

    def start(self) -> None:
        self.target(*self.args)


@pytest.fixture
def ai_task_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "ai_tasks.db"
    conn = sqlite3.connect(db_path)
    try:
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
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE ai_task_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                stage TEXT NOT NULL,
                message TEXT NOT NULL DEFAULT '',
                payload_json TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
            CREATE TABLE ai_agent_session_inbox (
                inbox_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                session_id INTEGER,
                input_type TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                consumed_at TEXT
            );
            """
        )
    finally:
        conn.close()

    def get_test_db(readonly: bool = False) -> sqlite3.Connection:
        del readonly
        test_conn = sqlite3.connect(db_path)
        test_conn.row_factory = sqlite3.Row
        return test_conn

    monkeypatch.setattr(ai_task_service, "get_db", get_test_db)
    return db_path


def test_mark_task_done_keeps_cancelled_task_cancelled(ai_task_db: Path):
    del ai_task_db
    task = ai_task_service.create_task(
        task_type="ai_report_weekly",
        stage="checking_cache",
        message="正在检查缓存",
        request={"report_type": "weekly"},
    )

    ai_task_service.cancel_task(task["task_id"])
    ai_task_service.mark_task_done(
        task["task_id"],
        stage="done",
        message="任务已完成",
        result={"answer": "late result"},
    )

    stored = ai_task_service.get_task(task["task_id"])
    events = ai_task_service.get_task_events(task["task_id"])

    assert stored is not None
    assert stored["status"] == "cancelled"
    assert stored["stage"] == "cancelled"
    assert stored["message"] == "任务已取消"
    assert stored["result"] is None
    assert events is not None
    assert [event["event_type"] for event in events[0]] == [
        "stage_started",
        "cancellation_requested",
        "cancellation_completed",
    ]


def test_handler_exception_marks_task_error(
    ai_task_db: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    del ai_task_db
    monkeypatch.setattr(ai_task_service.threading, "Thread", SyncThread)

    def failing_handler(task_id: str, request: dict[str, Any]) -> None:
        assert task_id
        assert request == {"question": "今年听了什么？"}
        raise RuntimeError("boom")

    task = ai_task_service.create_task(
        task_type="ai_chat_agent",
        stage="planning_tools",
        message="正在规划工具",
        request={"question": "今年听了什么？"},
        handler=failing_handler,
    )

    stored = ai_task_service.get_task(task["task_id"])
    events = ai_task_service.get_task_events(task["task_id"])

    assert stored is not None
    assert stored["status"] == "error"
    assert stored["stage"] == "error"
    assert stored["progress_pct"] == 1.0
    assert stored["error"] == "boom"
    assert "boom" in stored["message"]
    assert events is not None
    assert events[0][-1]["event_type"] == "stage_failed"
    assert events[0][-1]["stage"] == "error"
    assert events[0][-1]["payload"] == {"error": "boom"}


def test_startup_recovery_resumes_queued_agent_task(
    ai_task_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del ai_task_db
    from backend.core import config as runtime_config
    from backend.services import ai_agent_v2_service

    monkeypatch.setattr(runtime_config, "AI_AGENT_RUNTIME", "v2")
    monkeypatch.setattr(ai_task_service.threading, "Thread", SyncThread)
    observed: list[tuple[str, dict[str, Any], bool]] = []

    def fake_resume(task_id: str, request: dict[str, Any], *, resume: bool = False) -> None:
        observed.append((task_id, request, resume))

    monkeypatch.setattr(ai_agent_v2_service, "run_chat_agent_task_v2", fake_resume)
    task = ai_task_service.create_task(
        task_type="ai_chat_agent",
        stage="queued",
        message="等待 Agent",
        request={"question": "恢复这个问题"},
    )

    recovered = ai_task_service.recover_interrupted_agent_tasks()

    assert recovered == 1
    assert observed == [(task["task_id"], {"question": "恢复这个问题"}, True)]


def test_recovery_worker_waits_for_previous_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim_attempts: list[str] = []
    sleeps: list[float] = []
    handled: list[tuple[str, dict[str, Any]]] = []

    class DummyConnection:
        def close(self) -> None:
            return None

    class LeaseRepository:
        supports_worker_leases = False
        claimed_lease_generation = 2

        def __init__(self, conn: DummyConnection):
            del conn

        def get_run(self, task_id: str) -> dict[str, Any]:
            return {"task_id": task_id, "status": "running", "runtime_version": "v5"}

        def claim_run(self, task_id: str, *, lease_owner: str) -> bool:
            del task_id
            claim_attempts.append(lease_owner)
            return len(claim_attempts) >= 2

        def release_run(self, task_id: str, *, lease_owner: str) -> bool:
            del task_id, lease_owner
            return True

    clock = iter((0.0, 0.0, 0.5))
    monkeypatch.setattr(ai_task_service, "get_db", lambda readonly=False: DummyConnection())
    monkeypatch.setattr(ai_task_service, "AiTaskRepository", LeaseRepository)
    monkeypatch.setattr(ai_task_service.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(ai_task_service.time, "sleep", sleeps.append)

    ai_task_service._run_handler_safely(
        "recover-me",
        {"question": "继续"},
        lambda task_id, request: handled.append((task_id, request)),
        wait_for_lease_seconds=2,
    )

    assert len(claim_attempts) == 2
    assert sleeps == [1.0]
    assert handled == [("recover-me", {"question": "继续"})]


def test_v6_worker_exits_if_task_is_removed_after_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handled: list[str] = []
    reset_tokens: list[str] = []

    class DummyConnection:
        def close(self) -> None:
            return None

    class LeaseRepository:
        supports_worker_leases = False
        claimed_lease_generation = 1

        def __init__(self, conn: DummyConnection):
            del conn

        def get_run(self, task_id: str) -> dict[str, Any]:
            return {
                "task_id": task_id,
                "status": "queued",
                "runtime_version": "v6",
            }

        def claim_run(self, task_id: str, *, lease_owner: str) -> bool:
            del task_id, lease_owner
            return True

    class MissingRuntimeStore:
        def __init__(self, conn: DummyConnection, task_id: str):
            del conn, task_id

        def record_execution_started(self, **kwargs: Any) -> None:
            del kwargs
            raise KeyError("removed")

    monkeypatch.setattr(ai_task_service, "get_db", lambda readonly=False: DummyConnection())
    monkeypatch.setattr(ai_task_service, "AiTaskRepository", LeaseRepository)
    monkeypatch.setattr(ai_task_service, "RuntimeStore", MissingRuntimeStore)
    monkeypatch.setattr(ai_task_service, "bind_execution_identity", lambda identity: "token")
    monkeypatch.setattr(
        ai_task_service,
        "reset_execution_identity",
        reset_tokens.append,
    )

    ai_task_service._run_handler_safely(
        "removed-after-claim",
        {},
        lambda task_id, request: handled.append(task_id),
    )

    assert handled == []
    assert reset_tokens == ["token"]


def test_clarification_input_queues_and_resumes_agent(
    ai_task_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del ai_task_db
    from backend.services import ai_agent_v2_service

    monkeypatch.setattr(ai_task_service.threading, "Thread", SyncThread)
    observed: list[tuple[str, dict[str, Any], bool]] = []

    def fake_resume(task_id: str, request: dict[str, Any], *, resume: bool = False) -> None:
        observed.append((task_id, request, resume))

    monkeypatch.setattr(ai_agent_v2_service, "run_chat_agent_task_v2", fake_resume)
    task = ai_task_service.create_task(
        task_type="ai_chat_agent",
        stage="queued",
        message="等待 Agent",
        request={"question": "继续分析那个艺人", "session_id": 9},
    )
    conn = ai_task_service.get_db(readonly=False)
    conn.execute(
        "UPDATE ai_task_runs SET status='awaiting_input', stage='awaiting_input' WHERE task_id=?",
        (task["task_id"],),
    )
    conn.commit()
    conn.close()

    result = ai_task_service.enqueue_agent_input(
        task["task_id"],
        action="followup",
        content="Artist A",
    )

    assert result is not None
    assert result["accepted"] is True
    assert observed == [
        (
            task["task_id"],
            {"question": "继续分析那个艺人", "session_id": 9},
            True,
        )
    ]
    stored = ai_task_service.get_task(task["task_id"])
    assert stored is not None
    assert stored["status"] == "queued"
    conn = ai_task_service.get_db(readonly=True)
    inbox = conn.execute(
        "SELECT input_type, content, status FROM ai_agent_session_inbox WHERE task_id=?",
        (task["task_id"],),
    ).fetchone()
    conn.close()
    assert dict(inbox) == {
        "input_type": "followup",
        "content": "Artist A",
        "status": "pending",
    }


def test_handler_exception_does_not_overwrite_cancelled_task(
    ai_task_db: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    del ai_task_db
    monkeypatch.setattr(ai_task_service.threading, "Thread", SyncThread)

    def cancelled_handler(task_id: str, request: dict[str, Any]) -> None:
        assert request == {"report_type": "weekly"}
        ai_task_service.cancel_task(task_id)
        raise RuntimeError("late boom")

    task = ai_task_service.create_task(
        task_type="ai_report_weekly",
        stage="checking_cache",
        message="正在检查缓存",
        request={"report_type": "weekly"},
        handler=cancelled_handler,
    )

    stored = ai_task_service.get_task(task["task_id"])
    events = ai_task_service.get_task_events(task["task_id"])

    assert stored is not None
    assert stored["status"] == "cancelled"
    assert stored["stage"] == "cancelled"
    assert stored["message"] == "任务已取消"
    assert stored["error"] is None
    assert events is not None
    assert [event["event_type"] for event in events[0]] == [
        "stage_started",
        "cancellation_requested",
        "cancellation_completed",
    ]


def test_start_chat_agent_uses_v2_by_default(monkeypatch: pytest.MonkeyPatch):
    import backend.core.config as runtime_config
    from backend.services import ai_agent_v2_service

    captured: dict[str, Any] = {}

    def fake_v2_handler(task_id: str, request: dict[str, Any]) -> None:
        del task_id, request

    def fake_create_task(**kwargs):
        captured.update(kwargs)
        return {"task_id": "v2", "status": "queued", "stage": kwargs["stage"]}

    monkeypatch.setattr(runtime_config, "AI_AGENT_RUNTIME", "v2")
    monkeypatch.setattr(ai_agent_v2_service, "run_chat_agent_task_v2", fake_v2_handler)
    monkeypatch.setattr(ai_task_service, "create_task", fake_create_task)

    result = ai_task_service.start_chat_agent_task({"question": "test"})

    assert result["task_id"] == "v2"
    assert captured["handler"] is fake_v2_handler
    assert captured["message"] == "准备启动 Agent Chat V2"


def test_start_chat_agent_keeps_explicit_legacy_rollback(monkeypatch: pytest.MonkeyPatch):
    import backend.core.config as runtime_config
    from backend.services import ai_agent_service

    captured: dict[str, Any] = {}

    def fake_create_task(**kwargs):
        captured.update(kwargs)
        return {"task_id": "legacy", "status": "queued", "stage": kwargs["stage"]}

    monkeypatch.setattr(runtime_config, "AI_AGENT_RUNTIME", "legacy")
    monkeypatch.setattr(ai_task_service, "create_task", fake_create_task)

    ai_task_service.start_chat_agent_task({"question": "test"})

    assert captured["handler"] is ai_agent_service.run_chat_agent_task
    assert "旧运行时" in captured["message"]
