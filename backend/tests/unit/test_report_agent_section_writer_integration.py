from __future__ import annotations

import json
from threading import Lock

import pytest

from backend.domains.ai_reports import report_agent
from backend.domains.ai_reports.runtime_metrics import ReportRuntimeMetrics
from backend.providers.llm.client import LLMTextCompletion
from backend.services import ai_insights_service

pytestmark = pytest.mark.unit


def test_report_agent_writes_six_sections_and_records_provider_metrics(monkeypatch):
    lock = Lock()
    calls = 0

    def complete(*_args, **_kwargs):
        nonlocal calls
        with lock:
            calls += 1
            number = calls
        return LLMTextCompletion(
            content=json.dumps(
                {
                    "heading": f"章节 {number}",
                    "prose": "这是完全基于给定证据撰写的章节。" * 40,
                    "chart_refs": [],
                    "evidence_refs": ["yearly_overview"],
                },
                ensure_ascii=False,
            ),
            provider="deepseek",
            model="deepseek-chat",
            finish_reason="stop",
            usage={"prompt_tokens": 100, "completion_tokens": 200},
            elapsed_ms=15,
        )

    monkeypatch.setattr(ai_insights_service, "_llm_text_completion", complete)
    monkeypatch.setattr(
        report_agent,
        "audit_report_sections",
        lambda sections, **_kwargs: (
            sections,
            [{"section_index": 0, "status": "pass", "issues": []}],
            [],
        ),
    )
    metrics = ReportRuntimeMetrics()
    fallbacks = [
        {
            "id": f"section_{index}",
            "role": "opening",
            "heading": f"默认章节 {index}",
            "deck": "",
            "prose": "确定性回退正文。" * 80,
            "chart_refs": [],
            "evidence_refs": ["yearly_overview"],
        }
        for index in range(6)
    ]

    sections, metadata = report_agent._write_sections_v2(
        fallback_sections=fallbacks,
        research_text="研究摘要",
        all_tool_results=[
            {
                "_tool_name": "yearly_overview",
                "result_summary": "2025 年共播放 88 次",
                "data": {"hero": {"total_plays": 88}},
            }
        ],
        chart_data={},
        chart_specs=[],
        year=2025,
        end_date="2025-12-31",
        runtime_metrics=metrics,
        emit_event=None,
    )

    assert len(sections) == 6
    assert metadata["model_accepted_count"] == 6
    assert metadata["fallback_count"] == 0
    assert calls == 6
    assert len(metrics.provider_calls) == 6
    assert all(item["provider"] == "deepseek" for item in metrics.provider_calls)
