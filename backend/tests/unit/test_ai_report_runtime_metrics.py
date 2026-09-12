from __future__ import annotations

from backend.domains.ai_reports.runtime_metrics import ReportRuntimeMetrics


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


def test_report_runtime_metrics_accumulates_low_cardinality_stages() -> None:
    clock = _Clock()
    metrics = ReportRuntimeMetrics(clock=clock)

    with metrics.stage("context_snapshot_build"):
        clock.value = 0.125
    with metrics.stage("context_snapshot_build"):
        clock.value = 0.200

    metrics.record_context_snapshot(cache_hit=False, snapshot_key="abcdef" * 8, built=True)
    metrics.record_provider_call(
        {
            "provider": "deepseek",
            "model": "example",
            "finish_reason": "stop",
            "empty_reason": "",
            "elapsed_ms": 80,
            "content_chars": 240,
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        },
        stage="writer",
    )

    payload = metrics.to_dict()
    assert payload["stages_ms"] == {"context_snapshot_build": 200}
    assert payload["stage_counts"] == {"context_snapshot_build": 2}
    assert payload["context_snapshot_key"] == "abcdefabcdefabcd"
    assert payload["context_build_count"] == 1
    assert payload["provider_calls"] == [
        {
            "stage": "writer",
            "provider": "deepseek",
            "model": "example",
            "finish_reason": "stop",
            "empty_reason": "",
            "elapsed_ms": 80,
            "input_tokens": 10,
            "output_tokens": 20,
            "content_chars": 240,
        }
    ]
