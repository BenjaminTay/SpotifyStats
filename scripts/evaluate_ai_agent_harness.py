#!/usr/bin/env python3
"""Offline golden-question evaluator for the AI Agent harness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.domains.ai_agent.answer_critic import critique_answer  # noqa: E402
from backend.domains.ai_agent.evidence_recipes import recipe_for_frame  # noqa: E402
from backend.domains.ai_agent.question_frame import build_question_frame  # noqa: E402
from backend.domains.ai_agent.question_intent import parse_question_intent  # noqa: E402
from backend.domains.ai_agent.tool_registry import (  # noqa: E402
    UnknownAgentToolError,
    get_default_registry,
)
from backend.services import ai_agent_service  # noqa: E402

DEFAULT_FIXTURE_PATH = ROOT / "backend" / "tests" / "fixtures" / "ai_agent_golden_questions.json"
ANSWER_STYLE_VALUES = {"concise", "structured", "detailed"}


def load_cases(path: Path = DEFAULT_FIXTURE_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _expected_tools(case: dict[str, Any]) -> list[dict[str, Any]]:
    tools = case.get("recommended_tools") or case.get("expected_tools")
    return tools if isinstance(tools, list) else []


def _validate_tool_call(case_id: str, tool_call: Any) -> list[str]:
    failures: list[str] = []
    if not isinstance(tool_call, dict):
        return [f"{case_id}: tool entry must be an object"]

    tool_name = tool_call.get("tool_name")
    if not isinstance(tool_name, str) or not tool_name:
        return [f"{case_id}: tool_name must be a non-empty string"]

    try:
        definition = get_default_registry().get(tool_name)
    except UnknownAgentToolError:
        return [f"{case_id}: unknown tool {tool_name!r}"]

    params = tool_call.get("params", {})
    if not isinstance(params, dict):
        return [f"{case_id}: params for {tool_name} must be an object"]

    try:
        definition.params_model.model_validate(params)
    except Exception as exc:  # noqa: BLE001 - report pydantic validation details.
        failures.append(f"{case_id}: params for {tool_name} are invalid: {exc}")
    return failures


def _param_value_matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(
            key in actual and _param_value_matches(actual[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        return all(item in actual for item in expected)
    return actual == expected


def _tool_call_matches(required: dict[str, Any], actual: dict[str, Any]) -> bool:
    if required.get("tool_name") != actual.get("tool_name"):
        return False
    required_params = required.get("params", {})
    actual_params = actual.get("params", {})
    return _param_value_matches(actual_params, required_params)


def _dict_contains(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(
        key in actual and _param_value_matches(actual[key], expected_value)
        for key, expected_value in expected.items()
    )


def _case_entities(case: dict[str, Any]) -> tuple[str, list[str]]:
    expected_intent = case.get("expected_intent")
    if not isinstance(expected_intent, dict):
        return "unknown", []
    entity_type = str(expected_intent.get("entity_type") or "unknown")
    entities = expected_intent.get("entities")
    if not isinstance(entities, list):
        return entity_type, []
    return entity_type, [entity for entity in entities if isinstance(entity, str) and entity]


def _entity_name_param(entity_type: str, name: str) -> dict[str, str]:
    if entity_type == "artist":
        return {"artist_name": name}
    if entity_type == "album":
        return {"album_name": name}
    if entity_type == "track":
        return {"track_name": name}
    return {}


def _period_params_from_scope(time_scope: Any) -> dict[str, Any]:
    if isinstance(time_scope, str) and time_scope.startswith("year:"):
        year = time_scope.split(":", 1)[1]
        if year.isdigit():
            return {
                "period": "custom",
                "start_date": f"{year}-01-01",
                "end_date": f"{year}-12-31",
            }
    if isinstance(time_scope, str) and time_scope:
        return {"period": time_scope}
    return {"period": "lifetime"}


def _period_payload(params: dict[str, Any]) -> Any:
    period = params.get("period") or "lifetime"
    if params.get("start_date") or params.get("end_date"):
        return {
            "period": period,
            "start_date": params.get("start_date"),
            "end_date": params.get("end_date"),
        }
    return period


def _params_summary(params: dict[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in params.items())


def _tool_result_from_call(tool_call: dict[str, Any]) -> dict[str, Any]:
    tool_name = str(tool_call.get("tool_name") or "")
    params = tool_call.get("params")
    params = params if isinstance(params, dict) else {}
    data: dict[str, Any] = {**params}

    if tool_name == "compare_entities":
        names = params.get("names") if isinstance(params.get("names"), list) else []
        names = [name for name in names if isinstance(name, str)]
        winner = names[0] if names else ""
        data.update(
            {
                "entity_type": params.get("entity_type", "unknown"),
                "entities": [
                    {
                        "requested_name": name,
                        "name": name,
                        "plays": 120 - index * 10,
                        "power_score": 80 - index * 5,
                        "weeks_on_chart": 10 - index,
                    }
                    for index, name in enumerate(names)
                ],
                "winner_by_plays": winner,
                "winner_by_intensity": winner,
                "winner_by_power_score": winner,
                "fairness_notes": ["发行时间不同，比较时保留窗口边界。"],
            }
        )
    elif tool_name == "entity_stats":
        data["period"] = _period_payload(params)
        if data.get("entity") == "artist":
            data.setdefault(
                "top_albums",
                [{"album_name": "Representative Album", "plays": 100, "share_pct": 42.0}],
            )
            data.setdefault(
                "top_tracks",
                [{"track_name": "Representative Track", "plays": 80, "share_pct": 33.6}],
            )
        else:
            data.setdefault("summary", {"plays": 100})
    elif tool_name == "billboard_entity_detail":
        data.update({"power_score": 88.0, "peak_position": 1, "weeks_on_chart": 12})
    elif tool_name == "analysis_charts":
        data["period"] = _period_payload(params)
        data.setdefault(
            "rows",
            [{"rank": 1, "artist_name": "Representative Artist", "plays": 100}],
        )
    elif tool_name == "analysis_stats":
        data["period"] = _period_payload(params)
        data.setdefault("summary", {"total_plays": 100})
    elif tool_name == "listening_hours":
        data.setdefault("view", params.get("view") or "heatmap")
        data.setdefault("rows", [{"rank": 1, "track_name": "Representative Track", "plays": 20}])
    elif tool_name == "wrapped_yearly":
        data.setdefault("year", params.get("year"))
        data.setdefault("top_artists", [{"artist_name": "Representative Artist", "plays": 100}])

    return {
        "tool_name": tool_name,
        "status": "done",
        "params": params,
        "params_summary": _params_summary(params),
        "result_summary": "synthetic golden harness result",
        "source_range": "fixture",
        "data": data,
    }


def _tool_calls_from_recipe_patterns(case: dict[str, Any]) -> list[dict[str, Any]]:
    expected_recipe = case.get("expected_recipe")
    if not isinstance(expected_recipe, dict):
        return []
    patterns = expected_recipe.get("required_tool_patterns_contains")
    if not isinstance(patterns, list):
        return []

    expected_intent = case.get("expected_intent")
    expected_intent = expected_intent if isinstance(expected_intent, dict) else {}
    entity_type, entities = _case_entities(case)
    calls: list[dict[str, Any]] = []

    for pattern in patterns:
        if not isinstance(pattern, dict):
            continue
        tool_name = pattern.get("tool_name")
        if not isinstance(tool_name, str):
            continue

        if tool_name == "compare_entities" and entity_type in {"artist", "album", "track"}:
            calls.append(
                {
                    "tool_name": tool_name,
                    "params": {"entity_type": entity_type, "names": entities[:4]},
                }
            )
            continue

        if tool_name in {"entity_stats", "billboard_entity_detail"} and entities:
            pattern_entity = pattern.get("entity")
            call_entity_type = (
                pattern_entity if pattern_entity in {"artist", "album", "track"} else entity_type
            )
            for entity_name in entities:
                entity_params = {
                    "entity": call_entity_type,
                    **_entity_name_param(call_entity_type, entity_name),
                }
                if isinstance(pattern.get("period"), str):
                    entity_params["period"] = pattern["period"]
                calls.append({"tool_name": tool_name, "params": entity_params})
            continue

        if tool_name == "analysis_charts":
            chart_params: dict[str, Any] = {
                "entity": pattern.get("entity") or entity_type,
                "metric": pattern.get("metric") or "plays",
            }
            if isinstance(pattern.get("period"), str):
                chart_params["period"] = pattern["period"]
            else:
                chart_params.update(_period_params_from_scope(expected_intent.get("time_scope")))
            calls.append({"tool_name": tool_name, "params": chart_params})
            continue

        if tool_name == "analysis_stats":
            stats_params: dict[str, Any] = {}
            if isinstance(pattern.get("period"), str):
                stats_params["period"] = pattern["period"]
            calls.append({"tool_name": tool_name, "params": stats_params})
            continue

        if tool_name == "listening_hours":
            listening_params: dict[str, Any] = {}
            if isinstance(pattern.get("view"), str):
                listening_params["view"] = pattern["view"]
            calls.append({"tool_name": tool_name, "params": listening_params})
            continue

        if tool_name == "wrapped_yearly":
            time_scope = expected_intent.get("time_scope")
            if isinstance(time_scope, str) and time_scope.startswith("year:"):
                year = time_scope.split(":", 1)[1]
                if year.isdigit():
                    calls.append({"tool_name": tool_name, "params": {"year": int(year)}})

    return calls


def answer_style_probe_tool_results(case: dict[str, Any]) -> list[dict[str, Any]]:
    """Build deterministic offline tool results for probing answer_style."""
    calls = [*_expected_tools(case), *_tool_calls_from_recipe_patterns(case)]
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for call in calls:
        if not isinstance(call, dict):
            continue
        result = _tool_result_from_call(call)
        identity = (result["tool_name"], repr(sorted(result["params"].items())))
        if identity in seen:
            continue
        seen.add(identity)
        results.append(result)
    return results


def _validate_required_tool_calls(case: dict[str, Any]) -> list[str]:
    case_id = str(case.get("id") or "<missing-id>")
    required_calls = case.get("required_tool_calls")
    if not isinstance(required_calls, list) or not required_calls:
        return [f"{case_id}: required_tool_calls must be a non-empty list"]
    tools = _expected_tools(case)
    failures: list[str] = []
    for required in required_calls:
        if not isinstance(required, dict):
            failures.append(f"{case_id}: required_tool_calls entries must be objects")
            continue
        required_failures = _validate_tool_call(case_id, required)
        if required_failures:
            failures.extend(required_failures)
            continue
        if not any(
            isinstance(actual, dict) and _tool_call_matches(required, actual) for actual in tools
        ):
            failures.append(f"{case_id}: missing required tool call {required}")
    return failures


def _validate_structure(case: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    case_id = str(case.get("id") or "<missing-id>")

    if not isinstance(case.get("id"), str) or not case["id"]:
        failures.append(f"{case_id}: id must be a non-empty string")
    if not isinstance(case.get("question"), str) or not case["question"]:
        failures.append(f"{case_id}: question must be a non-empty string")
    expected_answer_style = case.get("expected_answer_style")
    if expected_answer_style is not None and (
        not isinstance(expected_answer_style, str)
        or expected_answer_style not in ANSWER_STYLE_VALUES
    ):
        failures.append(
            f"{case_id}: expected_answer_style must be one of {sorted(ANSWER_STYLE_VALUES)}"
        )
    if not isinstance(case.get("expected_intent"), dict):
        failures.append(f"{case_id}: expected_intent must be an object")
    expected_frame = case.get("expected_frame")
    if not isinstance(expected_frame, dict):
        failures.append(f"{case_id}: expected_frame must be an object")
        expected_frame = {}
    if expected_frame and (
        not isinstance(expected_frame.get("family"), str) or not expected_frame["family"]
    ):
        failures.append(f"{case_id}: expected_frame.family must be a non-empty string")
    if expected_frame and (
        not isinstance(expected_frame.get("answer_contract"), str)
        or not expected_frame["answer_contract"]
    ):
        failures.append(f"{case_id}: expected_frame.answer_contract must be a non-empty string")
    frame_axes = expected_frame.get("analysis_axes_contains")
    if not isinstance(frame_axes, list) or not frame_axes:
        failures.append(
            f"{case_id}: expected_frame.analysis_axes_contains must be a non-empty list"
        )
        frame_axes = []
    invalid_frame_axes = [axis for axis in frame_axes if not isinstance(axis, str) or not axis]
    if invalid_frame_axes:
        failures.append(f"{case_id}: expected_frame.analysis_axes_contains has invalid values")

    expected_recipe = case.get("expected_recipe")
    if not isinstance(expected_recipe, dict):
        failures.append(f"{case_id}: expected_recipe must be an object")
        expected_recipe = {}
    if expected_recipe and (
        not isinstance(expected_recipe.get("family"), str) or not expected_recipe["family"]
    ):
        failures.append(f"{case_id}: expected_recipe.family must be a non-empty string")
    recipe_axes = expected_recipe.get("required_axes_contains")
    if not isinstance(recipe_axes, list) or not recipe_axes:
        failures.append(
            f"{case_id}: expected_recipe.required_axes_contains must be a non-empty list"
        )
        recipe_axes = []
    invalid_recipe_axes = [axis for axis in recipe_axes if not isinstance(axis, str) or not axis]
    if invalid_recipe_axes:
        failures.append(f"{case_id}: expected_recipe.required_axes_contains has invalid values")
    recipe_patterns = expected_recipe.get("required_tool_patterns_contains")
    if not isinstance(recipe_patterns, list) or not recipe_patterns:
        failures.append(
            f"{case_id}: expected_recipe.required_tool_patterns_contains must be a non-empty list"
        )
        recipe_patterns = []
    for pattern in recipe_patterns:
        if not isinstance(pattern, dict):
            failures.append(
                f"{case_id}: expected_recipe.required_tool_patterns_contains entries must be objects"
            )
            continue
        if not isinstance(pattern.get("tool_name"), str) or not pattern["tool_name"]:
            failures.append(
                f"{case_id}: expected_recipe.required_tool_patterns_contains tool_name is required"
            )

    tools = _expected_tools(case)
    if not tools:
        failures.append(f"{case_id}: expected_tools or recommended_tools is required")
    for tool_call in tools:
        failures.extend(_validate_tool_call(case_id, tool_call))
    failures.extend(_validate_required_tool_calls(case))

    required_terms = case.get("required_answer_terms")
    forbidden_terms = case.get("forbidden_answer_terms")
    if not isinstance(required_terms, list) or not required_terms:
        failures.append(f"{case_id}: required_answer_terms must be a non-empty list")
        required_terms = []
    if not isinstance(forbidden_terms, list) or not forbidden_terms:
        failures.append(f"{case_id}: forbidden_answer_terms must be a non-empty list")
        forbidden_terms = []

    invalid_required = [term for term in required_terms if not isinstance(term, str) or not term]
    invalid_forbidden = [term for term in forbidden_terms if not isinstance(term, str) or not term]
    if invalid_required:
        failures.append(f"{case_id}: required_answer_terms contains invalid values")
    if invalid_forbidden:
        failures.append(f"{case_id}: forbidden_answer_terms contains invalid values")

    required_lower = {term.casefold() for term in required_terms if isinstance(term, str)}
    forbidden_lower = {term.casefold() for term in forbidden_terms if isinstance(term, str)}
    overlap = sorted(required_lower & forbidden_lower)
    if overlap:
        failures.append(f"{case_id}: terms appear in both required and forbidden: {overlap}")

    return failures


def _validate_frame_and_recipe(case: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    case_id = str(case.get("id") or "<missing-id>")
    expected_frame = case.get("expected_frame")
    expected_recipe = case.get("expected_recipe")
    if not isinstance(expected_frame, dict):
        return [f"{case_id}: expected_frame must be an object"]
    if not isinstance(expected_recipe, dict):
        return [f"{case_id}: expected_recipe must be an object"]

    intent = parse_question_intent(str(case.get("question") or ""))
    frame = build_question_frame(str(case.get("question") or ""), intent)
    frame_dump = frame.model_dump()
    expected_family = expected_frame.get("family")
    if isinstance(expected_family, str) and frame.family != expected_family:
        failures.append(
            f"{case_id}: expected_frame.family expected {expected_family!r}, got {frame.family!r}"
        )
    expected_contract = expected_frame.get("answer_contract")
    if isinstance(expected_contract, str) and frame.answer_contract != expected_contract:
        failures.append(
            f"{case_id}: expected_frame.answer_contract expected "
            f"{expected_contract!r}, got {frame.answer_contract!r}"
        )
    expected_axes = expected_frame.get("analysis_axes_contains")
    if isinstance(expected_axes, list):
        missing_axes = sorted(set(expected_axes) - set(frame_dump["analysis_axes"]))
        if missing_axes:
            failures.append(f"{case_id}: expected_frame missing analysis axes {missing_axes}")

    recipe = recipe_for_frame(frame)
    recipe_dump = recipe.model_dump()
    expected_recipe_family = expected_recipe.get("family")
    if isinstance(expected_recipe_family, str) and recipe.family != expected_recipe_family:
        failures.append(
            f"{case_id}: expected_recipe.family expected "
            f"{expected_recipe_family!r}, got {recipe.family!r}"
        )
    expected_required_axes = expected_recipe.get("required_axes_contains")
    if isinstance(expected_required_axes, list):
        missing_required_axes = sorted(
            set(expected_required_axes) - set(recipe_dump["required_axes"])
        )
        if missing_required_axes:
            failures.append(
                f"{case_id}: expected_recipe missing required axes {missing_required_axes}"
            )
    expected_patterns = expected_recipe.get("required_tool_patterns_contains")
    actual_patterns = recipe_dump["required_tool_patterns"]
    if isinstance(expected_patterns, list):
        for expected_pattern in expected_patterns:
            if not isinstance(expected_pattern, dict):
                continue
            if not any(
                isinstance(actual_pattern, dict)
                and _dict_contains(actual_pattern, expected_pattern)
                for actual_pattern in actual_patterns
            ):
                failures.append(
                    f"{case_id}: expected_recipe missing required_tool_patterns {expected_pattern}"
                )
    return failures


def _validate_intent(case: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    case_id = str(case.get("id") or "<missing-id>")
    expected = case.get("expected_intent")
    if not isinstance(expected, dict):
        return [f"{case_id}: expected_intent must be an object"]

    intent = parse_question_intent(str(case.get("question") or ""))
    dumped = intent.model_dump()
    for key in ("task_type", "entity_type", "entities", "time_scope", "needs_fairness_note"):
        if key in expected and dumped[key] != expected[key]:
            failures.append(
                f"{case_id}: intent.{key} expected {expected[key]!r}, got {dumped[key]!r}"
            )

    expected_metrics = expected.get("requested_metrics_contains", [])
    if not isinstance(expected_metrics, list):
        failures.append(f"{case_id}: requested_metrics_contains must be a list")
        expected_metrics = []
    missing_metrics = sorted(set(expected_metrics) - set(intent.requested_metrics))
    if missing_metrics:
        failures.append(f"{case_id}: intent missing requested metrics {missing_metrics}")
    forbidden_metrics = expected.get("forbidden_metrics_contains", [])
    if not isinstance(forbidden_metrics, list):
        failures.append(f"{case_id}: forbidden_metrics_contains must be a list")
        forbidden_metrics = []
    present_forbidden_metrics = sorted(set(forbidden_metrics) & set(intent.requested_metrics))
    if present_forbidden_metrics:
        failures.append(f"{case_id}: intent included forbidden metrics {present_forbidden_metrics}")
    return failures


def _validate_critic(case: dict[str, Any]) -> list[str]:
    critic = case.get("critic")
    case_id = str(case.get("id") or "<missing-id>")
    required_terms = case.get("required_answer_terms")
    required_answer = " ".join(required_terms) if isinstance(required_terms, list) else ""
    required_result = critique_answer(required_answer, {"coverage": {}, "evidence_cards": []})
    failures: list[str] = []
    if not required_result["ok"]:
        failures.append(
            f"{case_id}: required answer terms were rejected by critic: {required_result['issues']}"
        )
    if critic is None:
        return failures
    if not isinstance(critic, dict):
        return [f"{case_id}: critic must be an object when present"]

    payload = {
        "coverage": critic.get("coverage", {}),
        "evidence_cards": critic.get("evidence_cards", []),
    }
    safe_answer = critic.get("safe_answer")
    if isinstance(safe_answer, str) and safe_answer:
        safe_result = critique_answer(safe_answer, payload)
        if not safe_result["ok"]:
            failures.append(f"{case_id}: safe answer rejected by critic: {safe_result['issues']}")

    unsafe_answer = critic.get("unsafe_answer")
    if isinstance(unsafe_answer, str) and unsafe_answer:
        unsafe_result = critique_answer(unsafe_answer, payload)
        if unsafe_result["ok"]:
            failures.append(f"{case_id}: unsafe answer was not rejected by critic")
    return failures


def _validate_answer_style(case: dict[str, Any]) -> list[str]:
    expected_answer_style = case.get("expected_answer_style")
    if not expected_answer_style:
        return []
    if (
        not isinstance(expected_answer_style, str)
        or expected_answer_style not in ANSWER_STYLE_VALUES
    ):
        return []

    case_id = str(case.get("id") or "<missing-id>")
    question = str(case.get("question") or "")
    payload = ai_agent_service._final_payload(
        {"question": question, "conversation_history": []},
        answer_style_probe_tool_results(case),
    )
    answer_style = payload.get("answer_style")
    actual_style = answer_style.get("style") if isinstance(answer_style, dict) else None
    if actual_style != expected_answer_style:
        return [f"{case_id}: expected answer_style={expected_answer_style}, got {actual_style}"]
    return []


def evaluate_case(case: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    failures.extend(_validate_structure(case))
    failures.extend(_validate_intent(case))
    failures.extend(_validate_frame_and_recipe(case))
    failures.extend(_validate_critic(case))
    failures.extend(_validate_answer_style(case))
    return failures


def evaluate_fixture(path: Path = DEFAULT_FIXTURE_PATH) -> dict[str, Any]:
    cases = load_cases(path)
    failures_by_case: dict[str, list[str]] = {}
    for case in cases:
        case_id = str(case.get("id") or "<missing-id>")
        failures = evaluate_case(case)
        if failures:
            failures_by_case[case_id] = failures

    failed = len(failures_by_case)
    total = len(cases)
    return {
        "total": total,
        "passed": total - failed,
        "failed": failed,
        "failures": failures_by_case,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE_PATH,
        help="Path to ai_agent_golden_questions.json",
    )
    args = parser.parse_args()

    result = evaluate_fixture(args.fixture)
    print("AI Agent golden-question evaluation")
    print(f"cases: {result['total']}")
    print(f"passed: {result['passed']}")
    print(f"failed: {result['failed']}")

    if result["failed"]:
        for case_id, failures in result["failures"].items():
            print(f"\nFAIL {case_id}")
            for failure in failures:
                print(f"- {failure}")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
