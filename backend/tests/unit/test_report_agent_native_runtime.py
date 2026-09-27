from __future__ import annotations

import json
import sqlite3

import pytest

from backend.core.migrations import migrate_082, migrate_083, migrate_084
from backend.domains.agent_runtime.runtime_store import (
    IncompatibleModelRequestError,
    PersistentBudgetExceededError,
    RuntimeStore,
)
from backend.domains.ai_reports import report_agent
from backend.providers.base import ProviderNetworkError
from backend.providers.llm.client import LLMCompletion, LLMTextCompletion, LLMToolCall
from backend.services import ai_agent_v2_service


def _report_runtime_store() -> tuple[sqlite3.Connection, RuntimeStore]:
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
    migrate_082(conn)
    migrate_083(conn)
    migrate_084(conn)
    conn.execute(
        """INSERT INTO ai_task_runs
           (task_id, task_type, status, stage, runtime_version, workflow_version,
            event_schema_version, generation, lease_generation)
           VALUES ('report-v6', 'ai_report_yearly', 'running', 'researching',
                   'v6', 'yearly_v6', 2, 1, 0)"""
    )
    conn.commit()
    return conn, RuntimeStore(conn, "report-v6")


def test_report_research_uses_native_tool_observation_loop(monkeypatch):
    class FakeNativeModel:
        def __init__(self):
            self.calls = 0
            self.messages = []
            self.tools = []

        def complete(self, messages, tools, *, thinking):
            self.calls += 1
            self.messages = messages
            self.tools = tools
            if self.calls == 1:
                return LLMCompletion(
                    tool_calls=[
                        LLMToolCall(
                            call_id="report-call-1",
                            name="yearly_overview",
                            arguments={},
                        )
                    ]
                )
            return LLMCompletion(content="年度研究完成：共播放 88 次。")

    model = FakeNativeModel()
    monkeypatch.setattr(
        ai_agent_v2_service,
        "ConfiguredNativeToolModel",
        lambda _budget=None: model,
    )

    research, evidence = report_agent._native_report_research(
        planner_prompt="research",
        planner_user="yearly",
        base_filters={"min_ms": 30000},
        year=2025,
        end_date="2025-12-31",
        research_context={
            "reporting_period": {
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
            },
            "hero": {"total_plays": 88, "total_minutes": 600},
        },
        emit_event=None,
    )

    assert research == "年度研究完成：共播放 88 次。"
    assert evidence[0]["status"] == "ok"
    assert evidence[0]["_params"]["year"] == 2025
    assert evidence[0]["data"]["hero"]["total_plays"] == 88
    assert "yearly_overview" in [tool["name"] for tool in model.tools]
    assert "web_search" not in [tool["name"] for tool in model.tools]
    tool_messages = [message for message in model.messages if message["role"] == "tool"]
    assert len(tool_messages) == 1
    observed = json.loads(tool_messages[0]["content"])
    assert observed["data"]["hero"]["total_plays"] == 88


def test_durable_report_research_replays_without_model_or_tool_reexecution(monkeypatch):
    import backend.core.config as runtime_config
    from backend.domains.ai_reports import report_agent as agent

    class FakeNativeModel:
        provider_id = "fake:research"

        def __init__(self):
            self.calls = 0

        def complete(self, messages, tools, *, thinking):
            del messages, tools, thinking
            self.calls += 1
            if self.calls == 1:
                return LLMCompletion(
                    tool_calls=[
                        LLMToolCall(
                            call_id="overview-1",
                            name="yearly_overview",
                            arguments={},
                        )
                    ],
                    usage={"input_tokens": 10, "output_tokens": 5},
                )
            return LLMCompletion(
                content="固定年度研究摘要",
                usage={"input_tokens": 12, "output_tokens": 6},
            )

    conn, store = _report_runtime_store()
    model = FakeNativeModel()
    tool_calls = 0
    original_execute = agent.execute_report_tool

    def counted_execute(*args, **kwargs):
        nonlocal tool_calls
        tool_calls += 1
        return original_execute(*args, **kwargs)

    monkeypatch.setattr(runtime_config, "AI_AGENT_RUNTIME", "v2")
    monkeypatch.setattr(
        ai_agent_v2_service,
        "ConfiguredNativeToolModel",
        lambda _budget=None: model,
    )
    monkeypatch.setattr(agent, "execute_report_tool", counted_execute)
    kwargs = {
        "planner_prompt": "research",
        "planner_user": "yearly",
        "base_filters": {"min_ms": 30000},
        "year": 2025,
        "end_date": "2025-12-31",
        "research_context": {
            "reporting_period": {
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
            },
            "hero": {"total_plays": 88, "total_minutes": 600},
        },
        "emit_event": None,
        "checkpoint_store": store,
    }
    try:
        first = agent._native_report_research(**kwargs)
        first_model_calls = model.calls
        first_tool_calls = tool_calls
        conn.execute(
            """UPDATE ai_runtime_budget_usage
               SET step_count=?, model_call_count=?, active_elapsed_ms=300000
               WHERE task_id='report-v6' AND generation=1""",
            (
                runtime_config.AI_AGENT_MAX_STEPS + 12,
                runtime_config.AI_AGENT_MAX_STEPS + 12,
            ),
        )
        conn.commit()
        replayed = agent._native_report_research(**kwargs)
        usage = store.get_budget_usage()
    finally:
        conn.close()

    assert first == replayed
    assert first[0] == "固定年度研究摘要"
    assert first_model_calls == model.calls == 2
    assert first_tool_calls == tool_calls == 1
    assert usage["step_count"] == runtime_config.AI_AGENT_MAX_STEPS + 12
    assert usage["model_call_count"] == runtime_config.AI_AGENT_MAX_STEPS + 12


def test_durable_report_research_stops_retry_after_persisted_cancellation(monkeypatch):
    conn, store = _report_runtime_store()

    class CancellingResearchModel:
        provider_id = "fake:research"

        def __init__(self):
            self.calls = 0

        def complete(self, messages, tools, *, thinking):
            del messages, tools, thinking
            self.calls += 1
            conn.execute("UPDATE ai_task_runs SET status='cancelled' WHERE task_id='report-v6'")
            conn.commit()
            raise ProviderNetworkError("fake", "retryable failure after cancellation")

    model = CancellingResearchModel()
    monkeypatch.setattr(
        ai_agent_v2_service,
        "ConfiguredNativeToolModel",
        lambda _budget=None: model,
    )
    try:
        with pytest.raises(Exception) as caught:
            report_agent._native_report_research(
                planner_prompt="research",
                planner_user="yearly",
                base_filters={"min_ms": 30000},
                year=2025,
                end_date="2025-12-31",
                research_context={
                    "reporting_period": {
                        "start_date": "2025-01-01",
                        "end_date": "2025-12-31",
                    },
                    "hero": {"total_plays": 88, "total_minutes": 600},
                },
                emit_event=None,
                should_continue=lambda: (
                    conn.execute(
                        "SELECT status FROM ai_task_runs WHERE task_id='report-v6'"
                    ).fetchone()[0]
                    == "running"
                ),
                checkpoint_store=store,
            )
        assert not isinstance(caught.value, ProviderNetworkError)
        assert model.calls == 1
        usage = store.get_budget_usage()
        assert usage["model_call_count"] == 1
        assert usage["usage_unknown_count"] == 1
    finally:
        conn.close()


def test_durable_section_text_completion_reuses_committed_response(monkeypatch):
    class FakeLlm:
        provider = "fake"
        model = "section"

        def __init__(self):
            self.calls = 0

        def complete_text(self, messages, **kwargs):
            del messages, kwargs
            self.calls += 1
            return LLMTextCompletion(
                content='{"heading":"开场","prose":"固定正文","chart_refs":[]}',
                provider=self.provider,
                model=self.model,
                finish_reason="stop",
                usage={"input_tokens": 20, "output_tokens": 10},
            )

    class FakeConfigured:
        provider_id = "fake:section"

        def __init__(self, llm):
            self.llm = llm

    conn, store = _report_runtime_store()
    llm = FakeLlm()
    monkeypatch.setattr(
        ai_agent_v2_service,
        "ConfiguredNativeToolModel",
        lambda _budget=None: FakeConfigured(llm),
    )
    kwargs = {
        "system_prompt": "system",
        "user_content": "section",
        "temperature": 0.35,
        "max_tokens": 4096,
        "thinking": False,
        "checkpoint_store": store,
        "call_id": "report:section:opening:attempt:1",
        "step_id": "report:section:opening",
        "prompt_version": report_agent.REPORT_SECTION_PROMPT_VERSION,
    }
    try:
        first = report_agent._durable_text_completion(**kwargs)
        replayed = report_agent._durable_text_completion(**kwargs)
        usage = store.get_budget_usage()
    finally:
        conn.close()

    assert first == replayed
    assert llm.calls == 1
    assert usage["model_call_count"] == 1
    assert usage["input_tokens"] == 20


def test_durable_section_replays_committed_response_after_step_budget_exhaustion(
    monkeypatch,
):
    """Budget exhaustion blocks new work, not a pure read of committed output."""

    import backend.core.config as runtime_config

    conn, store = _report_runtime_store()
    call_id = "report:section:committed-at-step-cap:attempt:1"
    step_id = "report:section:committed-at-step-cap"
    store.prepare_model_request(
        call_id=call_id,
        step_id=step_id,
        payload={
            "messages": [{"role": "user", "content": "frozen"}],
            "tool_schemas": [],
            "provider_id": "original:model",
            "parameters": {
                "temperature": 0.2,
                "max_output_tokens": 512,
                "thinking": False,
            },
            "prompt_version": report_agent.REPORT_SECTION_PROMPT_VERSION,
        },
        max_steps=runtime_config.AI_AGENT_MAX_STEPS + 12,
    )
    dispatch_id = store.reserve_model_dispatch(
        call_id=call_id,
        step_id=step_id,
        provider_id="original:model",
        max_model_calls=runtime_config.AI_AGENT_MAX_STEPS + 12,
    )
    store.commit_model_response(
        call_id=call_id,
        step_id=step_id,
        payload={
            "content": '{"heading":"开场","prose":"已提交正文","chart_refs":[]}',
            "tool_calls": [],
            "finish_reason": "stop",
            "usage": {"input_tokens": 9, "output_tokens": 4},
            "provider_id": "original:model",
            "attempts": [],
        },
        elapsed_ms=10,
        attempt_count=1,
        successful_dispatch_id=dispatch_id,
    )
    conn.execute(
        """UPDATE ai_runtime_budget_usage
           SET step_count=?, model_call_count=?, active_elapsed_ms=300000
           WHERE task_id='report-v6' AND generation=1""",
        (
            runtime_config.AI_AGENT_MAX_STEPS + 12,
            runtime_config.AI_AGENT_MAX_STEPS + 12,
        ),
    )
    conn.commit()

    def unexpected_model(_budget=None):
        raise AssertionError("committed response replay must not configure a provider")

    monkeypatch.setattr(
        ai_agent_v2_service,
        "ConfiguredNativeToolModel",
        unexpected_model,
    )
    try:
        replayed = report_agent._durable_text_completion(
            system_prompt="changed system",
            user_content="changed request",
            temperature=0.9,
            max_tokens=4096,
            thinking=True,
            checkpoint_store=store,
            call_id=call_id,
            step_id=step_id,
            prompt_version=report_agent.REPORT_SECTION_PROMPT_VERSION,
        )
        usage = store.get_budget_usage()
        with pytest.raises(PersistentBudgetExceededError):
            report_agent._durable_text_completion(
                system_prompt="new system",
                user_content="new request",
                temperature=0.2,
                max_tokens=512,
                thinking=False,
                checkpoint_store=store,
                call_id="report:section:new-work-at-cap:attempt:1",
                step_id="report:section:new-work-at-cap",
                prompt_version=report_agent.REPORT_SECTION_PROMPT_VERSION,
            )
    finally:
        conn.close()

    assert replayed is not None
    assert "已提交正文" in replayed.content
    assert usage["step_count"] == runtime_config.AI_AGENT_MAX_STEPS + 12
    assert usage["model_call_count"] == runtime_config.AI_AGENT_MAX_STEPS + 12
    assert usage["active_elapsed_ms"] == 300000


def test_durable_section_stops_retry_after_persisted_cancellation(monkeypatch):
    conn, store = _report_runtime_store()

    class CancellingLlm:
        provider = "fake"
        model = "section"

        def __init__(self):
            self.calls = 0

        def complete_text(self, messages, **kwargs):
            del messages, kwargs
            self.calls += 1
            conn.execute("UPDATE ai_task_runs SET status='cancelled' WHERE task_id='report-v6'")
            conn.commit()
            raise ProviderNetworkError("fake", "retryable failure after cancellation")

    class FakeConfigured:
        provider_id = "fake:section"

        def __init__(self, llm):
            self.llm = llm

    llm = CancellingLlm()
    monkeypatch.setattr(
        ai_agent_v2_service,
        "ConfiguredNativeToolModel",
        lambda _budget=None: FakeConfigured(llm),
    )
    try:
        with pytest.raises(Exception) as caught:
            report_agent._durable_text_completion(
                system_prompt="system",
                user_content="section",
                temperature=0.35,
                max_tokens=4096,
                thinking=False,
                checkpoint_store=store,
                call_id="report:section:cancelled:attempt:1",
                step_id="report:section:cancelled",
                prompt_version=report_agent.REPORT_SECTION_PROMPT_VERSION,
                should_continue=lambda: (
                    conn.execute(
                        "SELECT status FROM ai_task_runs WHERE task_id='report-v6'"
                    ).fetchone()[0]
                    == "running"
                ),
            )
        assert not isinstance(caught.value, ProviderNetworkError)
        assert llm.calls == 1
        usage = store.get_budget_usage()
        assert usage["model_call_count"] == 1
        assert usage["usage_unknown_count"] == 1
        assert store.get_committed_model_response("report:section:cancelled:attempt:1") is None
    finally:
        conn.close()


def test_durable_section_dispatches_immutable_stored_request(monkeypatch):
    conn, store = _report_runtime_store()
    store.prepare_model_request(
        call_id="report:section:immutable:attempt:1",
        step_id="report:section:immutable",
        payload={
            "messages": [
                {"role": "system", "content": "ORIGINAL SYSTEM"},
                {"role": "user", "content": "ORIGINAL REQUEST"},
            ],
            "tool_schemas": [],
            "provider_id": "fake:section",
            "parameters": {
                "temperature": 0.11,
                "max_output_tokens": 777,
                "thinking": True,
            },
            "prompt_version": "old-prompt-v1",
        },
        max_steps=20,
    )

    class CapturingLlm:
        provider = "fake"
        model = "section"

        def __init__(self):
            self.calls: list[tuple[list[dict], dict]] = []

        def complete_text(self, messages, **kwargs):
            self.calls.append((messages, kwargs))
            return LLMTextCompletion(
                content='{"heading":"原始请求","prose":"已恢复。","chart_refs":[]}',
                provider=self.provider,
                model=self.model,
                finish_reason="stop",
                usage={"input_tokens": 8, "output_tokens": 4},
            )

    class FakeConfigured:
        provider_id = "fake:section"

        def __init__(self, llm):
            self.llm = llm

    llm = CapturingLlm()
    monkeypatch.setattr(
        ai_agent_v2_service,
        "ConfiguredNativeToolModel",
        lambda _budget=None: FakeConfigured(llm),
    )
    try:
        completion = report_agent._durable_text_completion(
            system_prompt="NEW SYSTEM",
            user_content="CHANGED REQUEST",
            temperature=0.99,
            max_tokens=4096,
            thinking=False,
            checkpoint_store=store,
            call_id="report:section:immutable:attempt:1",
            step_id="report:section:immutable",
            prompt_version=report_agent.REPORT_SECTION_PROMPT_VERSION,
        )
        descriptor = next(
            event["payload"]
            for event in store.list_events()
            if event["event_type"] == "model_request_started"
        )
    finally:
        conn.close()

    assert completion is not None
    assert len(llm.calls) == 1
    sent_messages, sent_kwargs = llm.calls[0]
    assert sent_messages == descriptor["messages"]
    assert sent_messages[0]["content"] == "ORIGINAL SYSTEM"
    assert sent_messages[1]["content"] == "ORIGINAL REQUEST"
    assert sent_kwargs["temperature"] == 0.11
    assert sent_kwargs["max_tokens"] == 777
    assert sent_kwargs["thinking"] is True


def test_durable_section_rejects_unavailable_stored_provider(monkeypatch):
    conn, store = _report_runtime_store()
    store.prepare_model_request(
        call_id="report:section:provider-mismatch:attempt:1",
        step_id="report:section:provider-mismatch",
        payload={
            "messages": [{"role": "user", "content": "original"}],
            "tool_schemas": [],
            "provider_id": "retired:model",
            "parameters": {"temperature": 0.1, "max_output_tokens": 512},
            "prompt_version": "old-prompt-v1",
        },
        max_steps=20,
    )

    class UnexpectedLlm:
        provider = "current"
        model = "model"

        def complete_text(self, messages, **kwargs):
            raise AssertionError((messages, kwargs))

    class FakeConfigured:
        provider_id = "current:model"

        def __init__(self):
            self.llm = UnexpectedLlm()

    monkeypatch.setattr(
        ai_agent_v2_service,
        "ConfiguredNativeToolModel",
        lambda _budget=None: FakeConfigured(),
    )
    try:
        with pytest.raises(IncompatibleModelRequestError, match="当前不可用"):
            report_agent._durable_text_completion(
                system_prompt="new system",
                user_content="new request",
                temperature=0.9,
                max_tokens=4096,
                thinking=False,
                checkpoint_store=store,
                call_id="report:section:provider-mismatch:attempt:1",
                step_id="report:section:provider-mismatch",
                prompt_version=report_agent.REPORT_SECTION_PROMPT_VERSION,
            )
        assert store.get_budget_usage()["model_call_count"] == 0
    finally:
        conn.close()
