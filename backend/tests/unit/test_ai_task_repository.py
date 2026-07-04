from __future__ import annotations

import sqlite3

import pytest

pytestmark = pytest.mark.unit


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
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
    return conn


def test_repository_creates_run_event_and_tool_call():
    from backend.domains.ai_tasks.repository import AiTaskRepository

    conn = make_conn()
    repo = AiTaskRepository(conn)

    repo.create_run(
        task_id="task-1",
        task_type="ai_chat_agent",
        status="queued",
        stage="planning_tools",
        message="准备分析问题",
        request={"question": "今年我听得最多的艺人是谁？"},
    )
    repo.add_event(
        task_id="task-1",
        event_type="stage_started",
        stage="planning_tools",
        message="正在规划数据查询",
        payload={"round": 1, "checks": ["本地数据"]},
    )
    repo.add_tool_call(
        task_id="task-1",
        tool_name="analysis_charts",
        status="done",
        params_summary="2026 artist plays top 10",
        result_summary="Top artist is Artist A with 12 plays",
        source_range="2026-01-01 to 2026-12-31",
    )
    repo.update_run(
        task_id="task-1",
        status="done",
        stage="done",
        progress_pct=1.0,
        message="分析完成",
        result={"answer": "Artist A", "sources": ["analysis_charts"]},
    )

    run = repo.get_run("task-1")
    events = repo.list_events("task-1")
    tools = repo.list_tool_calls("task-1")
    stored = conn.execute(
        "SELECT request_json, result_json FROM ai_task_runs WHERE task_id = ?",
        ("task-1",),
    ).fetchone()

    assert run is not None
    assert run["status"] == "done"
    assert run["request"] == {"question": "今年我听得最多的艺人是谁？"}
    assert run["result"]["answer"] == "Artist A"
    assert run["result"]["sources"] == ["analysis_charts"]
    assert events[0]["payload"] == {"round": 1, "checks": ["本地数据"]}
    assert tools[0]["tool_name"] == "analysis_charts"
    assert tools[0]["source_range"] == "2026-01-01 to 2026-12-31"
    assert "今年我听得最多" in stored["request_json"]
    assert "\\u4eca" not in stored["request_json"]


def test_repository_skips_conditional_tool_call_after_terminal_status():
    from backend.domains.ai_tasks.repository import AiTaskRepository

    conn = make_conn()
    repo = AiTaskRepository(conn)

    repo.create_run(
        task_id="task-done",
        task_type="ai_chat_agent",
        status="done",
        stage="done",
        message="完成",
    )
    inserted = repo.add_tool_call_if_not_terminal(
        task_id="task-done",
        tool_name="analysis_charts",
        status="done",
        params_summary="late trace",
    )

    assert inserted is False
    assert repo.list_tool_calls("task-done") == []


def test_repository_writes_conditional_tool_call_for_active_task():
    from backend.domains.ai_tasks.repository import AiTaskRepository

    conn = make_conn()
    repo = AiTaskRepository(conn)

    repo.create_run(
        task_id="task-running",
        task_type="ai_chat_agent",
        status="running",
        stage="collecting",
        message="分析中",
    )
    inserted = repo.add_tool_call_if_not_terminal(
        task_id="task-running",
        tool_name="analysis_charts",
        status="done",
        params_summary="active trace",
    )

    assert inserted is True
    assert repo.list_tool_calls("task-running")[0]["params_summary"] == "active trace"
