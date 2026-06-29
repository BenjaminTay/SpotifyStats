from __future__ import annotations

import pytest

from backend.domains.ai_agent import project_context

pytestmark = pytest.mark.unit


def test_project_context_prompt_contains_product_semantics() -> None:
    prompt = project_context.PROJECT_CONTEXT_PROMPT

    assert "SpotifyStats" in prompt
    assert "个人" in prompt
    assert "本地 Spotify" in prompt
    assert "本地播放记录" in prompt
    assert "个人 Billboard" in prompt
    assert "不是通用音乐百科" in prompt
    assert "不是官方 Billboard" in prompt


def test_tool_playbook_mentions_required_agent_tools() -> None:
    prompt = project_context.TOOL_PLAYBOOK_PROMPT

    assert "analysis_stats" in prompt
    assert "analysis_charts" in prompt
    assert "entity_stats(entity=artist)" in prompt
    assert "top_albums/top_tracks" in prompt
    assert "compare_entities" in prompt
    assert "listening_hours" in prompt
    assert "不能只查 lifetime" in prompt


def test_answer_philosophy_keeps_simple_answers_concise() -> None:
    prompt = project_context.ANSWER_PHILOSOPHY_PROMPT

    assert "先回答" in prompt
    assert "answer_style=concise" in prompt
    assert "3-6 句" in prompt
    assert "不写流水账" in prompt
    assert "本地个人 Billboard" in prompt


def test_project_context_fragments_stay_within_budget() -> None:
    combined = "\n".join(
        [
            project_context.PROJECT_CONTEXT_PROMPT,
            project_context.TOOL_PLAYBOOK_PROMPT,
            project_context.ANSWER_PHILOSOPHY_PROMPT,
            project_context.SAFETY_BOUNDARY_PROMPT,
        ]
    )

    assert len(combined) < 3200


def test_prompt_builders_include_version_and_base_prompt() -> None:
    planner = project_context.build_planner_system_prompt("BASE PLANNER")
    final = project_context.build_final_answer_system_prompt("BASE FINAL")
    thinking = project_context.build_final_answer_system_prompt(
        "BASE THINKING",
        thinking_mode=True,
    )

    assert project_context.PROJECT_CONTEXT_VERSION in planner
    assert "BASE PLANNER" in planner
    assert project_context.TOOL_PLAYBOOK_PROMPT in planner
    assert "BASE FINAL" in final
    assert project_context.ANSWER_PHILOSOPHY_PROMPT in final
    assert "BASE THINKING" in thinking
    assert "思考模式" in thinking
    assert "我查了什么" not in thinking


def test_project_context_payload_is_compact_metadata() -> None:
    payload = project_context.project_context_payload()

    assert payload == {
        "project_context_version": project_context.PROJECT_CONTEXT_VERSION,
    }
