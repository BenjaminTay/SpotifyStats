from backend.domains.agent_runtime.metrics import RuntimeMetrics


def test_runtime_metrics_separate_parallel_wall_and_cumulative_tool_time() -> None:
    metrics = RuntimeMetrics(clock=lambda: 1.0)

    metrics.record_model(
        elapsed_ms=80,
        usage={"prompt_tokens_details": {"cached_tokens": 20}},
        input_chars=100,
    )
    metrics.record_tool(
        elapsed_ms=120,
        result_bytes=10,
        cache_hit=True,
        include_wall_time=False,
    )
    metrics.record_tool(
        elapsed_ms=90,
        result_bytes=20,
        include_wall_time=False,
    )
    metrics.record_tool_batch_wall(125)
    metrics.record_tool(
        elapsed_ms=0,
        result_bytes=0,
        deduplicated=True,
        executed=False,
    )

    snapshot = metrics.snapshot()
    assert snapshot["model_elapsed_ms"] == 80
    assert snapshot["model_wait_elapsed_ms"] == 80
    assert snapshot["model_cache_hit_elapsed_ms"] == 80
    assert snapshot["tool_elapsed_ms"] == 125
    assert snapshot["tool_wall_elapsed_ms"] == 125
    assert snapshot["tool_cumulative_elapsed_ms"] == 210
    assert snapshot["tool_cache_hit_elapsed_ms"] == 120
    assert snapshot["tool_call_count"] == 2
    assert snapshot["tool_cache_hit_count"] == 1
    assert snapshot["tool_dedup_hit_count"] == 1
    assert snapshot["cache_hit_count"] == 3


def test_runtime_metrics_validation_timer_counts_complete_stage_once() -> None:
    now = [0.0]
    metrics = RuntimeMetrics(clock=lambda: now[0])

    now[0] = 0.010
    with metrics.measure_validation():
        now[0] = 0.026

    assert metrics.snapshot()["validation_elapsed_ms"] == 16
