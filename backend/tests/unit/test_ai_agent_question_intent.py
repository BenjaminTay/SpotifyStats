from __future__ import annotations

import json

import pytest

from backend.domains.ai_agent.question_intent import parse_question_intent
from backend.services import ai_agent_service

pytestmark = pytest.mark.unit


def test_detects_album_comparison_with_named_entities() -> None:
    intent = parse_question_intent(
        "从播放次数和billboard榜单成绩来看，我对GUTS和The Life of a Showgirl这两张专辑的喜爱程度哪张专辑更甚？"
    )

    assert intent.task_type == "comparison"
    assert intent.entity_type == "album"
    assert intent.entities == ["GUTS", "The Life of a Showgirl"]
    assert "plays" in intent.requested_metrics
    assert "personal_billboard" in intent.requested_metrics
    assert intent.needs_fairness_note is True


def test_detects_trend_question() -> None:
    intent = parse_question_intent("我最近六个月是不是越来越喜欢 Olivia Rodrigo？")

    assert intent.task_type == "trend"
    assert intent.entity_type == "artist"
    assert intent.entities == ["Olivia Rodrigo"]
    assert intent.time_scope == "last_6_months"
    assert "plays" in intent.requested_metrics
    assert "recent_window" in intent.requested_metrics


def test_detects_late_night_favorite_tracks_question() -> None:
    intent = parse_question_intent("我深夜最爱听什么歌？")

    assert intent.task_type == "ranking"
    assert intent.entity_type == "track"
    assert "plays" in intent.requested_metrics
    assert "time_of_day" in intent.requested_metrics


def test_plain_like_question_is_not_ranking() -> None:
    intent = parse_question_intent("我是不是爱听 Olivia Rodrigo？")

    assert intent.task_type != "ranking"
    assert "plays" in intent.requested_metrics


def test_ignores_product_names_when_extracting_entities() -> None:
    intent = parse_question_intent("SpotifyStats Billboard 里 GUTS 这张专辑表现如何？")

    assert intent.entities == ["GUTS"]


def test_ignores_markdown_table_format_instruction_when_extracting_entities() -> None:
    intent = parse_question_intent(
        "请用 Markdown 表格比较 GUTS 和 The Life of a Showgirl 这两张专辑。"
    )

    assert intent.task_type == "comparison"
    assert intent.entity_type == "album"
    assert intent.entities == ["GUTS", "The Life of a Showgirl"]


def test_ranking_signals_win_over_generic_which_terms() -> None:
    album_intent = parse_question_intent("我今年最常听哪张专辑？")
    artist_intent = parse_question_intent("哪个艺人播放量最高？")

    assert album_intent.task_type == "ranking"
    assert album_intent.entity_type == "album"
    assert album_intent.time_scope == "this_year"
    assert artist_intent.task_type == "ranking"
    assert artist_intent.entity_type == "artist"
    assert "plays" in artist_intent.requested_metrics


def test_scoped_artist_catalog_question_uses_artist_scope() -> None:
    intent = parse_question_intent("我最喜欢的Ariana Grande的专辑和歌曲是什么")

    assert intent.task_type == "ranking"
    assert intent.entity_type == "artist"
    assert intent.entities == ["Ariana Grande"]
    assert "plays" in intent.requested_metrics


def test_extracts_lowercase_numeric_and_chinese_context_entities() -> None:
    album_intent = parse_question_intent("我对brat和1989这两张专辑哪个更喜欢？")
    artist_intent = parse_question_intent("周杰伦和Taylor Swift这两位艺人哪个播放量更高？")

    assert album_intent.task_type == "comparison"
    assert album_intent.entities == ["brat", "1989"]
    assert artist_intent.task_type == "comparison"
    assert artist_intent.entities == ["周杰伦", "Taylor Swift"]


def test_detects_explicit_year_scope() -> None:
    intent = parse_question_intent("2025年我最常听哪张专辑？")

    assert intent.task_type == "ranking"
    assert intent.time_scope == "year:2025"


def test_planner_user_content_includes_question_intent() -> None:
    payload = json.loads(
        ai_agent_service._planner_user_content(
            {
                "question": "GUTS 和 Sour 哪张专辑播放量更高？",
                "conversation_history": [],
                "question_time": "2026-07-02T16:06:01+08:00",
                "timezone": "Asia/Shanghai",
            }
        )
    )

    assert payload["question_intent"]["task_type"] == "comparison"
    assert payload["question_intent"]["entity_type"] == "album"
    assert payload["question_intent"]["entities"] == ["GUTS", "Sour"]
    assert payload["temporal_context"]["today"] == "2026-07-02"
    assert "相对时间以 question_time 为准" in payload["temporal_context"]["relative_time_policy"]


def test_play_data_range_prefers_local_ts_date(monkeypatch: pytest.MonkeyPatch) -> None:
    observed_sql: list[str] = []

    class FakeConn:
        def execute(self, sql: str):
            observed_sql.append(sql)
            return self

        def fetchone(self):
            return ("2022-07-01", "2026-06-23")

        def close(self) -> None:
            pass

    monkeypatch.setattr(ai_agent_service, "get_db", lambda readonly=True: FakeConn())

    assert ai_agent_service._play_data_range() == {
        "data_start_date": "2022-07-01",
        "data_end_date": "2026-06-23",
    }
    assert "ts_date" in observed_sql[0]


def test_plan_tool_calls_temporal_guard_corrects_wrong_last_summer_year(monkeypatch) -> None:
    def fake_llm_chat(system_prompt: str, user_content: str, temperature: float = 0.3) -> str:
        return """
        [
          {
            "tool_name": "analysis_charts",
            "params": {
              "period": "custom",
              "start_date": "2024-06-01",
              "end_date": "2024-08-31",
              "entity": "artist",
              "metric": "plays"
            }
          },
          {"tool_name": "wrapped_yearly", "params": {"year": 2024}}
        ]
        """

    monkeypatch.setattr(ai_agent_service.ai_insights_service, "_llm_chat", fake_llm_chat)

    plan, mode = ai_agent_service._plan_tool_calls(
        {
            "question": "去年夏天我最常听什么类型的音乐？",
            "conversation_history": [],
            "question_time": "2026-07-02T16:06:01+08:00",
            "timezone": "Asia/Shanghai",
        }
    )

    assert mode == "planned_temporal_guarded"
    assert plan[0]["params"]["period"] == "custom"
    assert plan[0]["params"]["start_date"] == "2025-06-01"
    assert plan[0]["params"]["end_date"] == "2025-08-31"
    assert plan[1]["params"]["year"] == 2025


def test_plan_tool_calls_adds_bounded_tool_when_relative_time_plan_is_only_yearly(
    monkeypatch,
) -> None:
    def fake_llm_chat(system_prompt: str, user_content: str, temperature: float = 0.3) -> str:
        return '[{"tool_name":"wrapped_yearly","params":{"year":2025}}]'

    monkeypatch.setattr(ai_agent_service.ai_insights_service, "_llm_chat", fake_llm_chat)

    plan, mode = ai_agent_service._plan_tool_calls(
        {
            "question": "去年夏天我最常听什么类型的音乐？",
            "conversation_history": [],
            "question_time": "2026-07-02T16:06:01+08:00",
            "timezone": "Asia/Shanghai",
        }
    )

    assert mode == "planned_temporal_bounded"
    bounded_calls = [
        item
        for item in plan
        if item["tool_name"] == "analysis_charts"
        and item["params"].get("start_date") == "2025-06-01"
        and item["params"].get("end_date") == "2025-08-31"
    ]
    assert bounded_calls
    assert bounded_calls[0]["params"]["entity"] == "artist"


def test_prepare_followup_tool_call_applies_temporal_guard() -> None:
    prepared = ai_agent_service._prepare_followup_tool_call(
        {
            "tool_name": "analysis_charts",
            "params": {"period": "lifetime", "entity": "track", "metric": "plays"},
        },
        {
            "question": "去年夏天我最常听什么类型的音乐？",
            "question_time": "2026-07-02T16:06:01+08:00",
            "timezone": "Asia/Shanghai",
        },
    )

    assert prepared is not None
    assert prepared["params"]["period"] == "custom"
    assert prepared["params"]["start_date"] == "2025-06-01"
    assert prepared["params"]["end_date"] == "2025-08-31"


def test_sanitize_plan_applies_merge_level_to_compare_entities() -> None:
    plan = ai_agent_service._sanitize_plan(
        [
            {
                "tool_name": "compare_entities",
                "params": {"entity_type": "album", "names": ["A", "B"]},
            }
        ],
        {"question": "A 和 B 哪张更高？", "merge_level": 3},
    )

    assert plan[0]["params"]["merge_level"] == 3
