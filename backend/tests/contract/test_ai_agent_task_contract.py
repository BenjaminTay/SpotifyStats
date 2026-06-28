from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

import backend.api.ai_tasks as ai_tasks_api
from backend.services import ai_task_service

pytestmark = pytest.mark.contract


class SyncThread:
    def __init__(
        self,
        *,
        target: Callable[..., None],
        args: tuple[Any, ...] = (),
        daemon: bool | None = None,
    ):
        self.target = target
        self.args = args
        self.daemon = daemon

    def start(self) -> None:
        self.target(*self.args)


def test_chat_task_endpoint_uses_static_route_before_task_id(client, monkeypatch):
    observed: dict[str, Any] = {}

    def fake_start_chat_agent_task(request: dict[str, Any]) -> dict[str, Any]:
        observed.update(request)
        return {
            "task_id": "chat-contract",
            "status": "queued",
            "stage": "planning_tools",
            "progress_pct": 0.0,
            "message": "正在规划可用数据工具",
            "result": None,
        }

    monkeypatch.setattr(ai_tasks_api, "start_chat_agent_task", fake_start_chat_agent_task)

    response = client.post(
        "/api/ai/tasks/chat",
        json={
            "question": "我今年晚上都在听什么？",
            "conversation_history": [{"role": "user", "content": "先看今年"}],
            "min_ms": 45000,
            "music_only": False,
            "merge_enabled": False,
            "dynamic_threshold": False,
            "max_merge_gap_minutes": 45,
            "merge_level": 3,
            "thinking_mode": True,
        },
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    assert response.json()["task_id"] == "chat-contract"
    assert response.json()["stage"] == "planning_tools"
    assert observed == {
        "question": "我今年晚上都在听什么？",
        "conversation_history": [{"role": "user", "content": "先看今年"}],
        "min_ms": 45000,
        "music_only": False,
        "merge_enabled": False,
        "dynamic_threshold": False,
        "max_merge_gap_minutes": 45,
        "merge_level": 3,
        "thinking_mode": True,
    }


def test_chat_task_endpoint_rejects_empty_question(client, monkeypatch):
    monkeypatch.setattr(
        ai_tasks_api,
        "start_chat_agent_task",
        lambda request: pytest.fail("invalid chat request must not start a task"),
    )

    response = client.post("/api/ai/tasks/chat", json={"question": ""})

    assert response.status_code == 422
    assert response.headers["x-request-id"]


def test_chat_task_endpoint_rejects_filter_values_outside_tool_bounds(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        ai_tasks_api,
        "start_chat_agent_task",
        lambda request: pytest.fail("invalid chat request must not start a task"),
    )

    response = client.post(
        "/api/ai/tasks/chat",
        json={"question": "分析一下", "min_ms": 3_600_001},
    )

    assert response.status_code == 422
    assert response.headers["x-request-id"]


def test_chat_agent_task_runs_sync_and_persists_events_and_tool_trace(
    client,
    monkeypatch,
):
    import backend.services.ai_agent_service as agent_service

    llm_calls: list[tuple[str, str, float]] = []

    def fake_llm_chat(system_prompt: str, user_content: str, temperature: float = 0.3):
        llm_calls.append((system_prompt, user_content, temperature))
        if len(llm_calls) == 1:
            return (
                '[{"tool_name":"wrapped_yearly","params":{"year":2026}},'
                '{"tool_name":"listening_hours","params":{"view":"late_night_ratio"}}]'
            )
        return "你 2026 年的夜间聆听占比是 12.5%，年度播放 77 次。"

    def fake_dispatch_tool(tool_name: str, params: dict[str, Any] | None = None):
        assert tool_name in {"wrapped_yearly", "listening_hours"}
        if tool_name == "wrapped_yearly":
            return {
                "tool_name": tool_name,
                "params_summary": "year=2026",
                "result_summary": "plays=77, hours=9.5",
                "source_range": "2026",
                "data": {"year": 2026, "summary": {"total_plays": 77}},
            }
        return {
            "tool_name": tool_name,
            "params_summary": "view=late_night_ratio",
            "result_summary": "items=1",
            "source_range": "late_night_ratio",
            "data": [{"year": 2026, "rate": 12.5}],
        }

    monkeypatch.setattr(ai_task_service.threading, "Thread", SyncThread)
    monkeypatch.setattr(agent_service.ai_insights_service, "_llm_chat", fake_llm_chat)
    monkeypatch.setattr(agent_service, "dispatch_tool", fake_dispatch_tool)

    create_response = client.post(
        "/api/ai/tasks/chat",
        json={"question": "我今年夜间听歌情况如何？", "merge_level": 2},
    )

    assert create_response.status_code == 200
    assert create_response.json()["stage"] == "queued"
    task_id = create_response.json()["task_id"]

    status_response = client.get(f"/api/ai/tasks/{task_id}")
    events_response = client.get(f"/api/ai/tasks/{task_id}/events")

    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "done"
    assert status_payload["stage"] == "done"
    assert (
        status_payload["result"]["answer"] == "你 2026 年的夜间聆听占比是 12.5%，年度播放 77 次。"
    )
    assert status_payload["result"]["tool_call_count"] == 2

    events_payload = events_response.json()
    assert events_payload["found"] is True
    stages = [event["stage"] for event in events_payload["events"]]
    assert stages[0] == "queued"
    assert sum(1 for event in events_payload["events"] if event["stage"] == "planning_tools") == 2
    assert "planning_tools" in stages
    assert "calling_tool" in stages
    assert "calling_llm" in stages
    assert "done" in stages
    tool_calls = events_payload["tool_calls"]
    assert [call["tool_name"] for call in tool_calls] == ["wrapped_yearly", "listening_hours"]
    assert [call["status"] for call in tool_calls] == ["done", "done"]
    assert tool_calls[0]["params_summary"] == "year=2026"
    assert tool_calls[0]["result_summary"] == "plays=77, hours=9.5"
    assert tool_calls[0]["source_range"] == "2026"
    assert tool_calls[1]["params_summary"] == "view=late_night_ratio"
    assert len(llm_calls) == 2


def test_chat_agent_thinking_mode_uses_deeper_fallback_and_review_stage(
    client,
    monkeypatch,
):
    import backend.services.ai_agent_service as agent_service

    llm_calls: list[tuple[str, str, float]] = []
    dispatched_tools: list[str] = []

    def fake_llm_chat(system_prompt: str, user_content: str, temperature: float = 0.3):
        llm_calls.append((system_prompt, user_content, temperature))
        if len(llm_calls) == 1:
            return "not json"
        return "结论：这是基于多组只读数据交叉核对后的回答。\n\n依据：年度概览、排行和时间分布。"

    def fake_dispatch_tool(tool_name: str, params: dict[str, Any] | None = None):
        dispatched_tools.append(tool_name)
        return {
            "tool_name": tool_name,
            "params_summary": ",".join(sorted((params or {}).keys())),
            "result_summary": f"{tool_name} result",
            "source_range": "test-range",
            "data": {"tool": tool_name, "ok": True},
        }

    monkeypatch.setattr(ai_task_service.threading, "Thread", SyncThread)
    monkeypatch.setattr(agent_service.ai_insights_service, "_llm_chat", fake_llm_chat)
    monkeypatch.setattr(agent_service, "dispatch_tool", fake_dispatch_tool)

    create_response = client.post(
        "/api/ai/tasks/chat",
        json={"question": "深度分析一下我今年的听歌变化", "thinking_mode": True},
    )

    assert create_response.status_code == 200
    task_id = create_response.json()["task_id"]

    events_response = client.get(f"/api/ai/tasks/{task_id}/events")
    status_response = client.get(f"/api/ai/tasks/{task_id}")

    assert status_response.status_code == 200
    assert status_response.json()["status"] == "done"
    assert status_response.json()["result"]["tool_call_count"] >= 3

    events_payload = events_response.json()
    stages = [event["stage"] for event in events_payload["events"]]
    assert "reviewing_evidence" in stages
    assert len(events_payload["tool_calls"]) >= 3
    assert len(dispatched_tools) >= 3
    assert "analysis_stats" in dispatched_tools
    assert "analysis_charts" in dispatched_tools
    assert "thinking_mode" in llm_calls[0][1]


def test_chat_agent_retries_final_answer_when_it_contradicts_found_album_evidence(
    client,
    monkeypatch,
):
    import backend.services.ai_agent_service as agent_service

    llm_calls: list[tuple[str, str, float]] = []

    def fake_llm_chat(system_prompt: str, user_content: str, temperature: float = 0.3):
        llm_calls.append((system_prompt, user_content, temperature))
        if len(llm_calls) == 1:
            return (
                '[{"tool_name":"entity_stats","params":{"entity":"album","album_name":"GUTS"}},'
                '{"tool_name":"entity_stats","params":{"entity":"album",'
                '"album_name":"The Life of a Showgirl"}},'
                '{"tool_name":"billboard_entity_detail","params":{"entity":"album",'
                '"album_name":"The Life of a Showgirl"}}]'
            )
        if len(llm_calls) == 2:
            return (
                "**结论**\n"
                "只能提供 GUTS 的播放情况，缺少 The Life of a Showgirl 的播放数据，"
                "也没有 billboard 榜单成绩。"
            )
        assert "上一版回答与工具证据矛盾" in user_content
        assert "The Life of a Showgirl" in user_content
        assert "plays=1637" in user_content
        return "**结论**\nThe Life of a Showgirl 的短期热度更强；GUTS 的长期累计榜单资历更强。"

    def fake_dispatch_tool(tool_name: str, params: dict[str, Any] | None = None):
        album_name = str((params or {}).get("album_name") or "")
        if tool_name == "entity_stats" and album_name == "GUTS":
            return {
                "tool_name": tool_name,
                "params_summary": "entity=album, album_name=GUTS",
                "result_summary": "found=true, plays=1749, hours=95.6",
                "source_range": "2022-07-01..2026-06-23",
                "data": {"found": True, "summary": {"total_plays": 1749}},
            }
        if tool_name == "entity_stats" and album_name == "The Life of a Showgirl":
            return {
                "tool_name": tool_name,
                "params_summary": "entity=album, album_name=The Life of a Showgirl",
                "result_summary": "found=true, plays=1637, hours=96",
                "source_range": "2022-07-01..2026-06-23",
                "data": {"found": True, "summary": {"total_plays": 1637}},
            }
        return {
            "tool_name": tool_name,
            "params_summary": "entity=album, album_name=The Life of a Showgirl",
            "result_summary": (
                "found=true, album=The Life of a Showgirl, weeks=34, "
                "peak=1, no1_weeks=13, power_score=10087"
            ),
            "source_range": "all_years",
            "data": {"found": True, "chart_summary": {"weeks_on_chart": 34}},
        }

    monkeypatch.setattr(ai_task_service.threading, "Thread", SyncThread)
    monkeypatch.setattr(agent_service.ai_insights_service, "_llm_chat", fake_llm_chat)
    monkeypatch.setattr(agent_service, "dispatch_tool", fake_dispatch_tool)

    create_response = client.post(
        "/api/ai/tasks/chat",
        json={
            "question": (
                "从播放次数和billboard榜单成绩来看，我对GUTS和"
                "The Life of a Showgirl这两张专辑的喜爱程度哪张专辑更甚？"
            ),
            "thinking_mode": True,
        },
    )

    assert create_response.status_code == 200
    task_id = create_response.json()["task_id"]
    status_payload = client.get(f"/api/ai/tasks/{task_id}").json()

    assert status_payload["status"] == "done"
    assert "短期热度更强" in status_payload["result"]["answer"]
    assert "缺少 The Life of a Showgirl" not in status_payload["result"]["answer"]
    assert status_payload["result"]["answer_retried"] is True
    assert len(llm_calls) == 3


def test_chat_agent_adds_one_coverage_followup_round_for_missing_billboard(
    client,
    monkeypatch,
):
    import backend.services.ai_agent_service as agent_service

    llm_calls: list[tuple[str, str, float]] = []
    dispatched: list[tuple[str, dict[str, Any]]] = []

    def fake_llm_chat(system_prompt: str, user_content: str, temperature: float = 0.3):
        llm_calls.append((system_prompt, user_content, temperature))
        if len(llm_calls) == 1:
            return (
                '[{"tool_name":"entity_stats","params":{"entity":"album","album_name":"GUTS"}},'
                '{"tool_name":"billboard_entity_detail","params":{"entity":"album",'
                '"album_name":"GUTS"}},'
                '{"tool_name":"entity_stats","params":{"entity":"album",'
                '"album_name":"The Life of a Showgirl"}}]'
            )
        return "GUTS 的累计更强，The Life of a Showgirl 的近期榜单表现也已补查。"

    def fake_dispatch_tool(tool_name: str, params: dict[str, Any] | None = None):
        params = params or {}
        dispatched.append((tool_name, dict(params)))
        album_name = str(params.get("album_name") or "")
        if tool_name == "entity_stats":
            plays = 1749 if album_name == "GUTS" else 1637
            return {
                "tool_name": tool_name,
                "params_summary": f"entity=album, album_name={album_name}",
                "result_summary": f"found=true, plays={plays}",
                "source_range": "lifetime",
                "data": {
                    "found": True,
                    "album_name": album_name,
                    "summary": {"total_plays": plays},
                },
            }
        return {
            "tool_name": tool_name,
            "params_summary": f"entity=album, album_name={album_name}",
            "result_summary": f"found=true, album={album_name}, weeks=12, peak=1",
            "source_range": "all_years",
            "data": {
                "found": True,
                "album_name": album_name,
                "chart_summary": {"peak_position": 1},
            },
        }

    monkeypatch.setattr(ai_task_service.threading, "Thread", SyncThread)
    monkeypatch.setattr(agent_service.ai_insights_service, "_llm_chat", fake_llm_chat)
    monkeypatch.setattr(agent_service, "dispatch_tool", fake_dispatch_tool)

    create_response = client.post(
        "/api/ai/tasks/chat",
        json={
            "question": (
                "从播放次数和billboard榜单成绩来看，我对GUTS和"
                "The Life of a Showgirl这两张专辑的喜爱程度哪张专辑更甚？"
            )
        },
    )

    assert create_response.status_code == 200
    task_id = create_response.json()["task_id"]
    status_payload = client.get(f"/api/ai/tasks/{task_id}").json()
    events_payload = client.get(f"/api/ai/tasks/{task_id}/events").json()

    assert status_payload["status"] == "done"
    assert status_payload["result"]["tool_call_count"] == 4
    assert dispatched[-1] == (
        "billboard_entity_detail",
        {"entity": "album", "album_name": "The Life of a Showgirl"},
    )
    assert "reviewing_coverage" in [event["stage"] for event in events_payload["events"]]
    assert [call["tool_name"] for call in events_payload["tool_calls"]] == [
        "entity_stats",
        "billboard_entity_detail",
        "entity_stats",
        "billboard_entity_detail",
    ]
    assert (
        status_payload["result"]["coverage"]["entities"]["The Life of a Showgirl"][
            "billboard_entity_detail"
        ]
        == "found"
    )
    assert len(llm_calls) == 2


def test_chat_agent_task_marks_error_when_final_llm_is_empty(client, monkeypatch):
    import backend.services.ai_agent_service as agent_service

    llm_call_count = 0

    def sequenced_llm_chat(system_prompt: str, user_content: str, temperature: float = 0.3):
        nonlocal llm_call_count
        del system_prompt, user_content, temperature
        llm_call_count += 1
        if llm_call_count == 1:
            return '[{"tool_name":"analysis_stats","params":{}}]'
        return ""

    monkeypatch.setattr(ai_task_service.threading, "Thread", SyncThread)
    monkeypatch.setattr(agent_service.ai_insights_service, "_llm_chat", sequenced_llm_chat)
    monkeypatch.setattr(
        agent_service,
        "dispatch_tool",
        lambda tool_name, params=None: {
            "tool_name": tool_name,
            "params_summary": "",
            "result_summary": "plays=1",
            "source_range": "lifetime",
            "data": {"summary": {"total_plays": 1}},
        },
    )

    create_response = client.post("/api/ai/tasks/chat", json={"question": "给我一个总结"})

    assert create_response.status_code == 200
    task_id = create_response.json()["task_id"]
    status_payload = client.get(f"/api/ai/tasks/{task_id}").json()
    events_payload = client.get(f"/api/ai/tasks/{task_id}/events").json()

    assert status_payload["status"] == "error"
    assert status_payload["stage"] == "error"
    assert "LLM 未配置或调用失败" in status_payload["message"]
    assert events_payload["events"][-1]["event_type"] == "stage_failed"
    assert events_payload["events"][-1]["stage"] == "error"


def test_chat_agent_task_does_not_append_tool_trace_after_cancel(
    client,
    monkeypatch,
):
    import backend.services.ai_agent_service as agent_service
    from backend.core.db import get_db

    def fake_llm_chat(system_prompt: str, user_content: str, temperature: float = 0.3):
        del system_prompt, user_content, temperature
        return '[{"tool_name":"analysis_stats","params":{}}]'

    def fake_dispatch_tool(tool_name: str, params: dict[str, Any] | None = None):
        del tool_name, params
        conn = get_db(readonly=True)
        try:
            task_id = conn.execute(
                """SELECT task_id FROM ai_task_runs
                   WHERE task_type = 'ai_chat_agent' AND status = 'running'
                   ORDER BY created_at DESC, task_id DESC
                   LIMIT 1"""
            ).fetchone()["task_id"]
        finally:
            conn.close()
        ai_task_service.cancel_task(task_id)
        return {
            "tool_name": "analysis_stats",
            "params_summary": "",
            "result_summary": "plays=1",
            "source_range": "lifetime",
            "data": {"summary": {"total_plays": 1}},
        }

    monkeypatch.setattr(ai_task_service.threading, "Thread", SyncThread)
    monkeypatch.setattr(agent_service.ai_insights_service, "_llm_chat", fake_llm_chat)
    monkeypatch.setattr(agent_service, "dispatch_tool", fake_dispatch_tool)

    create_response = client.post("/api/ai/tasks/chat", json={"question": "给我一个总结"})

    assert create_response.status_code == 200
    task_id = create_response.json()["task_id"]
    status_payload = client.get(f"/api/ai/tasks/{task_id}").json()
    events_payload = client.get(f"/api/ai/tasks/{task_id}/events").json()

    assert status_payload["status"] == "cancelled"
    assert status_payload["stage"] == "cancelled"
    assert events_payload["tool_calls"] == []
