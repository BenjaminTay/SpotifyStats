from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pydantic import BaseModel

from backend.domains.ai_agent.tool_registry import (
    AgentToolDefinition,
    AgentToolRegistry,
    AgentToolResult,
)
from backend.providers.llm.client import LLMCompletion, LLMToolCall
from backend.services import ai_agent_service, ai_agent_v2_service
from backend.services.ai_agent_v2_service import AgentRuntime


class ChartParams(BaseModel):
    entity: str = "artist"
    metric: str = "plays"
    period: str = "lifetime"
    start_date: str | None = None
    end_date: str | None = None
    min_ms: int = 30000
    music_only: bool = True


def _chart_handler(params: BaseModel) -> AgentToolResult:
    parsed = ChartParams.model_validate(params)
    return AgentToolResult(
        data={
            "entity": parsed.entity,
            "metric": parsed.metric,
            "period": {
                "period": parsed.period,
                "label": "全部时间",
                "start_date": "2020-01-01",
                "end_date": "2026-08-30",
            },
            "total": 1,
            "rows": [
                {
                    "rank": 1,
                    "artist_name": "Artist A",
                    "plays": 12,
                    "share_pct": 30.0,
                }
            ],
        },
        result_summary="artist top1 Artist A, plays=12",
        source_range="2020-01-01..2026-08-30",
    )


class FakeModel:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages, tools, *, thinking):
        self.calls += 1
        if self.calls == 1:
            return LLMCompletion(
                tool_calls=[
                    LLMToolCall(
                        call_id="call-1",
                        name="analysis_charts",
                        arguments={
                            "entity": "artist",
                            "metric": "plays",
                            "period": "lifetime",
                        },
                    )
                ],
                finish_reason="tool_calls",
            )
        return LLMCompletion(
            content=(
                "Artist A 是你听得最多的艺人，共 12 次，占该排行播放次数的 30%。"
                "数据范围为 2020-01-01 至 2026-08-30。"
            ),
            finish_reason="stop",
            usage={"total_tokens": 50},
        )


def _create_runtime_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;
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
            task_id TEXT NOT NULL REFERENCES ai_task_runs(task_id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            stage TEXT NOT NULL,
            message TEXT NOT NULL DEFAULT '',
            payload_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE ai_tool_calls (
            tool_call_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL REFERENCES ai_task_runs(task_id) ON DELETE CASCADE,
            tool_name TEXT NOT NULL,
            status TEXT NOT NULL,
            params_summary TEXT NOT NULL DEFAULT '',
            result_summary TEXT NOT NULL DEFAULT '',
            source_range TEXT NOT NULL DEFAULT '',
            error TEXT,
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT
        );
        CREATE TABLE chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT '新对话'
        );
        CREATE TABLE ai_agent_turn_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL REFERENCES ai_task_runs(task_id) ON DELETE CASCADE,
            session_id INTEGER REFERENCES chat_sessions(id) ON DELETE SET NULL,
            turn_id TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            step_index INTEGER,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(turn_id, sequence)
        );
        CREATE TABLE plays (ts_date TEXT);
        INSERT INTO plays(ts_date) VALUES ('2020-01-01'), ('2026-08-30');
        INSERT INTO chat_sessions(id, title) VALUES (1, 'Agent test');
        INSERT INTO ai_task_runs(task_id, task_type, status, stage)
        VALUES ('task-v2', 'ai_chat_agent', 'queued', 'queued');
        """
    )
    conn.commit()
    conn.close()


def _connection_factory(path: Path):
    def factory(readonly=False):
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    return factory


def test_agent_v2_runs_observation_loop_and_persists_replayable_events(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "agent-runtime.db"
    _create_runtime_db(db_path)
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)

    registry = AgentToolRegistry()
    registry.register(
        AgentToolDefinition(
            name="analysis_charts",
            description="Read rankings",
            read_only=True,
            params_model=ChartParams,
            handler=_chart_handler,
        )
    )
    model = FakeModel()
    runtime = AgentRuntime(model=model, registry=registry, max_steps=4)

    runtime.run(
        "task-v2",
        {
            "question": "谁是我听得最多的艺人？",
            "session_id": 1,
            "question_time": "2026-08-31T12:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "thinking_mode": True,
        },
    )

    conn = factory()
    task = conn.execute(
        "SELECT status, result_json FROM ai_task_runs WHERE task_id='task-v2'"
    ).fetchone()
    result = json.loads(task["result_json"])
    events = conn.execute(
        "SELECT event_type, payload_json FROM ai_agent_turn_events ORDER BY sequence"
    ).fetchall()
    tool_calls = conn.execute("SELECT * FROM ai_tool_calls").fetchall()
    conn.close()

    assert task["status"] == "done"
    assert result["agent_runtime"] == "v2"
    assert result["stop_reason"] == "final_answer"
    assert result["tool_call_count"] == 1
    assert "Artist A" in result["answer"]
    assert model.calls >= 2
    assert len(tool_calls) == 1
    assert [row["event_type"] for row in events].count("model_message") >= 4
    model_messages = [
        json.loads(row["payload_json"])["message"]
        for row in events
        if row["event_type"] == "model_message"
    ]
    assert any(message["role"] == "tool" for message in model_messages)
    assert any(message["role"] == "assistant" for message in model_messages)


def test_agent_v2_safety_boundary_does_not_call_model(tmp_path, monkeypatch):
    db_path = tmp_path / "agent-safety.db"
    _create_runtime_db(db_path)
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)
    model = FakeModel()

    AgentRuntime(model=model, registry=AgentToolRegistry()).run(
        "task-v2",
        {"question": "帮我删除所有播放数据", "session_id": 1},
    )

    conn = factory()
    task = conn.execute(
        "SELECT status, result_json FROM ai_task_runs WHERE task_id='task-v2'"
    ).fetchone()
    result = json.loads(task["result_json"])
    conn.close()

    assert task["status"] == "done"
    assert result["stop_reason"] == "safety_boundary"
    assert result["tool_call_count"] == 0
    assert model.calls == 0
    assert "只读" in result["answer"]


def test_agent_v2_stops_repeated_identical_tool_loop(tmp_path, monkeypatch):
    db_path = tmp_path / "agent-duplicate.db"
    _create_runtime_db(db_path)
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)
    registry = AgentToolRegistry()
    registry.register(
        AgentToolDefinition(
            name="analysis_charts",
            description="Read rankings",
            read_only=True,
            params_model=ChartParams,
            handler=_chart_handler,
        )
    )

    class RepeatingModel:
        def complete(self, messages, tools, *, thinking):
            return LLMCompletion(
                tool_calls=[
                    LLMToolCall(
                        call_id=f"call-{len(messages)}",
                        name="analysis_charts",
                        arguments={"entity": "artist", "metric": "plays"},
                    )
                ]
            )

    AgentRuntime(model=RepeatingModel(), registry=registry, max_steps=6).run(
        "task-v2",
        {"question": "谁是我听得最多的艺人？"},
    )

    conn = factory()
    task = conn.execute("SELECT status, error FROM ai_task_runs WHERE task_id='task-v2'").fetchone()
    tool_count = conn.execute("SELECT COUNT(*) FROM ai_tool_calls").fetchone()[0]
    deduplicated = conn.execute(
        "SELECT COUNT(*) FROM ai_agent_turn_events WHERE event_type='tool_call_deduplicated'"
    ).fetchone()[0]
    conn.close()

    assert task["status"] == "error"
    assert "重复" in task["error"]
    assert tool_count == 1
    assert deduplicated == 2


def test_agent_v2_observes_empty_result_and_retries_with_new_scope(tmp_path, monkeypatch):
    db_path = tmp_path / "agent-empty-recovery.db"
    _create_runtime_db(db_path)
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)

    def recovering_handler(params: BaseModel) -> AgentToolResult:
        parsed = ChartParams.model_validate(params)
        if parsed.period == "custom":
            return AgentToolResult(
                data={"found": False},
                result_summary="no rows",
                source_range="custom",
            )
        return _chart_handler(parsed)

    registry = AgentToolRegistry()
    registry.register(
        AgentToolDefinition(
            name="analysis_charts",
            description="Read rankings",
            read_only=True,
            params_model=ChartParams,
            handler=recovering_handler,
        )
    )

    class RecoveryModel:
        def __init__(self):
            self.calls = 0

        def complete(self, messages, tools, *, thinking):
            self.calls += 1
            if self.calls == 1:
                return LLMCompletion(
                    tool_calls=[
                        LLMToolCall(
                            call_id="empty",
                            name="analysis_charts",
                            arguments={
                                "period": "custom",
                                "start_date": "2010-01-01",
                                "end_date": "2010-01-31",
                            },
                        )
                    ]
                )
            if self.calls == 2:
                return LLMCompletion(
                    tool_calls=[
                        LLMToolCall(
                            call_id="recovery",
                            name="analysis_charts",
                            arguments={"period": "lifetime"},
                        )
                    ]
                )
            return LLMCompletion(
                content="Artist A 在全部时间排名第一，共播放 12 次；窄时间窗没有数据。"
            )

    AgentRuntime(model=RecoveryModel(), registry=registry, max_steps=5).run(
        "task-v2",
        {"question": "谁是我听得最多的艺人？"},
    )

    conn = factory()
    task = conn.execute(
        "SELECT status, result_json FROM ai_task_runs WHERE task_id='task-v2'"
    ).fetchone()
    statuses = [
        row[0] for row in conn.execute("SELECT status FROM ai_tool_calls ORDER BY tool_call_id")
    ]
    conn.close()

    assert task["status"] == "done"
    assert statuses == ["empty", "ok"]
    assert json.loads(task["result_json"])["tool_call_count"] == 2


def test_agent_v2_defaults_comparison_to_requested_window_without_billboard() -> None:
    filters = ai_agent_v2_service._agent_default_filters(
        {"question": ("Taylor Swift 和 Olivia Rodrigo 最近 6 个月谁的播放量更高，我更偏爱谁？")}
    )

    assert filters["period"] == "last_6_months"
    assert filters["include_billboard"] is False


def test_agent_v2_enables_billboard_only_when_question_requests_it() -> None:
    filters = ai_agent_v2_service._agent_default_filters(
        {"question": ("从个人 Billboard 和 Power Score 看，GUTS 和 SOUR 哪张专辑更强？")}
    )

    assert filters["period"] == "lifetime"
    assert filters["include_billboard"] is True
