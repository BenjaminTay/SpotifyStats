from __future__ import annotations

import pytest

from scripts.evaluate_ai_report_performance import evaluate_report_runs, grade_report_task

pytestmark = pytest.mark.unit


def _task(*, hit: bool, build_count: int, fallback_count: int = 0):
    quality = {
        "report_mode": "visual_yearly_artifact",
        "section_count": 6,
        "article_length": 3200,
        "critic_passed": True,
        "fact_validation_passed": True,
        "final_artifact_quality_passed": True,
        "section_checkpoints_passed": True,
    }
    return {
        "task_id": "report-task",
        "status": "done",
        "result": {
            "metadata": quality,
            "runtime_metrics": {
                "total_elapsed_ms": 100,
                "context_snapshot_hit": hit,
                "context_build_count": build_count,
            },
            "section_writer_metadata": {
                "model_accepted_count": 6 - fallback_count,
                "fallback_count": fallback_count,
                "attempt_count": 6,
                "empty_reasons": {},
            },
        },
    }


def test_report_performance_accepts_one_cold_and_one_warm_run() -> None:
    cold = grade_report_task(_task(hit=False, build_count=1), 120_000)
    warm = grade_report_task(_task(hit=True, build_count=0, fallback_count=1), 90_000)

    result = evaluate_report_runs(
        [cold, warm],
        max_cold_ms=240_000,
        max_warm_ms=180_000,
        max_fallback_sections=2,
        expect_first="cold",
    )

    assert result["ok"] is True
    assert result["latency_ms"]["p95"] == 120_000
    assert result["fallback_sections"]["total"] == 1


def test_report_performance_rejects_rebuild_and_excessive_fallback() -> None:
    first = grade_report_task(_task(hit=False, build_count=2), 250_000)
    second = grade_report_task(_task(hit=False, build_count=1, fallback_count=3), 190_000)

    result = evaluate_report_runs(
        [first, second],
        max_cold_ms=240_000,
        max_warm_ms=180_000,
        max_fallback_sections=2,
        expect_first="cold",
    )

    assert result["ok"] is False
    assert any("more than once" in failure for failure in result["failures"])
    assert any("fallback count" in failure for failure in result["failures"])
    assert any("expected exact snapshot hit" in failure for failure in result["failures"])


def test_report_grade_requires_all_quality_gates() -> None:
    task = _task(hit=True, build_count=0)
    task["result"]["metadata"]["critic_passed"] = False

    graded = grade_report_task(task, 10)

    assert graded["ok"] is False
    assert graded["issues"] == ["quality gate critic_passed did not pass"]
