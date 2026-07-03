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


def test_final_payload_preserves_scoped_artist_album_and_track_rankings() -> None:
    payload = ai_agent_service._final_payload(
        {
            "question": "我最喜欢的Ariana Grande的专辑和歌曲是什么",
            "conversation_history": [],
        },
        [
            {
                "tool_name": "entity_stats",
                "status": "done",
                "params_summary": "entity=artist, artist_name=Ariana Grande, period=lifetime",
                "result_summary": "found=true, plays=2153, hours=115.7",
                "source_range": "2022-07-01..2026-06-23",
                "data": {
                    "found": True,
                    "period": {"period": "lifetime"},
                    "summary": {"total_plays": 2153, "total_hours": 115.7},
                    "top_albums": [
                        {
                            "rank": 1,
                            "album_name": "eternal sunshine",
                            "plays": 997,
                            "hours": 49.67,
                        }
                    ],
                    "top_tracks": [
                        {
                            "rank": 1,
                            "track_name": "Santa Tell Me",
                            "plays": 145,
                            "hours": 8.08,
                        }
                    ],
                },
            }
        ],
    )

    evidence = payload["tool_results"][0]["evidence"]
    assert evidence["top_albums"][0]["album_name"] == "eternal sunshine"
    assert evidence["top_albums"][0]["plays"] == 997
    assert evidence["top_tracks"][0]["track_name"] == "Santa Tell Me"
    assert evidence["top_tracks"][0]["plays"] == 145
    assert payload["analytical_brief"]["recommended_conclusion"]["top_album"] == (
        "eternal sunshine"
    )


def test_scoped_ranking_defaults_to_concise_answer_style() -> None:
    payload = ai_agent_service._final_payload(
        {
            "question": "我最喜欢的Ariana Grande的专辑和歌曲是什么",
            "conversation_history": [],
        },
        [
            {
                "tool_name": "entity_stats",
                "status": "done",
                "params_summary": "entity=artist, artist_name=Ariana Grande, period=lifetime",
                "result_summary": "found=true, plays=2153, hours=115.7",
                "source_range": "2022-07-01..2026-06-23",
                "data": {
                    "found": True,
                    "period": {"period": "lifetime"},
                    "top_albums": [{"rank": 1, "album_name": "eternal sunshine", "plays": 997}],
                    "top_tracks": [{"rank": 1, "track_name": "Santa Tell Me", "plays": 145}],
                },
            }
        ],
    )

    assert payload["answer_style"]["style"] == "concise"
    assert payload["answer_style"]["max_sentences"] == 6
    assert "我查了什么" in payload["answer_style"]["avoid_sections"]
    assert payload["analytical_brief"]["concise_shape"] == (
        "一句直接结论 + 两条关键数字 + 一句必要口径"
    )
    assert payload["project_context_version"] == "spotify-stats-project-context-v1"


def test_final_user_content_includes_project_context_version() -> None:
    content = ai_agent_service._final_user_content(
        {
            "question": "2023年我播放量最高的艺人是谁？",
            "conversation_history": [],
        },
        [
            {
                "tool_name": "analysis_charts",
                "status": "done",
                "params_summary": (
                    "period=custom, start_date=2023-01-01, end_date=2023-12-31, "
                    "entity=artist, metric=plays"
                ),
                "result_summary": "rows=10, top_artist=Taylor Swift",
                "source_range": "2023-01-01..2023-12-31",
                "data": {
                    "entity": "artist",
                    "metric": "plays",
                    "period": {
                        "period": "custom",
                        "start_date": "2023-01-01",
                        "end_date": "2023-12-31",
                    },
                    "rows": [{"rank": 1, "artist_name": "Taylor Swift", "plays": 1000}],
                },
            }
        ],
    )

    payload = json.loads(content)
    assert payload["project_context_version"] == "spotify-stats-project-context-v1"


def test_final_payload_projects_temporal_guard_into_simple_ranking_recipe() -> None:
    payload = ai_agent_service._final_payload(
        {
            "question": "去年夏天我最常听什么类型的音乐？",
            "conversation_history": [],
            "_temporal_context": {
                "today": "2026-07-03",
                "latest_play_date": "2026-06-23",
                "data_start_date": "2022-07-01",
                "data_end_date": "2026-06-23",
            },
            "_temporal_guard": {
                "time_interpretation": {
                    "label": "去年夏天",
                    "start_date": "2025-06-01",
                    "end_date": "2025-08-31",
                },
                "had_corrections": True,
                "corrections": [],
            },
        },
        [
            {
                "tool_name": "analysis_charts",
                "status": "done",
                "params_summary": "entity=track, metric=plays, period=custom",
                "result_summary": "track plays rows=10/1083",
                "source_range": "2025-06-01..2025-08-31",
                "data": {
                    "entity": "track",
                    "metric": "plays",
                    "period": {
                        "period": "custom",
                        "start_date": "2025-06-01",
                        "end_date": "2025-08-31",
                    },
                    "rows": [{"rank": 1, "track_name": "Manchild", "plays": 53}],
                },
            }
        ],
    )

    assert payload["evidence_recipe"]["required_context"]["period"] == "custom"
    assert payload["evidence_recipe"]["required_context"]["start_date"] == "2025-06-01"
    assert payload["evidence_sufficiency"]["sufficient"] is True
    assert payload["analytical_brief"]["recommended_conclusion"]["top_result"] == "Manchild"


def test_explicit_detail_request_uses_detailed_answer_style() -> None:
    payload = ai_agent_service._final_payload(
        {
            "question": "请详细说明我最喜欢的Ariana Grande的专辑和歌曲是什么，并列出依据",
            "conversation_history": [],
        },
        [
            {
                "tool_name": "entity_stats",
                "status": "done",
                "params_summary": "entity=artist, artist_name=Ariana Grande, period=lifetime",
                "result_summary": "found=true, plays=2153, hours=115.7",
                "source_range": "2022-07-01..2026-06-23",
                "data": {
                    "found": True,
                    "period": {"period": "lifetime"},
                    "top_albums": [{"rank": 1, "album_name": "eternal sunshine", "plays": 997}],
                    "top_tracks": [{"rank": 1, "track_name": "Santa Tell Me", "plays": 145}],
                },
            }
        ],
    )

    assert payload["answer_style"]["style"] == "detailed"
    assert payload["answer_style"]["allow_sections"] is True


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
        assert "上一版回答与工具证据或回答契约矛盾" in user_content
        return "在你的个人 Billboard 口径里，GUTS 的榜单表现更强。"

    def fake_dispatch_tool(tool_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        assert (params or {})["album_name"] == "GUTS"
        if tool_name == "entity_stats":
            return {
                "tool_name": tool_name,
                "params_summary": "entity=album, album_name=GUTS",
                "result_summary": "found=true, plays=1749",
                "source_range": "lifetime",
                "data": {
                    "found": True,
                    "entity": "album",
                    "album_name": "GUTS",
                    "summary": {"total_plays": 1749},
                },
            }
        assert tool_name == "billboard_entity_detail"
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
    assert fake_repo.result["answer"].startswith(
        "在你的个人 Billboard 口径里，GUTS 的榜单表现更强。"
    )
    assert "限制" in fake_repo.result["answer"]
    assert fake_repo.result["validation_issues"] == []
    assert len(llm_calls) == 3
