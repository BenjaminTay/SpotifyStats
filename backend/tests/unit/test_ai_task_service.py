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
    ):
        self.target = target
        self.args = args
        self.daemon = daemon

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
        "stage_completed",
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
        "stage_completed",
    ]
