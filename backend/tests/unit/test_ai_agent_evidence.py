from __future__ import annotations

import json
from typing import Any

import pytest

from backend.services import ai_agent_service

pytestmark = pytest.mark.unit


def test_final_prompt_preserves_each_tool_summary_when_first_tool_data_is_huge() -> None:
    tool_results: list[dict[str, Any]] = [
        {
            "tool_name": "entity_stats",
            "status": "done",
            "params_summary": "entity=album, album_name=GUTS",
            "result_summary": "found=true, plays=1749, hours=95.6",
            "source_range": "2022-07-01..2026-06-23",
            "data": {
                "found": True,
                "summary": {"total_plays": 1749},
                "daily_trend": [{"date": "2026-01-01", "plays": index} for index in range(2000)],
            },
        },
        {
            "tool_name": "entity_stats",
            "status": "done",
            "params_summary": "entity=album, album_name=The Life of a Showgirl",
            "result_summary": "SECOND_ENTITY_PLAYS=1637, hours=96",
            "source_range": "2022-07-01..2026-06-23",
            "data": {"found": True, "summary": {"total_plays": 1637}},
        },
    ]

    content = ai_agent_service._final_user_content(
        {
            "question": (
                "从播放次数和billboard榜单成绩来看，我对GUTS和"
                "The Life of a Showgirl这两张专辑的喜爱程度哪张专辑更甚？"
            ),
            "conversation_history": [],
        },
        tool_results,
    )

    payload = json.loads(content)
    assert payload["tool_results"][0]["result_summary"] == "found=true, plays=1749, hours=95.6"
    assert payload["tool_results"][1]["result_summary"] == "SECOND_ENTITY_PLAYS=1637, hours=96"
    assert "SECOND_ENTITY_PLAYS=1637" in content
    assert "daily_trend" not in content
    assert len(content) < 16000


def test_final_prompt_includes_requested_entity_coverage_manifest() -> None:
    content = ai_agent_service._final_user_content(
        {
            "question": (
                "从播放次数和billboard榜单成绩来看，我对GUTS和"
                "The Life of a Showgirl这两张专辑的喜爱程度哪张专辑更甚？"
            ),
            "conversation_history": [],
        },
        [
            {
                "tool_name": "entity_stats",
                "status": "done",
                "params_summary": "entity=album, album_name=GUTS",
                "result_summary": "found=true, plays=1749, hours=95.6",
                "source_range": "2022-07-01..2026-06-23",
                "data": {"found": True},
            },
            {
                "tool_name": "entity_stats",
                "status": "done",
                "params_summary": "entity=album, album_name=The Life of a Showgirl",
                "result_summary": "found=true, plays=1637, hours=96",
                "source_range": "2022-07-01..2026-06-23",
                "data": {"found": True},
            },
            {
                "tool_name": "billboard_entity_detail",
                "status": "done",
                "params_summary": "entity=album, album_name=The Life of a Showgirl",
                "result_summary": "found=true, album=The Life of a Showgirl, weeks=34, peak=1",
                "source_range": "all_years",
                "data": {"found": True},
            },
        ],
    )

    payload = json.loads(content)
    assert payload["coverage"]["requested_entities"] == ["GUTS", "The Life of a Showgirl"]
    assert payload["coverage"]["entities"]["GUTS"]["entity_stats"] == "found"
    assert payload["coverage"]["entities"]["The Life of a Showgirl"]["entity_stats"] == "found"
    assert (
        payload["coverage"]["entities"]["The Life of a Showgirl"]["billboard_entity_detail"]
        == "found"
    )


def test_tool_call_identity_distinguishes_compare_entity_names() -> None:
    first = ai_agent_service._tool_call_identity(
        {
            "tool_name": "compare_entities",
            "params": {"entity_type": "album", "names": ["GUTS", "SOUR"]},
        }
    )
    second = ai_agent_service._tool_call_identity(
        {
            "tool_name": "compare_entities",
            "params": {"entity_type": "album", "names": ["GUTS", "SOUR", "brat"]},
        }
    )

    assert first != second


def test_chat_agent_retries_when_critic_rejects_external_billboard_claim(monkeypatch) -> None:
    class FakeConn:
        def close(self) -> None:
            pass

    class FakeRepo:
        def __init__(self) -> None:
            self.result: dict[str, Any] | None = None

        def update_run_if_not_terminal(self, **kwargs: Any) -> bool:
            if "result" in kwargs:
                self.result = kwargs["result"]
            return True

        def add_event(self, **kwargs: Any) -> None:
            pass

        def get_run(self, task_id: str) -> dict[str, str]:
            return {"status": "running"}

        def add_tool_call(self, **kwargs: Any) -> None:
            pass

    fake_repo = FakeRepo()
    llm_calls: list[tuple[str, str, float]] = []

    def fake_llm_chat(system_prompt: str, user_content: str, temperature: float = 0.3) -> str:
        llm_calls.append((system_prompt, user_content, temperature))
        if len(llm_calls) == 1:
            return (
                '[{"tool_name":"billboard_entity_detail",'
                '"params":{"entity":"album","album_name":"GUTS"}}]'
            )
        if len(llm_calls) == 2:
            return "GUTS 的 Billboard 市场影响力和商业成绩更强。"
        assert "上一版回答与工具证据矛盾" in user_content
        assert "外部官方 Billboard" in user_content
        return "在你的个人 Billboard 口径里，GUTS 的榜单表现更强。"

    def fake_dispatch_tool(tool_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        assert tool_name == "billboard_entity_detail"
        assert (params or {})["album_name"] == "GUTS"
        return {
            "tool_name": tool_name,
            "params_summary": "entity=album, album_name=GUTS",
            "result_summary": "found=true, album=GUTS, weeks=34, peak=1",
            "source_range": "all_years",
            "data": {
                "found": True,
                "entity": "album",
                "album_name": "GUTS",
                "chart_summary": {"weeks_on_chart": 34, "peak_position": 1},
            },
        }

    monkeypatch.setattr(ai_agent_service, "get_db", lambda readonly=False: FakeConn())
    monkeypatch.setattr(ai_agent_service, "AiTaskRepository", lambda conn: fake_repo)
    monkeypatch.setattr(ai_agent_service.ai_insights_service, "_llm_chat", fake_llm_chat)
    monkeypatch.setattr(ai_agent_service, "dispatch_tool", fake_dispatch_tool)

    ai_agent_service.run_chat_agent_task("task-critic-retry", {"question": "GUTS 的榜单成绩如何？"})

    assert fake_repo.result is not None
    assert fake_repo.result["answer_retried"] is True
    assert fake_repo.result["answer"] == "在你的个人 Billboard 口径里，GUTS 的榜单表现更强。"
    assert any("外部官方 Billboard" in issue for issue in fake_repo.result["validation_issues"])
    assert len(llm_calls) == 3
