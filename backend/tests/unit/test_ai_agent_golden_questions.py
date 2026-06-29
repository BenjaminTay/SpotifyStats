from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from backend.domains.ai_agent.question_intent import parse_question_intent
from backend.domains.ai_agent.tool_registry import list_tools
from scripts import evaluate_ai_agent_harness

pytestmark = pytest.mark.unit

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "ai_agent_golden_questions.json"


def _load_cases() -> list[dict[str, object]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_golden_question_fixture_has_executable_shape() -> None:
    cases = _load_cases()
    available_tools = {tool["name"] for tool in list_tools()}

    assert len(cases) >= 4
    assert {case["id"] for case in cases}.issuperset(
        {
            "album_guts_vs_showgirl",
            "artist_olivia_last_6_months_trend",
            "ranking_top_artist_2023",
            "deep_night_tracks_and_hours",
        }
    )

    for case in cases:
        assert isinstance(case["id"], str) and case["id"]
        assert isinstance(case["question"], str) and case["question"]
        assert isinstance(case["expected_intent"], dict)
        expected_frame = case.get("expected_frame")
        assert isinstance(expected_frame, dict), case["id"]
        assert isinstance(expected_frame.get("family"), str) and expected_frame["family"]
        assert (
            isinstance(expected_frame.get("answer_contract"), str)
            and expected_frame["answer_contract"]
        )
        analysis_axes_contains = expected_frame.get("analysis_axes_contains")
        assert isinstance(analysis_axes_contains, list) and analysis_axes_contains, case["id"]
        assert all(isinstance(axis, str) and axis.strip() for axis in analysis_axes_contains)

        expected_recipe = case.get("expected_recipe")
        assert isinstance(expected_recipe, dict), case["id"]
        assert isinstance(expected_recipe.get("family"), str) and expected_recipe["family"]
        required_axes_contains = expected_recipe.get("required_axes_contains")
        assert isinstance(required_axes_contains, list) and required_axes_contains, case["id"]
        assert all(isinstance(axis, str) and axis.strip() for axis in required_axes_contains)
        required_tool_patterns_contains = expected_recipe.get("required_tool_patterns_contains")
        assert (
            isinstance(required_tool_patterns_contains, list) and required_tool_patterns_contains
        ), case["id"]
        for pattern in required_tool_patterns_contains:
            assert isinstance(pattern, dict), case["id"]
            assert isinstance(pattern.get("tool_name"), str) and pattern["tool_name"]

        recommended_tools = case.get("recommended_tools")
        expected_tools = case.get("expected_tools")
        tools = recommended_tools or expected_tools
        assert isinstance(tools, list) and tools, case["id"]
        for tool in tools:
            assert isinstance(tool, dict)
            assert tool["tool_name"] in available_tools
            assert isinstance(tool.get("params", {}), dict)

        required_terms = case["required_answer_terms"]
        forbidden_terms = case["forbidden_answer_terms"]
        assert isinstance(required_terms, list) and required_terms
        assert isinstance(forbidden_terms, list) and forbidden_terms
        assert all(isinstance(term, str) and term.strip() for term in required_terms)
        assert all(isinstance(term, str) and term.strip() for term in forbidden_terms)
        assert {term.casefold() for term in required_terms}.isdisjoint(
            {term.casefold() for term in forbidden_terms}
        )


@pytest.mark.parametrize("case", _load_cases(), ids=lambda case: case["id"])
def test_golden_questions_match_current_intent_parser(case: dict[str, object]) -> None:
    expected = case["expected_intent"]
    assert isinstance(expected, dict)

    intent = parse_question_intent(str(case["question"]))
    dumped = intent.model_dump()

    for key in ("task_type", "entity_type", "entities", "time_scope", "needs_fairness_note"):
        if key in expected:
            assert dumped[key] == expected[key]

    expected_metrics = expected.get("requested_metrics_contains", [])
    assert isinstance(expected_metrics, list)
    assert set(expected_metrics).issubset(set(intent.requested_metrics))


def test_golden_harness_reports_all_cases_pass() -> None:
    result = evaluate_ai_agent_harness.evaluate_fixture(FIXTURE_PATH)

    assert result["failed"] == 0
    assert result["passed"] == result["total"] >= 4


def test_golden_harness_rejects_missing_required_tool_call() -> None:
    case = deepcopy(next(item for item in _load_cases() if item["id"] == "album_guts_vs_showgirl"))
    case["recommended_tools"] = [{"tool_name": "analysis_stats", "params": {"period": "lifetime"}}]

    failures = evaluate_ai_agent_harness.evaluate_case(case)

    assert any("missing required tool call" in failure for failure in failures)


def test_golden_harness_rejects_expected_frame_mismatch() -> None:
    case = deepcopy(next(item for item in _load_cases() if item["id"] == "album_guts_vs_showgirl"))
    case["expected_frame"] = {
        "family": "simple_ranking",
        "answer_contract": "simple_rank_answer",
        "analysis_axes_contains": ["ranking"],
    }
    case["expected_recipe"] = {
        "family": "simple_ranking",
        "required_axes_contains": ["ranking"],
        "required_tool_patterns_contains": [{"tool_name": "analysis_charts"}],
    }

    failures = evaluate_ai_agent_harness.evaluate_case(case)

    assert any("expected_frame.family" in failure for failure in failures)


def test_golden_harness_rejects_expected_recipe_missing_tool_pattern() -> None:
    case = deepcopy(next(item for item in _load_cases() if item["id"] == "album_guts_vs_showgirl"))
    case["expected_frame"] = {
        "family": "preference_comparison",
        "answer_contract": "layered_preference_comparison",
        "analysis_axes_contains": ["cumulative", "recency", "intensity"],
    }
    case["expected_recipe"] = {
        "family": "preference_comparison",
        "required_axes_contains": ["cumulative", "recency", "intensity"],
        "required_tool_patterns_contains": [{"tool_name": "wrapped_yearly"}],
    }

    failures = evaluate_ai_agent_harness.evaluate_case(case)

    assert any("required_tool_patterns" in failure for failure in failures)
