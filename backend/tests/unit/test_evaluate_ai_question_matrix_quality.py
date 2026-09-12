from __future__ import annotations

import pytest

from scripts.evaluate_ai_question_matrix import (
    MatrixCase,
    _grade_case,
    _performance_gate,
    _performance_summary,
)

pytestmark = pytest.mark.unit


def _task_result(**overrides):
    result = {
        "agent_runtime": "v2",
        "answer": "基于本地证据，可以确认播放事实。",
        "validation_issues": [],
        "evidence_coverage": 1.0,
        "claim_ledger": {"unsupported_literals": []},
        "answer_contract": {
            "ok": True,
            "classification": "pass",
            "dimensions": {
                name: {"passed": True, "applicable": True, "issues": []}
                for name in (
                    "grounded",
                    "complete",
                    "informative",
                    "constraint_compliant",
                    "readable",
                )
            },
        },
        "tool_evidence": [
            {
                "schema_version": "tool_evidence_v2",
                "tool_name": "analysis_stats",
                "constraint_fingerprint": "abc123",
            }
        ],
        "tools": [{"tool_name": "analysis_stats", "status": "ok"}],
        "grounded_fallback_used": False,
        "runtime_metrics": {
            "total_elapsed_ms": 1_000,
            "tool_call_count": 1,
        },
    }
    result.update(overrides)
    return {"status": "done", "task_id": "task-1", "result": result}


def _events():
    return {
        "trajectory": [
            {"event_type": "turn_started"},
            {"event_type": "model_message"},
            {"event_type": "turn_ended"},
        ]
    }


def test_live_quality_gate_fails_unsupported_numeric_claims() -> None:
    case = MatrixCase("AI-01", "问题", "预期", [])
    task = _task_result(
        evidence_coverage=0.5,
        claim_ledger={"unsupported_literals": ["250"]},
    )

    graded = _grade_case(case, task, _events())

    assert graded["grade"] == "Fail"
    assert any("evidence coverage" in issue for issue in graded["issues"])
    assert any("unsupported numeric claims" in issue for issue in graded["issues"])


def test_live_quality_gate_marks_slow_and_excessive_tool_turn_partial() -> None:
    case = MatrixCase("AI-01", "问题", "预期", [])
    task = _task_result(
        grounded_fallback_used=True,
        runtime_metrics={"total_elapsed_ms": 180_001, "tool_call_count": 9},
    )

    graded = _grade_case(case, task, _events())

    assert graded["grade"] == "Partial"
    assert len(graded["issues"]) == 2


def test_live_quality_gate_accepts_fully_grounded_deterministic_fallback() -> None:
    case = MatrixCase("AI-01", "问题", "预期", [])
    task = _task_result(grounded_fallback_used=True)

    graded = _grade_case(case, task, _events())

    assert graded["grade"] == "Pass"
    assert graded["grounded_fallback_used"] is True


def test_live_quality_gate_rejects_missing_answer_contract_or_tool_evidence() -> None:
    case = MatrixCase("AI-01", "问题", "预期", [])
    task = _task_result(answer_contract={}, tool_evidence=[])

    graded = _grade_case(case, task, _events())

    assert graded["grade"] == "Fail"
    assert any("answer quality contract" in issue for issue in graded["issues"])
    assert any("tool_evidence_v2" in issue for issue in graded["issues"])


def test_performance_summary_and_gate_use_nearest_rank_p95() -> None:
    results = [
        {
            "grade": "Pass",
            "runtime_metrics": {
                "total_elapsed_ms": index * 1_000,
                "model_elapsed_ms": index * 600,
                "tool_elapsed_ms": index * 300,
            },
        }
        for index in range(1, 31)
    ]
    summary = _performance_summary({"results": results})

    assert summary["sample_count"] == 30
    assert summary["pass_rate"] == 1.0
    assert summary["total_elapsed_ms"]["p95"] == 29_000
    assert summary["tool_elapsed_ms"]["p95"] == 8_700
    assert (
        _performance_gate(
            summary,
            min_samples=30,
            min_pass_rate=1.0,
            max_p95_ms=60_000,
            max_tool_p95_ms=45_000,
        )
        == []
    )


def test_performance_gate_rejects_missing_samples_and_slow_p95() -> None:
    summary = _performance_summary(
        {
            "results": [
                {
                    "grade": "Partial",
                    "runtime_metrics": {
                        "total_elapsed_ms": 61_000,
                        "tool_elapsed_ms": 46_000,
                    },
                }
            ]
        }
    )

    failures = _performance_gate(
        summary,
        min_samples=30,
        min_pass_rate=1.0,
        max_p95_ms=60_000,
        max_tool_p95_ms=45_000,
    )

    assert len(failures) == 4
