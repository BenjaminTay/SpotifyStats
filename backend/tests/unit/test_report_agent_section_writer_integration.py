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
    max_tokens_seen: list[int] = []

    def complete(*_args, **kwargs):
        nonlocal calls
        with lock:
            calls += 1
            number = calls
            max_tokens_seen.append(int(kwargs["max_tokens"]))
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
    assert max_tokens_seen == [4096] * 6
    assert len(metrics.provider_calls) == 6
    assert all(item["provider"] == "deepseek" for item in metrics.provider_calls)


def test_report_agent_strips_unsupported_numeric_sentence_before_accepting(monkeypatch):
    def complete(*_args, **_kwargs):
        return LLMTextCompletion(
            content=json.dumps(
                {
                    "heading": "证据章节",
                    "prose": "这是基于给定证据的稳定观察。" * 8 + "999 次没有证据支持。",
                    "chart_refs": [],
                    "evidence_refs": ["yearly_overview"],
                },
                ensure_ascii=False,
            ),
            provider="deepseek",
            model="deepseek-v4-flash",
            finish_reason="stop",
        )

    monkeypatch.setattr(ai_insights_service, "_llm_text_completion", complete)
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
        runtime_metrics=ReportRuntimeMetrics(),
        emit_event=None,
    )

    assert metadata["model_accepted_count"] == 6
    assert metadata["fallback_count"] == 0
    assert all("999" not in section["prose"] for section in sections)


def test_report_agent_routes_resume_checkpoints_to_section_writer(monkeypatch):
    resume_sections = [{"section_id": "section_0", "status": "validated"}]
    commits: list[str] = []
    observed: dict[str, object] = {}
    fallbacks = [
        {
            "id": f"section_{index}",
            "role": "opening",
            "heading": f"默认章节 {index}",
            "deck": "",
            "prose": "确定性回退正文。" * 80,
            "chart_refs": [],
            "evidence_refs": [],
        }
        for index in range(6)
    ]

    monkeypatch.setattr(
        report_agent,
        "_native_report_research",
        lambda **_kwargs: ("研究摘要", []),
    )

    def write_sections(**kwargs):
        observed.update(kwargs)
        return fallbacks, {"model_accepted_count": 1, "fallback_count": 0}

    monkeypatch.setattr(report_agent, "_write_sections_v2", write_sections)
    monkeypatch.setattr(
        report_agent,
        "audit_report_sections",
        lambda sections, **_kwargs: (
            sections,
            [
                {"section_index": index, "status": "pass", "issues": []}
                for index in range(len(sections))
            ],
            [],
        ),
    )

    result = report_agent.run_report_agent(
        year=2025,
        is_partial_year=False,
        end_date="2025-12-31",
        min_ms=30000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=True,
        max_merge_gap_minutes=None,
        chart_data={},
        chart_specs=[],
        research_context={},
        fallback_sections=fallbacks,
        resume_sections=resume_sections,
        on_section_committed=commits.append,
    )

    assert len(result["sections"]) == 6
    assert observed["resume_sections"] is resume_sections
    assert observed["on_section_committed"] == commits.append


def test_report_section_resume_reuses_later_committed_retry_without_provider_call(monkeypatch):
    fallbacks = [
        {
            "id": f"section_{index}",
            "role": "opening",
            "heading": f"默认章节 {index}",
            "deck": "",
            "prose": "确定性回退正文。" * 80,
            "chart_refs": [],
            "evidence_refs": [],
        }
        for index in range(6)
    ]

    class LaterRetryStore:
        def __init__(self):
            self.lookups: list[str] = []
            self.budget_checks = 0

        def get_committed_model_response(self, call_id):
            self.lookups.append(call_id)
            if call_id.endswith(":attempt:2"):
                section_id = call_id.split(":")[2]
                return {
                    "content": json.dumps(
                        {
                            "heading": section_id,
                            "prose": "已提交的第二次模型响应。" * 40,
                            "chart_refs": [],
                            "evidence_refs": [],
                        },
                        ensure_ascii=False,
                    ),
                    "finish_reason": "stop",
                    "usage": {"input_tokens": 10, "output_tokens": 10},
                    "provider_id": "fake:replayed",
                }
            return None

        def assert_budget_available(self, **_kwargs):
            self.budget_checks += 1

    store = LaterRetryStore()
    monkeypatch.setattr(
        report_agent,
        "audit_report_sections",
        lambda sections, **_kwargs: (
            sections,
            [{"section_index": 0, "status": "pass", "issues": []}],
            [],
        ),
    )
    monkeypatch.setattr(
        ai_insights_service,
        "_llm_text_completion",
        lambda *_args, **_kwargs: pytest.fail("committed retry must not call provider"),
    )

    sections, metadata = report_agent._write_sections_v2(
        fallback_sections=fallbacks,
        research_text="固定研究",
        all_tool_results=[],
        chart_data={},
        chart_specs=[],
        year=2025,
        end_date="2025-12-31",
        runtime_metrics=None,
        emit_event=None,
        checkpoint_store=store,
    )

    assert len(sections) == 6
    assert metadata["model_accepted_count"] == 6
    assert store.budget_checks == 0
    assert all(
        any(f"report:section:section_{index}:attempt:2" == item for item in store.lookups)
        for index in range(6)
    )


def test_report_agent_reuses_research_without_new_model_or_tool_calls(monkeypatch):
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
    checkpoint = {
        "research_summary": "已持久化研究",
        "evidence": [{"_tool_name": "yearly_overview", "result_summary": "播放 3 次"}],
    }
    committed: list[object] = []
    monkeypatch.setattr(
        report_agent,
        "_native_report_research",
        lambda **_kwargs: pytest.fail("恢复时不应重新调用研究模型"),
    )
    monkeypatch.setattr(
        report_agent,
        "_write_sections_v2",
        lambda **kwargs: (fallbacks, {"research": kwargs["research_text"]}),
    )
    monkeypatch.setattr(
        report_agent,
        "audit_report_sections",
        lambda sections, **_kwargs: (
            sections,
            [
                {"section_index": index, "status": "pass", "issues": []}
                for index in range(len(sections))
            ],
            [],
        ),
    )

    result = report_agent.run_report_agent(
        year=2025,
        is_partial_year=False,
        end_date="2025-12-31",
        min_ms=30000,
        music_only=True,
        merge_enabled=True,
        dynamic_threshold=True,
        max_merge_gap_minutes=None,
        chart_data={},
        chart_specs=[],
        research_context={},
        fallback_sections=fallbacks,
        resume_research=checkpoint,
        on_research_committed=lambda *_args: committed.append(True),
    )

    assert result["research_summary"] == "已持久化研究"
    assert result["evidence"] == checkpoint["evidence"]
    assert committed == []
