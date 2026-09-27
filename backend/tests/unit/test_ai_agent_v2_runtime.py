from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from backend.core.migrations import migrate_080, migrate_081, migrate_082
from backend.domains.agent_runtime.event_log import AgentEventLog
from backend.domains.agent_runtime.observation import compact_observation
from backend.domains.agent_runtime.tool_runtime import ToolOutcome
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
from backend.providers.base import ProviderNetworkError
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
    assert shadow_payloads[0]["source"] == "event_log"
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


def test_v2_grounded_fallback_preserves_requested_markdown_ranking_table() -> None:
    request = {"question": "请用 Markdown 表格比较 2025 年 Top 5 艺人"}
    tool_results = [
        {
            "tool_name": "analysis_charts",
            "status": "ok",
            "source_range": "2025-01-01..2025-12-31",
            "result_summary": "artist rows=5",
            "data": {
                "period": {"label": "2025"},
                "entity": "artist",
                "metric": "plays",
                "total": 5,
                "rows": [
                    {
                        "rank": rank,
                        "artist_name": f"Artist {rank}",
                        "plays": 100 - rank,
                        "share_pct": 10 - rank,
                    }
                    for rank in range(1, 6)
                ],
            },
        }
    ]
    final_payload = ai_agent_service._final_payload(request, tool_results)

    answer, issues, used = ai_agent_v2_service._ensure_v2_grounded_answer(
        "模型声称有 999 次播放",
        final_payload,
        ["回答包含无法追溯到事实目录的数字：999"],
        request=request,
        tool_results=tool_results,
    )

    assert used is True
    assert "| 年份 | 排名 | 艺人 | 播放次数 |" in answer
    assert "| 2025 | 5 | Artist 5 | 95 |" in answer
    assert not any("无法追溯" in issue for issue in issues)


def test_v2_generic_ranking_fallback_satisfies_informative_contract() -> None:
    request = {"question": "过去一年我反复回去听的是谁？"}
    tool_results = [
        {
            "tool_name": "analysis_charts",
            "status": "ok",
            "source_range": "2025-09-22..2026-09-19",
            "data": {
                "period": {"label": "自定义"},
                "entity": "artist",
                "metric": "plays",
                "total": 1,
                "rows": [
                    {
                        "rank": 1,
                        "artist_name": "Taylor Swift",
                        "plays": 2897,
                        "share_pct": 16.2,
                    }
                ],
            },
        }
    ]
    final_payload = ai_agent_service._final_payload(request, tool_results)

    answer, issues, used = ai_agent_v2_service._ensure_v2_grounded_answer(
        "模型声称有 999 次播放",
        final_payload,
        ["回答包含无法追溯到事实目录的数字：999"],
        request=request,
        tool_results=tool_results,
    )

    assert used is True
    assert "第1名艺人：Taylor Swift" in answer
    assert not any("排行回答必须给出实际排名实体及排序指标" in issue for issue in issues)


def test_semantic_fallback_compares_weekday_and_weekend_per_day() -> None:
    answer = ai_agent_v2_service._semantic_evidence_fallback(
        {"question": "我周末和工作日听歌习惯差得明显吗？"},
        [
            {
                "tool_name": "analysis_stats",
                "data": {
                    "weekday_distribution": [
                        {"day": "周一", "plays": 10},
                        {"day": "周二", "plays": 10},
                        {"day": "周三", "plays": 10},
                        {"day": "周四", "plays": 10},
                        {"day": "周五", "plays": 10},
                        {"day": "周六", "plays": 30},
                        {"day": "周日", "plays": 30},
                    ]
                },
            }
        ],
    )

    assert answer is not None
    assert "周末更多" in answer
    assert "每天平均" in answer


def test_semantic_fallback_refuses_unsupported_language_time_cross() -> None:
    answer = ai_agent_v2_service._semantic_evidence_fallback(
        {"question": "按语言和时段交叉看，晚上最突出的语言是什么？"},
        [],
    )

    assert answer is not None
    assert "语言与时段" in answer
    assert "不能" in answer


def test_preflight_clarifies_1989_rerecording_identity() -> None:
    clarification = ai_agent_v2_service._preflight_clarification(
        {"question": "比较 1989 和同名重录版。"}
    )

    assert clarification is not None
    assert "1989 (Taylor's Version)" in clarification


def test_required_entity_followup_uses_album_leader_for_internal_tracks() -> None:
    followup = ai_agent_v2_service._required_entity_followup(
        {"question": "找出去年最常听的专辑；再列其中最常听的三首歌。"},
        [
            {
                "tool_name": "analysis_charts",
                "params": {
                    "entity": "album",
                    "metric": "plays",
                    "period": "custom",
                    "start_date": "2025-01-01",
                    "end_date": "2025-12-31",
                },
                "data": {
                    "entity": "album",
                    "metric": "plays",
                    "rows": [
                        {
                            "rank": 1,
                            "album_name": "The Life of a Showgirl",
                            "artist_name": "Taylor Swift",
                        }
                    ],
                },
            }
        ],
    )

    assert followup is not None
    assert followup[0] == "entity_stats"
    assert followup[1]["entity"] == "album"
    assert followup[1]["album_name"] == "The Life of a Showgirl"


def test_semantic_fallback_reads_album_track_breakdown() -> None:
    answer = ai_agent_v2_service._semantic_evidence_fallback(
        {"question": "找出去年最常听的专辑；再列其中最常听的三首歌。"},
        [
            {
                "tool_name": "analysis_charts",
                "data": {
                    "entity": "album",
                    "metric": "plays",
                    "rows": [{"album_name": "Album A", "artist_name": "Artist A"}],
                },
            },
            {
                "tool_name": "entity_stats",
                "data": {
                    "track_breakdown": [
                        {"track_name": "Track 1"},
                        {"track_name": "Track 2"},
                        {"track_name": "Track 3"},
                    ]
                },
            },
        ],
    )

    assert answer is not None
    assert "Track 1、Track 2、Track 3" in answer


def test_semantic_fallback_renders_scoped_artist_albums_and_tracks() -> None:
    answer = ai_agent_v2_service._semantic_evidence_fallback(
        {"question": "我最喜欢的 Ariana Grande 的专辑和歌曲是什么？"},
        [
            {
                "tool_name": "entity_stats",
                "data": {
                    "top_albums": [{"album_name": "eternal sunshine"}],
                    "top_tracks": [{"track_name": "Santa Tell Me"}],
                },
            }
        ],
    )

    assert answer is not None
    assert "eternal sunshine" in answer
    assert "Santa Tell Me" in answer
    assert "播放次数排行" in answer


def test_ranking_table_fallback_supports_late_night_tracks() -> None:
    answer = ai_agent_v2_service._ranking_table_fallback(
        {"question": "整理成表格。"},
        [
            {
                "tool_name": "listening_hours",
                "data": {
                    "view": "late_night_tracks",
                    "items": {
                        "tracks": [
                            {
                                "rank": 1,
                                "track_name": "vampire",
                                "artist_name": "Olivia Rodrigo",
                                "plays": 33,
                            }
                        ]
                    },
                },
            }
        ],
    )

    assert answer is not None
    assert "| 排名 | 歌曲 | 艺人 | 播放次数 |" in answer
    assert "| 1 | vampire | Olivia Rodrigo | 33 |" in answer


def test_comparison_fallback_labels_recent_half_year() -> None:
    answer = ai_agent_v2_service._comparison_fallback(
        [
            {
                "tool_name": "compare_entities",
                "params": {"period": "last_6_months"},
                "data": {
                    "includes_personal_billboard": False,
                    "winner_by_cumulative_plays": "GUTS",
                    "winner_by_total_hours": "GUTS",
                    "winner_by_intensity": "GUTS",
                    "entities": [
                        {"name": "GUTS", "found": True, "plays": 10, "hours": 1},
                        {"name": "SOUR", "found": True, "plays": 5, "hours": 0.5},
                    ],
                },
            }
        ]
    )

    assert answer is not None
    assert "最近半年" in answer


def test_optional_boundary_followup_question_does_not_pause_task() -> None:
    answer = (
        "当前只读工具存在关键缺口，因此无法给出事实结论。"
        + "现有结果只能说明时段分布，不能形成语言与时段交叉。" * 12
        + "需要我按其中哪个方向继续？"
    )

    assert (
        ai_agent_v2_service._clarification_needed(
            answer,
            [{"tool_name": "listening_hours", "data": {"view": "heatmap"}}],
        )
        is False
    )


def test_optional_retry_offer_does_not_pause_completed_evidence_answer() -> None:
    answer = (
        "工具已经返回去年夏天的汇总，但具体曲风名称在压缩结果中被截断。"
        + "目前仍能确认总时长、曲风覆盖数和语言覆盖率。" * 12
        + "如果你希望拿到具体曲风排名，可以缩小范围后再查。需要我重试吗？"
    )

    assert (
        ai_agent_v2_service._clarification_needed(
            answer,
            [{"tool_name": "taste_profile", "data": {"genre_count": 13}}],
        )
        is False
    )

    alternate_offer = answer.rsplit("需要我重试吗？", 1)[0] + "需要我按哪种方式重试？"
    assert (
        ai_agent_v2_service._clarification_needed(
            alternate_offer,
            [{"tool_name": "taste_profile", "data": {"genre_count": 13}}],
        )
        is False
    )

    capability_offer = (
        "当前只读工具不能跨全部专辑形成个人榜单与收听时长的交叉筛选。" * 8
        + "这里列出的候选只是名称匹配，不能回答原问题。需要我按哪种方式继续？"
    )
    assert (
        ai_agent_v2_service._clarification_needed(
            capability_offer,
            [
                {
                    "tool_name": "resolve_entity",
                    "data": {"candidates": [{"name": "A"}, {"name": "B"}]},
                }
            ],
        )
        is False
    )


def test_album_billboard_duration_cross_filter_has_precise_capability_boundary() -> None:
    answer = ai_agent_v2_service._semantic_evidence_fallback(
        {"question": "找出榜单成绩高但实际收听时长不高的专辑。"},
        [],
    )

    assert answer is not None
    assert "个人 Billboard" in answer
    assert "收听时长" in answer
    assert "指定专辑" in answer


def test_reference_metric_switch_fallback_uses_current_duration_evidence_only() -> None:
    answer = ai_agent_v2_service._semantic_evidence_fallback(
        {"question": "刚才第一位艺人，按时长再看一次。"},
        [
            {
                "tool_name": "analysis_charts",
                "data": {
                    "entity": "artist",
                    "metric": "hours",
                    "rows": [{"rank": 1, "artist_name": "Taylor Swift", "hours": 176.93}],
                },
            }
        ],
    )

    assert answer == "按当前同一时间范围的收听时长排行，第一名艺人是Taylor Swift。"
    assert "两种口径" not in answer


def test_v2_grounded_fallback_has_non_numeric_last_resort(monkeypatch) -> None:
    request = {"question": "去年夏天我最常听什么？"}
    tool_results = [
        {
            "tool_name": "analysis_charts",
            "status": "ok",
            "source_range": "2025-06-01..2025-08-31",
            "data": {
                "period": {"label": "自定义"},
                "entity": "artist",
                "metric": "plays",
                "total": 1,
                "rows": [{"rank": 1, "artist_name": "Artist A", "plays": 12}],
            },
        }
    ]
    final_payload = ai_agent_service._final_payload(request, tool_results)
    monkeypatch.setattr(
        ai_agent_v2_service,
        "_render_evidence_fallback",
        lambda request, tool_results, final_payload: "错误回退声称 999 次",
    )

    answer, issues, used = ai_agent_v2_service._ensure_v2_grounded_answer(
        "模型声称 999 次",
        final_payload,
        ["回答包含无法追溯到事实目录的数字：999"],
        request=request,
        tool_results=tool_results,
    )

    assert used is True
    assert "999" not in answer
    assert not any("无法追溯" in issue for issue in issues)


def test_agent_v2_provider_failure_after_tool_preserves_evidence_and_finishes(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "agent-provider-degraded.db"
    _create_runtime_db(db_path)
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)

    class ProviderFailsAfterTool:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, messages, tools, *, thinking):
            del messages, tools, thinking
            self.calls += 1
            if self.calls == 1:
                return LLMCompletion(
                    tool_calls=[
                        LLMToolCall(
                            call_id="call-1",
                            name="analysis_charts",
                            arguments={"entity": "artist", "metric": "plays"},
                        )
                    ]
                )
            raise ProviderNetworkError("test", "temporary upstream failure")

    model = ProviderFailsAfterTool()
    AgentRuntime(model=model, registry=_chart_registry(), max_steps=4).run(
        "task-v2",
        {"question": "谁是我听得最多的艺人？"},
    )

    conn = factory()
    task = conn.execute(
        "SELECT status, result_json FROM ai_task_runs WHERE task_id='task-v2'"
    ).fetchone()
    tool_call_count = conn.execute("SELECT COUNT(*) FROM ai_tool_calls").fetchone()[0]
    result = json.loads(task["result_json"])
    conn.close()

    assert task["status"] == "done"
    assert tool_call_count == 1
    assert model.calls == 3
    assert result["stop_reason"] == "provider_degraded_fallback"
    assert result["provider_degraded"] is True
    assert result["grounded_fallback_used"] is True
    assert result["evidence_coverage"] == 1.0
    assert "12" in result["answer"]


def test_agent_v2_budget_timeout_after_tool_publishes_observed_evidence(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "agent-budget-degraded.db"
    _create_runtime_db(db_path)
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)
    now = [0.0]

    def slow_chart_handler(params: BaseModel) -> AgentToolResult:
        now[0] += 20.0
        return _chart_handler(params)

    registry = AgentToolRegistry()
    registry.register(
        AgentToolDefinition(
            name="analysis_charts",
            description="Read rankings",
            read_only=True,
            params_model=ChartParams,
            handler=slow_chart_handler,
        )
    )
    model = FakeModel()
    AgentRuntime(
        model=model,
        registry=registry,
        max_steps=4,
        timeout_seconds=10,
        clock=lambda: now[0],
    ).run("task-v2", {"question": "谁是我听得最多的艺人？"})

    conn = factory()
    task = conn.execute(
        "SELECT status, result_json FROM ai_task_runs WHERE task_id='task-v2'"
    ).fetchone()
    result = json.loads(task["result_json"])
    conn.close()

    assert task["status"] == "done"
    assert model.calls == 1
    assert result["stop_reason"] == "budget_degraded_fallback"
    assert result["budget_degraded"] is True
    assert result["grounded_fallback_used"] is True
    assert result["evidence_coverage"] == 1.0
    assert "12" in result["answer"]


def test_agent_v2_empty_completion_after_tool_uses_observed_evidence(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "agent-empty-completion.db"
    _create_runtime_db(db_path)
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)

    class EmptyAfterToolModel(FakeModel):
        def complete(self, messages, tools, *, thinking):
            if self.calls == 0:
                return super().complete(messages, tools, thinking=thinking)
            self.calls += 1
            return LLMCompletion(content="", tool_calls=[])

    model = EmptyAfterToolModel()
    AgentRuntime(model=model, registry=_chart_registry(), max_steps=4).run(
        "task-v2",
        {"question": "谁是我听得最多的艺人？"},
    )

    conn = factory()
    task = conn.execute(
        "SELECT status, result_json FROM ai_task_runs WHERE task_id='task-v2'"
    ).fetchone()
    result = json.loads(task["result_json"])
    conn.close()

    assert task["status"] == "done"
    assert result["stop_reason"] == "budget_degraded_fallback"
    assert result["grounded_fallback_used"] is True
    assert result["evidence_coverage"] == 1.0


def test_comparison_fallback_honors_billboard_exclusion() -> None:
    answer = ai_agent_v2_service._comparison_fallback(
        [
            {
                "tool_name": "compare_entities",
                "data": {
                    "includes_personal_billboard": False,
                    "winner_by_cumulative_plays": "Showgirl",
                    "winner_by_total_hours": "Showgirl",
                    "winner_by_intensity": "GUTS",
                    "entities": [
                        {
                            "name": "GUTS",
                            "found": True,
                            "plays": 271,
                            "hours": 14.3,
                            "plays_per_window_week": 8.2,
                            "power_score": None,
                        },
                        {
                            "name": "Showgirl",
                            "found": True,
                            "plays": 524,
                            "hours": 31.3,
                            "plays_per_window_week": 15.9,
                            "power_score": None,
                        },
                    ],
                },
            }
        ]
    )

    assert answer is not None
    assert "Billboard" not in answer
    assert "Power Score" not in answer
    assert "None" not in answer
    assert "播放时长更高：Showgirl" in answer
    assert "所选窗口周均播放更高：GUTS" in answer


def test_question_context_honors_structured_metric_exclusions() -> None:
    context = ai_agent_service._question_context(
        {
            "question": "比较 GUTS 和 Showgirl 的播放次数与个人 Billboard；再比较播放时长",
            "_agent_session_state": {
                "metrics": ["plays", "hours"],
                "excluded_dimensions": ["personal_billboard"],
            },
        }
    )

    assert context["routing_signals"]["explicit_billboard"] is False
    assert context["question_intent"]["requested_metrics"] == ["plays", "hours"]
    assert "personal_billboard" not in context["question_frame"]["analysis_axes"]
    assert "personal_billboard" not in context["evidence_recipe"]["required_axes"]
    assert "personal_billboard" not in context["evidence_recipe"]["conditional_axes"]


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


def test_agent_v2_rejects_unsupported_apple_music_scope_without_tools(tmp_path, monkeypatch):
    db_path = tmp_path / "agent-apple-music-safety.db"
    _create_runtime_db(db_path)
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)
    model = FakeModel()

    AgentRuntime(model=model, registry=AgentToolRegistry()).run(
        "task-v2",
        {"question": "我在 Apple Music 上最常听什么？", "session_id": 1},
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
    assert "Apple Music" in result["answer"]
    assert "Spotify" in result["answer"]


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
    task = conn.execute(
        "SELECT status, error, result_json FROM ai_task_runs WHERE task_id='task-v2'"
    ).fetchone()
    tool_count = conn.execute("SELECT COUNT(*) FROM ai_tool_calls").fetchone()[0]
    deduplicated = conn.execute(
        "SELECT COUNT(*) FROM ai_agent_turn_events WHERE event_type='tool_call_deduplicated'"
    ).fetchone()[0]
    conn.close()

    result = json.loads(task["result_json"])
    assert task["status"] == "done"
    assert task["error"] is None
    assert result["stop_reason"] == "budget_degraded_fallback"
    assert result["evidence_coverage"] == 1.0
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


def test_compact_observation_preserves_nested_taste_bucket_scalars() -> None:
    observation = compact_observation(
        {
            "status": "ok",
            "data": {
                "taste_profile": {
                    "primary_styles": {
                        "buckets": [
                            {
                                "key": "pop",
                                "label": "Pop",
                                "hours": 88.5,
                                "share_pct": 42.1,
                            }
                        ]
                    }
                }
            },
        }
    )

    bucket = observation["data"]["taste_profile"]["primary_styles"]["buckets"][0]
    assert bucket == {
        "key": "pop",
        "label": "Pop",
        "hours": 88.5,
        "share_pct": 42.1,
    }


def test_tool_outcome_does_not_recompact_nested_observation() -> None:
    outcome = ToolOutcome(
        call_id="call-taste",
        tool_name="taste_profile",
        status="ok",
        params={},
        params_summary="{}",
        result_summary="styles=1",
        source_range="2025-06-01..2025-08-31",
        data={"taste_profile": {"primary_styles": {"buckets": [{"label": "Pop", "hours": 88.5}]}}},
    )

    bucket = outcome.model_payload()["data"]["taste_profile"]["primary_styles"]["buckets"][0]
    assert bucket == {"label": "Pop", "hours": 88.5}


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


def test_v6_chat_cancellation_during_retry_prevents_second_provider_dispatch(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "agent-v6-cancel-retry.db"
    _create_runtime_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    migrate_080(conn)
    migrate_081(conn)
    migrate_082(conn)
    conn.execute(
        """UPDATE ai_task_runs
           SET runtime_version='v6', workflow_version='v6', event_schema_version=2,
               status='queued'
           WHERE task_id='task-v2'"""
    )
    conn.commit()
    conn.close()
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)

    class CancelOnFirstFailure:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, messages, tools, *, thinking):
            del messages, tools, thinking
            self.calls += 1
            cancelling = factory()
            cancelling.execute(
                """UPDATE ai_task_runs
                   SET status='cancelled', stage='cancelled', state_version=state_version+1
                   WHERE task_id='task-v2'"""
            )
            cancelling.commit()
            cancelling.close()
            raise ProviderNetworkError("fake", "retryable failure after cancellation")

    model = CancelOnFirstFailure()
    AgentRuntime(model=model, registry=_chart_registry(), max_steps=4).run(
        "task-v2",
        {"question": "谁是我听得最多的艺人？", "session_id": 1},
    )

    conn = factory()
    task = conn.execute("SELECT status FROM ai_task_runs WHERE task_id='task-v2'").fetchone()
    dispatches = conn.execute(
        "SELECT status FROM ai_model_dispatch_attempts WHERE task_id='task-v2'"
    ).fetchall()
    usage = conn.execute(
        "SELECT model_call_count, usage_unknown_count FROM ai_runtime_budget_usage "
        "WHERE task_id='task-v2'"
    ).fetchone()
    conn.close()

    assert task["status"] == "cancelled"
    assert model.calls == 1
    assert len(dispatches) == 1
    assert usage["model_call_count"] == 1
    assert usage["usage_unknown_count"] == 1


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
    state_event = conn.execute(
        "SELECT payload_json FROM ai_agent_turn_events "
        "WHERE event_type='session_state_updated' ORDER BY event_id DESC LIMIT 1"
    ).fetchone()
    public_event = conn.execute(
        "SELECT payload_json FROM ai_task_events "
        "WHERE event_type='session_state_updated' ORDER BY event_id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert inbox["status"] == "consumed"
    assert inbox["consumed_at"] is not None
    assert consumed_events == 1
    state_payload = json.loads(state_event["payload_json"])
    assert state_payload["semantic_action"] == "replace_constraints"
    assert state_payload["state"]["time_range"]["period"] == "custom"
    public_payload = json.loads(public_event["payload_json"])
    assert public_payload["state"]["time_range"]["period"] == "custom"
    assert "active_question" not in public_payload["state"]
    assert "pending_requirements" not in public_payload["state"]


def test_agent_persists_clarification_as_awaiting_input(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "agent-clarification.db"
    _create_runtime_db(db_path)
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)

    class ClarificationModel(FakeModel):
        def complete(self, messages, tools, *, thinking):
            self.calls += 1
            if self.calls == 1:
                return LLMCompletion(
                    tool_calls=[
                        LLMToolCall(
                            call_id="clarify-source",
                            name="analysis_charts",
                            arguments={"entity": "artist", "metric": "plays"},
                        )
                    ],
                    finish_reason="tool_calls",
                )
            return LLMCompletion(content="请确认，你指的是 Artist A 吗？", finish_reason="stop")

    AgentRuntime(model=ClarificationModel(), registry=_chart_registry(), max_steps=4).run(
        "task-v2",
        {"question": "继续分析那个艺人", "session_id": 1},
    )

    conn = factory()
    task = conn.execute(
        "SELECT status, stage, message, result_json FROM ai_task_runs WHERE task_id='task-v2'"
    ).fetchone()
    event_types = [
        row[0]
        for row in conn.execute(
            "SELECT event_type FROM ai_agent_turn_events ORDER BY sequence"
        ).fetchall()
    ]
    conn.close()

    assert task["status"] == "awaiting_input"
    assert task["stage"] == "awaiting_input"
    assert task["message"] == "请确认，你指的是 Artist A 吗？"
    assert json.loads(task["result_json"])["runtime_contract"] == "v6"
    assert "clarification_requested" in event_types
    assert "turn_ended" not in event_types


def test_agent_preflight_clarifies_missing_same_name_album_before_model(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "agent-preflight-clarification.db"
    _create_runtime_db(db_path)
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)

    class UnexpectedModel(FakeModel):
        def complete(self, messages, tools, *, thinking):
            raise AssertionError("preflight clarification must not call the model")

    AgentRuntime(model=UnexpectedModel(), registry=_chart_registry(), max_steps=4).run(
        "task-v2",
        {"question": "我更常听哪一个同名专辑？"},
    )

    conn = factory()
    task = conn.execute(
        "SELECT status, result_json FROM ai_task_runs WHERE task_id='task-v2'"
    ).fetchone()
    conn.close()
    result = json.loads(task["result_json"])

    assert task["status"] == "awaiting_input"
    assert "专辑名" in result["clarification_question"]


def test_steering_invalidates_tool_evidence_from_old_constraints(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "agent-steering-evidence.db"
    _create_runtime_db(db_path)
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)

    class SteeringModel:
        calls = 0

        def complete(self, messages, tools, *, thinking):
            del tools, thinking
            self.calls += 1
            if self.calls == 1:
                conn = factory()
                conn.execute(
                    """INSERT INTO ai_agent_session_inbox
                       (task_id, session_id, input_type, content)
                       VALUES ('task-v2', 1, 'steer', '只看今年')"""
                )
                conn.commit()
                conn.close()
                return LLMCompletion(
                    tool_calls=[
                        LLMToolCall(
                            call_id="old",
                            name="analysis_charts",
                            arguments={"entity": "artist", "metric": "plays"},
                        )
                    ]
                )
            if self.calls == 2:
                return LLMCompletion(
                    tool_calls=[
                        LLMToolCall(
                            call_id="new",
                            name="analysis_charts",
                            arguments={"entity": "artist", "metric": "plays"},
                        )
                    ]
                )
            return LLMCompletion(content="Taylor Swift 是第一名。")

    AgentRuntime(model=SteeringModel(), registry=_chart_registry(), max_steps=4).run(
        "task-v2",
        {"question": "谁是我听得最多的艺人？", "session_id": 1},
    )

    conn = factory()
    task = conn.execute("SELECT result_json FROM ai_task_runs WHERE task_id='task-v2'").fetchone()
    invalidated = conn.execute(
        "SELECT payload_json FROM ai_agent_turn_events WHERE event_type='tool_evidence_invalidated'"
    ).fetchone()
    latest_tool_call = conn.execute(
        "SELECT payload_json FROM ai_agent_turn_events "
        "WHERE event_type='tool_call' ORDER BY event_id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    result = json.loads(task["result_json"])

    assert len(result["tools"]) == 1
    assert json.loads(invalidated["payload_json"])["invalidated_result_count"] == 1
    assert json.loads(latest_tool_call["payload_json"])["params"]["period"] == "custom"
    interpretation = result["temporal_guard"]["time_interpretation"]
    assert interpretation["label"] == "今年"
    assert interpretation["effective_start_date"] == "2026-01-01"
    assert interpretation["effective_end_date"] == "2026-08-30"


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


def test_v6_chat_resume_rejects_provider_change_for_unfinished_model_step(
    tmp_path,
    monkeypatch,
) -> None:
    """A process crash must resume the original logical request, not skip it."""

    db_path = tmp_path / "agent-v6-unfinished-model-step.db"
    _create_runtime_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    migrate_080(conn)
    migrate_081(conn)
    migrate_082(conn)
    conn.execute(
        """UPDATE ai_task_runs
           SET runtime_version='v6', workflow_version='v6', event_schema_version=2,
               status='running'
           WHERE task_id='task-v2'"""
    )
    conn.commit()
    conn.close()
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)

    class SimulatedProcessTermination(BaseException):
        pass

    class InterruptedModel:
        provider_id = "original:model"

        def __init__(self) -> None:
            self.calls = 0

        def complete(self, messages, tools, *, thinking):
            del messages, tools, thinking
            self.calls += 1
            raise SimulatedProcessTermination("worker terminated after dispatch")

    interrupted = InterruptedModel()
    with pytest.raises(SimulatedProcessTermination):
        AgentRuntime(model=interrupted, registry=_chart_registry(), max_steps=4).run(
            "task-v2",
            {"question": "谁是我听得最多的艺人？", "session_id": 1},
        )

    class ChangedModel:
        provider_id = "changed:model"

        def __init__(self) -> None:
            self.calls = 0

        def complete(self, messages, tools, *, thinking):
            del messages, tools, thinking
            self.calls += 1
            raise AssertionError("changed provider must not receive the frozen request")

    changed = ChangedModel()
    AgentRuntime(model=changed, registry=_chart_registry(), max_steps=4).run(
        "task-v2",
        {"question": "谁是我听得最多的艺人？", "session_id": 1},
        resume=True,
    )

    conn = factory()
    task = conn.execute("SELECT status, error FROM ai_task_runs WHERE task_id='task-v2'").fetchone()
    requests = conn.execute(
        """SELECT call_id FROM ai_runtime_events
           WHERE task_id='task-v2' AND event_type='model_request_started'
           ORDER BY sequence"""
    ).fetchall()
    dispatches = conn.execute(
        """SELECT call_id, provider_id FROM ai_model_dispatch_attempts
           WHERE task_id='task-v2' ORDER BY attempt_index"""
    ).fetchall()
    conn.close()

    assert interrupted.calls == 1
    assert changed.calls == 0
    assert task["status"] == "error"
    assert "provider/model" in str(task["error"])
    assert [row["call_id"] for row in requests] == [requests[0]["call_id"]]
    assert len(dispatches) == 1
    assert dispatches[0]["provider_id"] == "original:model"


def test_v6_chat_resume_retries_same_logical_call_with_original_provider(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "agent-v6-original-call-retry.db"
    _create_runtime_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    migrate_080(conn)
    migrate_081(conn)
    migrate_082(conn)
    conn.execute(
        """UPDATE ai_task_runs
           SET runtime_version='v6', workflow_version='v6', event_schema_version=2,
               status='running'
           WHERE task_id='task-v2'"""
    )
    conn.commit()
    conn.close()
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)

    class SimulatedProcessTermination(BaseException):
        pass

    class InterruptedModel:
        provider_id = "stable:model"

        def complete(self, messages, tools, *, thinking):
            del messages, tools, thinking
            raise SimulatedProcessTermination("terminated with dispatch outcome unknown")

    with pytest.raises(SimulatedProcessTermination):
        AgentRuntime(model=InterruptedModel(), registry=_chart_registry(), max_steps=3).run(
            "task-v2",
            {"question": "谁是我听得最多的艺人？", "session_id": 1},
        )

    class ResumedModel:
        provider_id = "stable:model"

        def __init__(self) -> None:
            self.calls = 0

        def complete(self, messages, tools, *, thinking):
            del tools, thinking
            self.calls += 1
            if self.calls == 1:
                assert not any(item.get("role") == "tool" for item in messages)
                return LLMCompletion(
                    tool_calls=[
                        LLMToolCall(
                            call_id="stable-tool-call",
                            name="analysis_charts",
                            arguments={"entity": "artist", "metric": "plays"},
                        )
                    ]
                )
            assert any(item.get("role") == "tool" for item in messages)
            return LLMCompletion(
                content=(
                    "Artist A 是第一名，共 12 次，占 30%。数据范围为 2020-01-01 至 2026-08-30。"
                )
            )

    resumed = ResumedModel()
    AgentRuntime(model=resumed, registry=_chart_registry(), max_steps=3).run(
        "task-v2",
        {"question": "谁是我听得最多的艺人？", "session_id": 1},
        resume=True,
    )

    conn = factory()
    task = conn.execute(
        "SELECT status, result_json FROM ai_task_runs WHERE task_id='task-v2'"
    ).fetchone()
    request_rows = conn.execute(
        """SELECT call_id, COUNT(*) AS count FROM ai_runtime_events
           WHERE task_id='task-v2' AND event_type='model_request_started'
           GROUP BY call_id ORDER BY call_id"""
    ).fetchall()
    dispatch_rows = conn.execute(
        """SELECT call_id, attempt_index, provider_id FROM ai_model_dispatch_attempts
           WHERE task_id='task-v2' ORDER BY call_id, attempt_index"""
    ).fetchall()
    usage = conn.execute(
        """SELECT step_count, model_call_count, usage_unknown_count
           FROM ai_runtime_budget_usage WHERE task_id='task-v2'"""
    ).fetchone()
    conn.close()

    result = json.loads(task["result_json"])
    assert task["status"] == "done"
    assert result["steps"] == 2
    assert resumed.calls == 2
    assert [row["count"] for row in request_rows] == [1, 1]
    first_call_id = request_rows[0]["call_id"]
    first_dispatches = [row for row in dispatch_rows if row["call_id"] == first_call_id]
    assert [row["attempt_index"] for row in first_dispatches] == [1, 2]
    assert {row["provider_id"] for row in first_dispatches} == {"stable:model"}
    assert usage["step_count"] == 2
    assert usage["model_call_count"] == 3
    assert usage["usage_unknown_count"] >= 1


@pytest.mark.parametrize("mismatch", ["tool_schema", "parameters"])
def test_v6_chat_resume_rejects_incompatible_frozen_request_contract(
    tmp_path,
    monkeypatch,
    mismatch,
) -> None:
    db_path = tmp_path / f"agent-v6-{mismatch}-mismatch.db"
    _create_runtime_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    migrate_080(conn)
    migrate_081(conn)
    migrate_082(conn)
    conn.execute(
        """UPDATE ai_task_runs
           SET runtime_version='v6', workflow_version='v6', event_schema_version=2,
               status='running'
           WHERE task_id='task-v2'"""
    )
    conn.commit()
    conn.close()
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)

    class SimulatedProcessTermination(BaseException):
        pass

    class InterruptedModel:
        provider_id = "stable:model"

        def complete(self, messages, tools, *, thinking):
            del messages, tools, thinking
            raise SimulatedProcessTermination("terminated after request freeze")

    with pytest.raises(SimulatedProcessTermination):
        AgentRuntime(model=InterruptedModel(), registry=_chart_registry(), max_steps=3).run(
            "task-v2",
            {"question": "谁是我听得最多的艺人？", "session_id": 1},
        )

    registry = _chart_registry()
    if mismatch == "tool_schema":
        registry = AgentToolRegistry()
        registry.register(
            AgentToolDefinition(
                name="analysis_charts",
                description="Changed rankings contract",
                read_only=True,
                params_model=ChartParams,
                handler=_chart_handler,
            )
        )
    else:
        conn = factory()
        row = conn.execute(
            """SELECT event_id, payload_json FROM ai_runtime_events
               WHERE task_id='task-v2' AND event_type='model_request_started'"""
        ).fetchone()
        descriptor = json.loads(row["payload_json"])
        descriptor["parameters"]["temperature"] = 0.7
        conn.execute(
            "UPDATE ai_runtime_events SET payload_json=? WHERE event_id=?",
            (json.dumps(descriptor, ensure_ascii=False), row["event_id"]),
        )
        conn.commit()
        conn.close()

    class NoDispatchModel:
        provider_id = "stable:model"

        def __init__(self) -> None:
            self.calls = 0

        def complete(self, messages, tools, *, thinking):
            del messages, tools, thinking
            self.calls += 1
            raise AssertionError("incompatible frozen request must not dispatch")

    model = NoDispatchModel()
    AgentRuntime(model=model, registry=registry, max_steps=3).run(
        "task-v2",
        {"question": "谁是我听得最多的艺人？", "session_id": 1},
        resume=True,
    )

    conn = factory()
    task = conn.execute("SELECT status, error FROM ai_task_runs WHERE task_id='task-v2'").fetchone()
    dispatch_count = conn.execute(
        "SELECT COUNT(*) FROM ai_model_dispatch_attempts WHERE task_id='task-v2'"
    ).fetchone()[0]
    conn.close()

    assert model.calls == 0
    assert task["status"] == "error"
    assert ("schema" if mismatch == "tool_schema" else "参数") in task["error"]
    assert dispatch_count == 1


def test_v6_chat_resume_defers_new_steering_until_after_frozen_retry(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "agent-v6-deferred-steering.db"
    _create_runtime_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    migrate_080(conn)
    migrate_081(conn)
    migrate_082(conn)
    conn.execute(
        """UPDATE ai_task_runs
           SET runtime_version='v6', workflow_version='v6', event_schema_version=2,
               status='running'
           WHERE task_id='task-v2'"""
    )
    conn.commit()
    conn.close()
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)

    class SimulatedProcessTermination(BaseException):
        pass

    class InterruptedModel:
        provider_id = "stable:model"

        def complete(self, messages, tools, *, thinking):
            del messages, tools, thinking
            raise SimulatedProcessTermination("terminated after frozen dispatch")

    with pytest.raises(SimulatedProcessTermination):
        AgentRuntime(model=InterruptedModel(), registry=_chart_registry(), max_steps=4).run(
            "task-v2",
            {"question": "谁是我听得最多的艺人？", "session_id": 1},
        )
    conn = factory()
    conn.execute(
        """INSERT INTO ai_agent_session_inbox
           (task_id, session_id, input_type, content)
           VALUES ('task-v2', 1, 'steer', '只看今年，不要全部时间')"""
    )
    conn.commit()
    conn.close()

    class SteeringAwareModel:
        provider_id = "stable:model"

        def __init__(self) -> None:
            self.calls = 0

        def complete(self, messages, tools, *, thinking):
            del tools, thinking
            self.calls += 1
            has_steering = any("只看今年" in str(item.get("content") or "") for item in messages)
            if self.calls == 1:
                assert has_steering is False
                return LLMCompletion(
                    tool_calls=[
                        LLMToolCall(
                            call_id="original-scope-call",
                            name="analysis_charts",
                            arguments={"entity": "artist", "metric": "plays"},
                        )
                    ]
                )
            if self.calls == 2:
                assert has_steering is True
                return LLMCompletion(
                    tool_calls=[
                        LLMToolCall(
                            call_id="steered-scope-call",
                            name="analysis_charts",
                            arguments={
                                "entity": "artist",
                                "metric": "plays",
                                "period": "this_year",
                            },
                        )
                    ]
                )
            assert has_steering is True
            return LLMCompletion(
                content=(
                    "今年 Artist A 是第一名，共 12 次，占 30%。"
                    "数据范围为 2020-01-01 至 2026-08-30。"
                )
            )

    model = SteeringAwareModel()
    AgentRuntime(model=model, registry=_chart_registry(), max_steps=4).run(
        "task-v2",
        {"question": "谁是我听得最多的艺人？", "session_id": 1},
        resume=True,
    )

    conn = factory()
    task = conn.execute("SELECT status FROM ai_task_runs WHERE task_id='task-v2'").fetchone()
    inbox = conn.execute(
        "SELECT status FROM ai_agent_session_inbox ORDER BY inbox_id DESC LIMIT 1"
    ).fetchone()
    consumed_step = conn.execute(
        """SELECT step_index FROM ai_agent_turn_events
           WHERE event_type='session_input_consumed' ORDER BY event_id DESC LIMIT 1"""
    ).fetchone()
    conn.close()

    assert task["status"] == "done"
    assert model.calls == 3
    assert inbox["status"] == "consumed"
    assert consumed_step["step_index"] == 2


def test_v6_chat_resume_replays_committed_response_and_only_missing_tool(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "agent-v6-partial-tools.db"
    _create_runtime_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    migrate_080(conn)
    migrate_081(conn)
    migrate_082(conn)
    conn.execute(
        """UPDATE ai_task_runs
           SET runtime_version='v6', workflow_version='v6', event_schema_version=2,
               status='running'
           WHERE task_id='task-v2'"""
    )
    conn.commit()
    conn.close()
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)

    class SimulatedProcessTermination(BaseException):
        pass

    counts = {"artist": 0, "album": 0}

    def crash_second_tool_once(params: BaseModel) -> AgentToolResult:
        parsed = ChartParams.model_validate(params)
        counts[parsed.entity] += 1
        if parsed.entity == "album" and counts[parsed.entity] == 1:
            raise SimulatedProcessTermination("terminated during second tool")
        return _chart_handler(parsed)

    registry = AgentToolRegistry()
    registry.register(
        AgentToolDefinition(
            name="analysis_charts",
            description="Read rankings",
            read_only=True,
            params_model=ChartParams,
            handler=crash_second_tool_once,
            supports_parallel=False,
        )
    )

    class TwoToolModel:
        provider_id = "stable:model"

        def complete(self, messages, tools, *, thinking):
            del messages, tools, thinking
            return LLMCompletion(
                tool_calls=[
                    LLMToolCall(
                        call_id="artist-call",
                        name="analysis_charts",
                        arguments={"entity": "artist", "metric": "plays"},
                    ),
                    LLMToolCall(
                        call_id="album-call",
                        name="analysis_charts",
                        arguments={"entity": "album", "metric": "plays"},
                    ),
                ]
            )

    with pytest.raises(SimulatedProcessTermination):
        AgentRuntime(model=TwoToolModel(), registry=registry, max_steps=3).run(
            "task-v2",
            {"question": "比较我的艺人与专辑排行", "session_id": 1},
        )

    class FinalModel:
        provider_id = "stable:model"

        def __init__(self) -> None:
            self.calls = 0

        def complete(self, messages, tools, *, thinking):
            del tools, thinking
            self.calls += 1
            tool_ids = {item.get("tool_call_id") for item in messages if item.get("role") == "tool"}
            assert tool_ids == {"artist-call", "album-call"}
            return LLMCompletion(
                content=(
                    "艺人与专辑排行均已查询；Artist A 为艺人第一名，共 12 次。"
                    "数据范围为 2020-01-01 至 2026-08-30。"
                )
            )

    final_model = FinalModel()
    AgentRuntime(model=final_model, registry=registry, max_steps=3).run(
        "task-v2",
        {"question": "比较我的艺人与专辑排行", "session_id": 1},
        resume=True,
    )

    conn = factory()
    task = conn.execute("SELECT status FROM ai_task_runs WHERE task_id='task-v2'").fetchone()
    response_count = conn.execute(
        """SELECT COUNT(*) FROM ai_runtime_events
           WHERE task_id='task-v2' AND event_type='model_response_committed'
             AND call_id LIKE '%:step:1:model'"""
    ).fetchone()[0]
    observations = conn.execute(
        """SELECT call_id, COUNT(*) AS count FROM ai_runtime_events
           WHERE task_id='task-v2' AND event_type='tool_observation_committed'
           GROUP BY call_id ORDER BY call_id"""
    ).fetchall()
    conn.close()

    assert task["status"] == "done"
    assert final_model.calls == 1
    assert counts == {"artist": 1, "album": 2}
    assert response_count == 1
    assert {row["call_id"]: row["count"] for row in observations} == {
        "album-call": 1,
        "artist-call": 1,
    }


def test_v6_chat_last_step_replays_committed_answer_without_new_provider_call(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "agent-v6-final-step-publish.db"
    _create_runtime_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    migrate_080(conn)
    migrate_081(conn)
    migrate_082(conn)
    conn.execute(
        """UPDATE ai_task_runs
           SET runtime_version='v6', workflow_version='v6', event_schema_version=2,
               status='running'
           WHERE task_id='task-v2'"""
    )
    conn.commit()
    conn.close()
    factory = _connection_factory(db_path)
    monkeypatch.setattr(ai_agent_v2_service, "get_db", factory)
    monkeypatch.setattr(ai_agent_service, "get_db", factory)

    class SimulatedProcessTermination(BaseException):
        pass

    class FinalStepModel(FakeModel):
        provider_id = "stable:model"

    original_final_payload = ai_agent_v2_service._final_payload
    final_payload_calls = 0

    def terminate_before_publish(request, tool_results):
        nonlocal final_payload_calls
        final_payload_calls += 1
        if final_payload_calls == 1:
            raise SimulatedProcessTermination("terminated after final response commit")
        return original_final_payload(request, tool_results)

    monkeypatch.setattr(ai_agent_v2_service, "_final_payload", terminate_before_publish)
    initial_model = FinalStepModel()
    with pytest.raises(SimulatedProcessTermination):
        AgentRuntime(model=initial_model, registry=_chart_registry(), max_steps=2).run(
            "task-v2",
            {"question": "谁是我听得最多的艺人？", "session_id": 1},
        )
    assert initial_model.calls == 2

    class NoDispatchModel:
        provider_id = "stable:model"

        def __init__(self) -> None:
            self.calls = 0

        def complete(self, messages, tools, *, thinking):
            del messages, tools, thinking
            self.calls += 1
            raise AssertionError("committed final-step response must be replayed")

    resumed_model = NoDispatchModel()
    AgentRuntime(model=resumed_model, registry=_chart_registry(), max_steps=2).run(
        "task-v2",
        {"question": "谁是我听得最多的艺人？", "session_id": 1},
        resume=True,
    )

    conn = factory()
    task = conn.execute(
        "SELECT status, result_json FROM ai_task_runs WHERE task_id='task-v2'"
    ).fetchone()
    usage = conn.execute(
        """SELECT step_count, model_call_count FROM ai_runtime_budget_usage
           WHERE task_id='task-v2'"""
    ).fetchone()
    conn.close()

    assert task["status"] == "done"
    assert json.loads(task["result_json"])["steps"] == 2
    assert resumed_model.calls == 0
    assert usage["step_count"] == 2
    assert usage["model_call_count"] == 2
