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
