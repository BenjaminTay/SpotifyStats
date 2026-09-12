from __future__ import annotations

import json

from backend.domains.ai_reports import report_agent
from backend.providers.llm.client import LLMCompletion, LLMToolCall
from backend.services import ai_agent_v2_service


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
        lambda: model,
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
