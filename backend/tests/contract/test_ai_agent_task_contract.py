from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

import backend.api.ai_tasks as ai_tasks_api
from backend.services import ai_agent_service, ai_task_service

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


def test_chat_agent_prompts_include_project_context(monkeypatch) -> None:
    class FakeConn:
        def close(self) -> None:
            pass

    class FakeRepo:
        def __init__(self) -> None:
            self.result: dict[str, object] | None = None

        def update_run_if_not_terminal(self, **kwargs):
            if "result" in kwargs:
                self.result = kwargs["result"]
            return True

        def add_event(self, **kwargs):
            pass

        def get_run(self, task_id):
            return {"status": "running"}

        def add_tool_call(self, **kwargs):
            pass

    fake_repo = FakeRepo()
    llm_calls: list[tuple[str, str, float]] = []

    def fake_llm_chat(system_prompt: str, user_content: str, temperature: float = 0.3) -> str:
        llm_calls.append((system_prompt, user_content, temperature))
        if len(llm_calls) == 1:
            return '[{"tool_name":"analysis_stats","params":{"period":"this_year"}}]'
        return "今年你听歌很多。"

    def fake_dispatch_tool(tool_name, params=None):
        return {
            "tool_name": tool_name,
            "params_summary": "period=this_year",
            "result_summary": "plays=100",
            "source_range": "2026-01-01..2026-06-29",
            "data": {
                "period": {"period": "this_year"},
                "summary": {"total_plays": 100},
            },
        }

    monkeypatch.setattr(ai_agent_service, "get_db", lambda readonly=False: FakeConn())
    monkeypatch.setattr(ai_agent_service, "AiTaskRepository", lambda conn: fake_repo)
    monkeypatch.setattr(ai_agent_service.ai_insights_service, "_llm_chat", fake_llm_chat)
    monkeypatch.setattr(ai_agent_service, "dispatch_tool", fake_dispatch_tool)

    ai_agent_service.run_chat_agent_task("task-project-context", {"question": "我今年听歌怎么样？"})

    assert len(llm_calls) >= 2
    planner_prompt = llm_calls[0][0]
    final_prompt = llm_calls[1][0]
    assert "spotify-stats-project-context-v1" in planner_prompt
    assert "Tool Playbook" in planner_prompt
    assert "不要编造工具、SQL、URL" in planner_prompt
    assert "spotify-stats-project-context-v1" in final_prompt
    assert "Answer Philosophy" in final_prompt
    assert "本地个人 Billboard" in final_prompt
    assert fake_repo.result is not None
    assert fake_repo.result["project_context_version"] == "spotify-stats-project-context-v1"


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
                '[{"tool_name":"analysis_stats","params":{"period":"this_year"}},'
                '{"tool_name":"listening_hours","params":{"view":"late_night_ratio"}}]'
            )
        return "你 2026 年的夜间聆听占比是 12.5%，年度播放 77 次。"

    def fake_dispatch_tool(tool_name: str, params: dict[str, Any] | None = None):
        assert tool_name in {"analysis_stats", "listening_hours"}
        if tool_name == "analysis_stats":
            return {
                "tool_name": tool_name,
                "params_summary": "period=this_year",
                "result_summary": "plays=77, hours=9.5",
                "source_range": "2026",
                "data": {"period": {"period": "this_year"}, "summary": {"total_plays": 77}},
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
    assert "coverage" in status_payload["result"]
    assert "evidence_cards" in status_payload["result"]
    assert "tools" in status_payload["result"]
    assert "question_frame" in status_payload["result"]
    assert "evidence_sufficiency" in status_payload["result"]
    assert "analytical_brief" in status_payload["result"]
    assert "answer_obligations" in status_payload["result"]
    assert isinstance(status_payload["result"]["question_frame"]["family"], str)
    assert "sufficient" in status_payload["result"]["evidence_sufficiency"]
    assert "answer_contract" in status_payload["result"]["analytical_brief"]

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
    assert [call["tool_name"] for call in tool_calls] == ["analysis_stats", "listening_hours"]
    assert [call["status"] for call in tool_calls] == ["done", "done"]
    assert tool_calls[0]["params_summary"] == "period=this_year"
    assert tool_calls[0]["result_summary"] == "plays=77, hours=9.5"
    assert tool_calls[0]["source_range"] == "2026"
    assert tool_calls[1]["params_summary"] == "view=late_night_ratio"
    assert len(llm_calls) == 3
    assert status_payload["result"]["answer_retried"] is True


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
    thinking_final_prompt = llm_calls[1][0]
    assert "spotify-stats-project-context-v1" in thinking_final_prompt
    assert "Answer Philosophy" in thinking_final_prompt
    assert "Thinking Mode Note" in thinking_final_prompt
    assert "思考模式只表示工具核对更充分" in thinking_final_prompt
    assert "用中文组织为「结论」「我查了什么」「依据」「自检与限制」四段" not in (
        thinking_final_prompt
    )


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
        assert "上一版回答与工具证据或回答契约矛盾" in user_content
        assert "project_context_version" in user_content
        assert "spotify-stats-project-context-v1" in user_content
        assert "Project Context 的项目语境要求" in user_content
        assert "answer_style" in user_content
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


def test_chat_agent_adds_sufficiency_followups_with_total_tool_cap(
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
        if len(llm_calls) == 2:
            return "结论：所有指标均指向 GUTS，明显是 GUTS 更甚。"
        assert "evidence_sufficiency" in user_content
        assert "analytical_brief" in user_content
        assert "missing_axes" in user_content
        assert "must_explain" in user_content
        return (
            "结论：不同口径不完全一致，不能给出明显单方胜出的结论。"
            "累计播放偏向 GUTS，但个人榜单和强度证据需要分层说明。"
        )

    def fake_dispatch_tool(tool_name: str, params: dict[str, Any] | None = None):
        params = params or {}
        dispatched.append((tool_name, dict(params)))
        album_name = str(params.get("album_name") or "")
        if tool_name == "entity_stats":
            plays = 1749 if album_name == "GUTS" else 1637
            period = str(params.get("period") or "lifetime")
            return {
                "tool_name": tool_name,
                "params_summary": f"entity=album, album_name={album_name}, period={period}",
                "result_summary": f"found=true, plays={plays}",
                "source_range": period,
                "data": {
                    "found": True,
                    "album_name": album_name,
                    "period": {"period": period},
                    "summary": {"total_plays": plays},
                },
            }
        if tool_name == "compare_entities":
            return {
                "tool_name": tool_name,
                "params_summary": "entity_type=album, names=GUTS|The Life of a Showgirl",
                "result_summary": "found=true, compared=2",
                "source_range": "lifetime",
                "data": {
                    "entity_type": "album",
                    "entities": [
                        {
                            "requested_name": "GUTS",
                            "name": "GUTS",
                            "found": True,
                            "plays": 1749,
                            "power_score": 9000,
                            "plays_per_chart_week": 12.0,
                        },
                        {
                            "requested_name": "The Life of a Showgirl",
                            "name": "The Life of a Showgirl",
                            "found": True,
                            "plays": 1637,
                            "power_score": 10087,
                            "plays_per_chart_week": 18.0,
                        },
                    ],
                    "winner_by_cumulative_plays": "GUTS",
                    "winner_by_power_score": "The Life of a Showgirl",
                    "winner_by_intensity": "The Life of a Showgirl",
                    "fairness_notes": ["发行窗口不同，需要分层比较。"],
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
            ),
            "min_ms": 45000,
            "music_only": False,
            "merge_enabled": False,
            "dynamic_threshold": False,
            "max_merge_gap_minutes": 45,
            "merge_level": 3,
        },
    )

    assert create_response.status_code == 200
    task_id = create_response.json()["task_id"]
    status_payload = client.get(f"/api/ai/tasks/{task_id}").json()
    events_payload = client.get(f"/api/ai/tasks/{task_id}/events").json()

    assert status_payload["status"] == "done"
    assert status_payload["result"]["tool_call_count"] == 8
    assert dispatched[3] == (
        "compare_entities",
        {
            "entity_type": "album",
            "names": ["GUTS", "The Life of a Showgirl"],
            "min_ms": 45000,
            "music_only": False,
            "merge_enabled": False,
            "dynamic_threshold": False,
            "max_merge_gap_minutes": 45,
            "merge_level": 3,
        },
    )
    assert dispatched[4][0] == "entity_stats"
    assert dispatched[4][1]["album_name"] == "GUTS"
    assert dispatched[4][1]["period"] == "last_6_months"
    assert dispatched[5][0] == "entity_stats"
    assert dispatched[5][1]["album_name"] == "The Life of a Showgirl"
    assert dispatched[5][1]["period"] == "last_6_months"
    assert dispatched[6][0] == "entity_stats"
    assert dispatched[6][1]["album_name"] == "GUTS"
    assert dispatched[6][1]["period"] == "last_4_weeks"
    assert dispatched[7][0] == "entity_stats"
    assert dispatched[7][1]["album_name"] == "The Life of a Showgirl"
    assert dispatched[7][1]["period"] == "last_4_weeks"
    assert "reviewing_coverage" in [event["stage"] for event in events_payload["events"]]
    assert [call["tool_name"] for call in events_payload["tool_calls"]] == [
        "entity_stats",
        "billboard_entity_detail",
        "entity_stats",
        "compare_entities",
        "entity_stats",
        "entity_stats",
        "entity_stats",
        "entity_stats",
    ]
    assert status_payload["result"]["coverage"]["comparison"]["compare_entities"] == "found"
    assert status_payload["result"]["evidence_sufficiency"]["sufficient"] is True
    assert status_payload["result"]["answer_retried"] is True
    assert "不同口径不完全一致" in status_payload["result"]["answer"]
    assert "明显是 GUTS 更甚" not in status_payload["result"]["answer"]
    assert any(
        "证据不足" in issue or "过度" in issue
        for issue in status_payload["result"]["validation_issues"]
    )
    assert len(llm_calls) == 3


def test_chat_agent_replans_scoped_ranking_after_global_chart_miss(
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
                '[{"tool_name":"analysis_stats","params":{"period":"this_year"}},'
                '{"tool_name":"analysis_charts","params":{"entity":"album","metric":"plays",'
                '"period":"lifetime","limit":10}},'
                '{"tool_name":"analysis_charts","params":{"entity":"artist","metric":"plays",'
                '"period":"this_year","limit":10}},'
                '{"tool_name":"listening_hours","params":{"view":"platform_hourly"}},'
                '{"tool_name":"analysis_charts","params":{"entity":"track","metric":"plays",'
                '"period":"lifetime","limit":10}}]'
            )
        assert "scoped_ranking" in user_content
        assert "eternal sunshine" in user_content
        assert "Santa Tell Me" in user_content
        return "你最喜欢的 Ariana Grande 专辑是 eternal sunshine，歌曲是 Santa Tell Me。"

    def fake_dispatch_tool(tool_name: str, params: dict[str, Any] | None = None):
        params = params or {}
        dispatched.append((tool_name, dict(params)))
        if tool_name == "entity_stats":
            return {
                "tool_name": "entity_stats",
                "params_summary": "entity=artist, artist_name=Ariana Grande, period=lifetime",
                "result_summary": "found=true, plays=2153, hours=115.7",
                "source_range": "2022-07-01..2026-06-23",
                "data": {
                    "found": True,
                    "period": {"period": "lifetime"},
                    "summary": {"total_plays": 2153, "total_hours": 115.7},
                    "top_albums": [{"rank": 1, "album_name": "eternal sunshine", "plays": 997}],
                    "top_tracks": [{"rank": 1, "track_name": "Santa Tell Me", "plays": 145}],
                },
            }
        if tool_name == "analysis_charts":
            return {
                "tool_name": "analysis_charts",
                "params_summary": ", ".join(f"{key}={value}" for key, value in params.items()),
                "result_summary": f"{params.get('entity', 'track')} plays rows=10/100",
                "source_range": "2022-07-01..2026-06-23",
                "data": {
                    "entity": params.get("entity", "track"),
                    "metric": params.get("metric", "plays"),
                    "period": {"period": params.get("period", "lifetime")},
                    "rows": [{"rank": 1, "album_name": "Midnights", "plays": 2559}],
                },
            }
        if tool_name == "listening_hours":
            return {
                "tool_name": "listening_hours",
                "params_summary": "view=platform_hourly",
                "result_summary": "view=platform_hourly, items=3",
                "source_range": "platform_hourly",
                "data": {"view": "platform_hourly", "items": []},
            }
        return {
            "tool_name": "analysis_stats",
            "params_summary": "period=this_year",
            "result_summary": "plays=7860, hours=498",
            "source_range": "2026-01-01..2026-06-29",
            "data": {"period": {"period": "this_year"}, "summary": {"total_plays": 7860}},
        }

    monkeypatch.setattr(ai_task_service.threading, "Thread", SyncThread)
    monkeypatch.setattr(agent_service.ai_insights_service, "_llm_chat", fake_llm_chat)
    monkeypatch.setattr(agent_service, "dispatch_tool", fake_dispatch_tool)

    create_response = client.post(
        "/api/ai/tasks/chat",
        json={
            "question": "我最喜欢的Ariana Grande的专辑和歌曲是什么",
            "thinking_mode": True,
        },
    )

    assert create_response.status_code == 200
    task_id = create_response.json()["task_id"]
    status_payload = client.get(f"/api/ai/tasks/{task_id}").json()

    assert status_payload["status"] == "done"
    assert status_payload["result"]["question_frame"]["family"] == "scoped_ranking"
    assert status_payload["result"]["tool_call_count"] == 6
    assert dispatched[5] == (
        "entity_stats",
        {
            "entity": "artist",
            "artist_name": "Ariana Grande",
            "period": "lifetime",
            "min_ms": 30000,
            "music_only": True,
            "merge_enabled": True,
            "dynamic_threshold": True,
            "max_merge_gap_minutes": None,
            "merge_level": 1,
        },
    )
    assert status_payload["result"]["evidence_sufficiency"]["sufficient"] is True
    assert (
        status_payload["result"]["analytical_brief"]["recommended_conclusion"]["top_album"]
        == "eternal sunshine"
    )


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
    assert "LLM 调用失败" in status_payload["message"]
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
