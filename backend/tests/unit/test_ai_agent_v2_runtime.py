from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from backend.domains.agent_runtime.event_log import AgentEventLog
from backend.domains.agent_runtime.observation import compact_observation
from backend.domains.agent_runtime.tool_selector import (
    select_agent_profile,
    tool_schemas_for_profile,
)
from backend.domains.ai_agent.tool_registry import (
    AgentToolDefinition,
    AgentToolRegistry,
    AgentToolResult,
    get_default_registry,
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
    shadow_payloads = [
        json.loads(row["payload_json"])
        for row in events
        if row["event_type"] == "context_projection_shadow"
    ]
    assert len(shadow_payloads) == 1
    assert shadow_payloads[0]["source"] == "memory"
    assert shadow_payloads[0]["matches"] is True


def test_agent_v2_replaces_repeated_unsupported_numbers_with_grounded_fallback(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "agent-grounded-fallback.db"
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

    class UnsupportedNumberModel(FakeModel):
        def complete(self, messages, tools, *, thinking):
            if self.calls == 0:
                return super().complete(messages, tools, thinking=thinking)
            self.calls += 1
            return LLMCompletion(
                content=(
                    "Artist A 共播放 12 次，但我还推断你听了 250 首歌。"
                    "数据范围为 2020-01-01 至 2026-08-30。"
                ),
                finish_reason="stop",
            )

    model = UnsupportedNumberModel()
    AgentRuntime(model=model, registry=registry, max_steps=4).run(
        "task-v2",
        {
            "question": "谁是我听得最多的艺人？",
            "question_time": "2026-08-31T12:00:00+08:00",
        },
    )

    conn = factory()
    task = conn.execute(
        "SELECT status, result_json FROM ai_task_runs WHERE task_id='task-v2'"
    ).fetchone()
    result = json.loads(task["result_json"])
    conn.close()

    assert task["status"] == "done"
    assert result["grounded_fallback_used"] is True
    assert result["evidence_coverage"] == 1.0
    assert "250" not in result["answer"]
    assert result["claim_ledger"]["unsupported_literals"] == []


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


def test_agent_v2_clips_explicit_year_default_to_local_data_cutoff(monkeypatch) -> None:
    monkeypatch.setattr(
        ai_agent_v2_service,
        "_temporal_context",
        lambda request: {
            "today": "2026-08-31",
            "data_start_date": "2022-07-01",
            "data_end_date": "2026-08-21",
            "latest_play_date": "2026-08-21",
        },
    )
    request: dict[str, Any] = {"question": "2026年我听得最多的艺人是谁？"}

    filters = ai_agent_v2_service._agent_default_filters(request)

    assert filters["start_date"] == "2026-01-01"
    assert filters["end_date"] == "2026-08-21"
    interpretation = request["_temporal_guard"]["time_interpretation"]
    assert interpretation["requested_end_date"] == "2026-12-31"
    assert interpretation["effective_end_date"] == "2026-08-21"
    assert interpretation["coverage_clipped"] is True


def test_agent_v2_enables_billboard_only_when_question_requests_it() -> None:
    filters = ai_agent_v2_service._agent_default_filters(
        {"question": ("从个人 Billboard 和 Power Score 看，GUTS 和 SOUR 哪张专辑更强？")}
    )

    assert filters["period"] == "lifetime"
    assert filters["include_billboard"] is True


def test_agent_v2_does_not_enable_billboard_for_generic_ranking_word() -> None:
    filters = ai_agent_v2_service._agent_default_filters(
        {"question": "Taylor Swift 和 Olivia Rodrigo 的本地播放排名谁更高？"}
    )

    assert filters["include_billboard"] is False


def test_agent_profile_exposes_only_family_specific_tool_schemas() -> None:
    registry = get_default_registry()
    ranking_context = ai_agent_service._question_context({"question": "我今年听得最多的艺人是谁？"})
    comparison_context = ai_agent_service._question_context(
        {"question": "Taylor Swift 和 Olivia Rodrigo 哪位艺人我更喜欢？"}
    )

    ranking = select_agent_profile(ranking_context, registry)
    comparison = select_agent_profile(comparison_context, registry)

    assert ranking.family == "simple_ranking"
    assert 3 <= len(ranking.tool_names) <= 6
    assert "analysis_charts" in ranking.tool_names
    assert "web_search" not in ranking.tool_names
    assert comparison.family == "preference_comparison"
    assert 3 <= len(comparison.tool_names) <= 6
    assert comparison.tool_names[0] == "compare_entities"
    assert "billboard_entity_detail" not in comparison.tool_names
    all_schema_chars = len(json.dumps(registry.list_tools(), ensure_ascii=False))
    selected_schema_chars = len(
        json.dumps(tool_schemas_for_profile(registry, ranking), ensure_ascii=False)
    )
    assert selected_schema_chars < all_schema_chars * 0.6
    comparison_schemas = tool_schemas_for_profile(registry, comparison)
    compare_schema = next(item for item in comparison_schemas if item["name"] == "compare_entities")
    assert "ROUTING_METADATA=" in compare_schema["description"]
    assert '"best_for"' in compare_schema["description"]
    assert '"parallel_safe":true' in compare_schema["description"]
    assert "我今年" not in ai_agent_v2_service._system_prompt()


def test_agent_profile_exposes_billboard_tool_only_for_explicit_billboard() -> None:
    registry = get_default_registry()
    ordinary = ai_agent_service._question_context(
        {"question": "Taylor Swift 和 Olivia Rodrigo 的本地播放次数谁更多？"}
    )
    billboard = ai_agent_service._question_context(
        {"question": "比较 Taylor Swift 和 Olivia Rodrigo 的个人 Billboard 在榜周"}
    )

    ordinary_profile = select_agent_profile(ordinary, registry)
    billboard_profile = select_agent_profile(billboard, registry)

    assert ordinary_profile.tool_names[0] == "compare_entities"
    assert "billboard_entity_detail" not in ordinary_profile.tool_names
    assert billboard_profile.tool_names[0] == "compare_entities"
    assert "billboard_entity_detail" in billboard_profile.tool_names


def test_agent_v2_records_runtime_metrics_and_patches_mechanical_obligations(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "agent-metrics.db"
    _create_runtime_db(db_path)
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)
    registry = AgentToolRegistry()

    def cached_chart_handler(params: BaseModel) -> AgentToolResult:
        result = _chart_handler(params)
        return AgentToolResult(
            data=result.data,
            result_summary=result.result_summary,
            source_range=result.source_range,
            cache_hit=True,
        )

    registry.register(
        AgentToolDefinition(
            name="analysis_charts",
            description="Read rankings",
            read_only=True,
            params_model=ChartParams,
            handler=cached_chart_handler,
        )
    )

    class MetricsModel:
        def __init__(self):
            self.calls = 0
            self.schema_counts: list[int] = []

        def complete(self, messages, tools, *, thinking):
            self.calls += 1
            self.schema_counts.append(len(tools))
            if self.calls == 1:
                return LLMCompletion(
                    tool_calls=[
                        LLMToolCall(
                            call_id="metrics-tool",
                            name="analysis_charts",
                            arguments={"entity": "artist", "metric": "plays"},
                        )
                    ],
                    usage={"prompt_tokens": 80, "completion_tokens": 10},
                )
            return LLMCompletion(
                content="Artist A 是你今年听得最多的艺人，共 12 次。",
                usage={"input_tokens": 100, "output_tokens": 20},
            )

    model = MetricsModel()
    AgentRuntime(model=model, registry=registry, max_steps=4).run(
        "task-v2",
        {
            "question": "我今年听得最多的艺人是谁？",
            "question_time": "2026-08-31T12:00:00+08:00",
            "timezone": "Asia/Shanghai",
        },
    )

    conn = factory()
    task = conn.execute(
        "SELECT status, result_json FROM ai_task_runs WHERE task_id='task-v2'"
    ).fetchone()
    result = json.loads(task["result_json"])
    turn_ended = conn.execute(
        "SELECT payload_json FROM ai_agent_turn_events "
        "WHERE event_type='turn_ended' ORDER BY sequence DESC LIMIT 1"
    ).fetchone()
    conn.close()

    metrics = result["runtime_metrics"]
    assert task["status"] == "done"
    assert model.calls == 2
    assert model.schema_counts == [1, 1]
    assert metrics["model_call_count"] == 2
    assert metrics["tool_call_count"] == 1
    assert metrics["cache_hit_count"] == 1
    assert metrics["tool_cache_hit_count"] == 1
    assert metrics["input_tokens"] == 180
    assert metrics["output_tokens"] == 30
    assert metrics["tool_result_bytes"] > 0
    assert "2026-08-30" in result["answer"]
    assert "修正回答" not in result["answer"]
    assert json.loads(turn_ended["payload_json"])["runtime_metrics"]["model_call_count"] == 2


def test_agent_event_log_redacts_credentials_but_keeps_usage(tmp_path) -> None:
    db_path = tmp_path / "agent-redaction.db"
    _create_runtime_db(db_path)
    conn = _connection_factory(db_path)()
    log = AgentEventLog(conn, task_id="task-v2", turn_id="redaction", session_id=None)

    log.append(
        "provider_debug",
        {
            "api_key": "sk-1234567890abcdef",  # pragma: allowlist secret
            "authorization": "Bearer very-secret-token",
            "usage": {"input_tokens": 12, "output_tokens": 3},
        },
    )
    payload = log.list_events()[0]["payload"]
    conn.close()

    assert payload["api_key"] == "[REDACTED]"
    assert payload["authorization"] == "[REDACTED]"
    assert payload["usage"] == {"input_tokens": 12, "output_tokens": 3}


def test_compact_observation_bounds_large_rows_without_invalid_json() -> None:
    observation = compact_observation(
        {"rows": [{"rank": index, "name": f"Artist {index}"} for index in range(50)]}
    )

    assert len(observation["rows"]) == 13
    assert observation["rows"][-1]["omitted_items"] == 38
    assert json.loads(json.dumps(observation, ensure_ascii=False)) == observation


def test_agent_executes_two_independent_readonly_tools_in_parallel_with_stable_order(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "agent-parallel.db"
    _create_runtime_db(db_path)
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)
    barrier = threading.Barrier(2)
    state = {"active": 0, "max_active": 0}
    lock = threading.Lock()

    def handler_for(label: str):
        def handler(params: BaseModel) -> AgentToolResult:
            del params
            with lock:
                state["active"] += 1
                state["max_active"] = max(state["max_active"], state["active"])
            barrier.wait(timeout=2)
            time.sleep(0.03)
            with lock:
                state["active"] -= 1
            return AgentToolResult(
                data={"found": True, "label": label},
                result_summary=label,
                source_range="lifetime",
            )

        return handler

    registry = AgentToolRegistry()
    for name in ("analysis_charts", "analysis_stats"):
        registry.register(
            AgentToolDefinition(
                name=name,
                description=name,
                read_only=True,
                params_model=ChartParams,
                handler=handler_for(name),
                supports_parallel=True,
            )
        )

    class ParallelModel:
        def __init__(self) -> None:
            self.calls = 0
            self.tool_order: list[str] = []

        def complete(self, messages, tools, *, thinking):
            del tools, thinking
            self.calls += 1
            if self.calls == 1:
                return LLMCompletion(
                    tool_calls=[
                        LLMToolCall(call_id="first", name="analysis_charts", arguments={}),
                        LLMToolCall(call_id="second", name="analysis_stats", arguments={}),
                    ]
                )
            self.tool_order = [
                str(item.get("name")) for item in messages if item.get("role") == "tool"
            ]
            return LLMCompletion(
                content=("两个只读统计工具均已返回结果。数据范围为 2020-01-01 至 2026-08-30。")
            )

    model = ParallelModel()
    AgentRuntime(model=model, registry=registry, max_steps=3).run(
        "task-v2",
        {"question": "我的播放排行和总体统计是什么？"},
    )

    conn = factory()
    events = conn.execute(
        "SELECT turn_id, step_index, event_type, payload_json "
        "FROM ai_agent_turn_events ORDER BY sequence"
    ).fetchall()
    event_types = [row["event_type"] for row in events]
    task = conn.execute(
        "SELECT status, error, result_json FROM ai_task_runs WHERE task_id='task-v2'"
    ).fetchone()
    conn.close()
    assert task["status"] == "done", task["error"]
    assert state["max_active"] == 2
    assert model.tool_order == ["analysis_charts", "analysis_stats"]
    assert "parallel_tool_batch_started" in event_types
    assert "parallel_tool_batch_ended" in event_types
    metrics = json.loads(task["result_json"])["runtime_metrics"]
    assert metrics["tool_call_count"] == 2
    assert metrics["tool_wall_elapsed_ms"] < metrics["tool_cumulative_elapsed_ms"]
    turn_id = str(events[0]["turn_id"])
    model_events = [
        json.loads(row["payload_json"])
        for row in events
        if row["event_type"] in {"model_request", "assistant_message"}
    ]
    assert model_events[0]["model_call_id"] == f"{turn_id}:step:1:model"
    assert model_events[1]["model_call_id"] == f"{turn_id}:step:1:model"
    tool_events = [
        json.loads(row["payload_json"]) for row in events if row["event_type"] == "tool_result"
    ]
    assert [item["tool_execution_id"] for item in tool_events] == [
        f"{turn_id}:step:1:tool:first",
        f"{turn_id}:step:1:tool:second",
    ]


def test_agent_consumes_session_inbox_before_next_model_step(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "agent-inbox.db"
    _create_runtime_db(db_path)
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)
    conn = factory()
    conn.execute(
        """INSERT INTO ai_agent_session_inbox
           (task_id, session_id, input_type, content)
           VALUES ('task-v2', 1, 'steer', '只看今年，不要全部时间')"""
    )
    conn.commit()
    conn.close()

    class InboxModel(FakeModel):
        def complete(self, messages, tools, *, thinking):
            assert any(
                "只看今年，不要全部时间" in str(item.get("content") or "") for item in messages
            )
            return super().complete(messages, tools, thinking=thinking)

    AgentRuntime(model=InboxModel(), registry=_chart_registry(), max_steps=4).run(
        "task-v2",
        {"question": "谁是我听得最多的艺人？", "session_id": 1},
    )
    conn = factory()
    inbox = conn.execute("SELECT status, consumed_at FROM ai_agent_session_inbox").fetchone()
    consumed_events = conn.execute(
        "SELECT COUNT(*) FROM ai_agent_turn_events WHERE event_type='session_input_consumed'"
    ).fetchone()[0]
    conn.close()
    assert inbox["status"] == "consumed"
    assert inbox["consumed_at"] is not None
    assert consumed_events == 1


def _chart_registry() -> AgentToolRegistry:
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
    return registry


def test_agent_resume_reuses_completed_tool_result_without_dispatch(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "agent-resume.db"
    _create_runtime_db(db_path)
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)
    conn = factory()
    conn.execute("UPDATE ai_task_runs SET status='running' WHERE task_id='task-v2'")
    log = AgentEventLog(
        conn,
        task_id="task-v2",
        turn_id="interrupted-turn",
        session_id=1,
    )
    log.append("turn_started", {})
    log.append_model_message({"role": "system", "content": "rules"}, origin="initial")
    log.append_model_message(
        {"role": "user", "content": "谁是第一名？"},
        origin="initial",
    )
    assistant = {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "completed-call",
                "type": "function",
                "function": {
                    "name": "analysis_charts",
                    "arguments": json.dumps({"entity": "artist", "metric": "plays"}),
                },
            }
        ],
    }
    log.append("step_started", {}, step_index=1)
    log.append_model_message(assistant, origin="model_response", step_index=1)
    params = {"entity": "artist", "metric": "plays"}
    log.append(
        "tool_call",
        {"call_id": "completed-call", "tool_name": "analysis_charts", "params": params},
        step_index=1,
    )
    log.append(
        "tool_result",
        {
            "call_id": "completed-call",
            "tool_name": "analysis_charts",
            "params": params,
            "outcome": {
                "status": "ok",
                "tool_name": "analysis_charts",
                "result_summary": "artist top1 Artist A, plays=12",
                "source_range": "2020-01-01..2026-08-30",
                "data": {"found": True, "rows": [{"artist_name": "Artist A"}]},
            },
        },
        step_index=1,
    )
    conn.close()
    dispatch_count = 0

    def must_not_dispatch(params: BaseModel) -> AgentToolResult:
        nonlocal dispatch_count
        dispatch_count += 1
        return _chart_handler(params)

    registry = AgentToolRegistry()
    registry.register(
        AgentToolDefinition(
            name="analysis_charts",
            description="Read rankings",
            read_only=True,
            params_model=ChartParams,
            handler=must_not_dispatch,
        )
    )

    class ResumeModel:
        def complete(self, messages, tools, *, thinking):
            del tools, thinking
            assert any(item.get("role") == "tool" for item in messages)
            return LLMCompletion(
                content=("Artist A 是第一名，共 12 次。数据范围为 2020-01-01 至 2026-08-30。")
            )

    AgentRuntime(model=ResumeModel(), registry=registry, max_steps=4).run(
        "task-v2",
        {"question": "谁是第一名？", "session_id": 1},
        resume=True,
    )
    conn = factory()
    task = conn.execute("SELECT status FROM ai_task_runs WHERE task_id='task-v2'").fetchone()
    resumed = conn.execute(
        "SELECT COUNT(*) FROM ai_agent_turn_events WHERE event_type='run_resumed'"
    ).fetchone()[0]
    conn.close()
    assert task["status"] == "done"
    assert resumed == 1
    assert dispatch_count == 0
