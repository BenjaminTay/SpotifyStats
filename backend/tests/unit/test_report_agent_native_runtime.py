from __future__ import annotations

import json

from pydantic import BaseModel

from backend.domains.ai_agent.tool_registry import (
    AgentToolDefinition,
    AgentToolRegistry,
    AgentToolResult,
)
from backend.domains.ai_reports import report_agent
from backend.providers.llm.client import LLMCompletion, LLMToolCall
from backend.services import ai_agent_v2_service


class ReportStatsParams(BaseModel):
    period: str = "lifetime"
    start_date: str | None = None
    end_date: str | None = None
    min_ms: int = 30000


def test_report_research_uses_native_tool_observation_loop(monkeypatch):
    registry = AgentToolRegistry()
    registry.register(
        AgentToolDefinition(
            name="analysis_stats",
            description="Read yearly stats",
            read_only=True,
            params_model=ReportStatsParams,
            handler=lambda params: AgentToolResult(
                data={
                    "period": {
                        "start_date": params.start_date,
                        "end_date": params.end_date,
                    },
                    "summary": {"total_plays": 88},
                },
                result_summary="plays=88",
                source_range=f"{params.start_date}..{params.end_date}",
            ),
        )
    )

    class FakeNativeModel:
        def __init__(self):
            self.calls = 0
            self.messages = []

        def complete(self, messages, tools, *, thinking):
            self.calls += 1
            self.messages = messages
            if self.calls == 1:
                return LLMCompletion(
                    tool_calls=[
                        LLMToolCall(
                            call_id="report-call-1",
                            name="analysis_stats",
                            arguments={},
                        )
                    ]
                )
            return LLMCompletion(content="年度研究完成：共播放 88 次。")

    model = FakeNativeModel()
    monkeypatch.setattr(report_agent, "get_default_registry", lambda: registry)
    monkeypatch.setattr(
        ai_agent_v2_service,
        "ConfiguredNativeToolModel",
        lambda: model,
    )

    research, evidence = report_agent._native_report_research(
        planner_prompt="research",
        planner_user="yearly",
        base_filters={"min_ms": 30000},
        year=2025,
        end_date="2025-12-31",
        emit_event=None,
    )

    assert research == "年度研究完成：共播放 88 次。"
    assert evidence[0]["status"] == "ok"
    assert evidence[0]["_params"]["period"] == "custom"
    assert evidence[0]["_params"]["start_date"] == "2025-01-01"
    assert evidence[0]["_params"]["end_date"] == "2025-12-31"
    tool_messages = [message for message in model.messages if message["role"] == "tool"]
    assert len(tool_messages) == 1
    observed = json.loads(tool_messages[0]["content"])
    assert observed["data"]["summary"]["total_plays"] == 88
