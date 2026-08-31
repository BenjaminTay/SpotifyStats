from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def _sample_result(endpoint: str, hot_p95: float) -> dict:
    return {
        "endpoint": endpoint,
        "status": 200,
        "cold_p50": 0.2,
        "cold_p95": 0.2,
        "hot_p50": hot_p95,
        "hot_p95": hot_p95,
        "cold_samples": [0.2],
        "hot_samples": [hot_p95],
        "raw_kb": 10.0,
        "gzip_kb": 2.0,
        "compression_ratio": 80.0,
    }


def test_benchmark_api_exposes_reusable_performance_cli():
    script = ROOT / "scripts" / "benchmark_api.py"

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "--base-url" in result.stdout
    assert "--slow-ms" in result.stdout
    assert "--fail-on-slow" in result.stdout
    assert "--json-output" in result.stdout
    assert "default 22: 1 cold + 21" in result.stdout
    assert "hot)" in result.stdout


def test_benchmark_api_default_has_enough_hot_samples_for_p95():
    from scripts.benchmark_api import DEFAULT_RUNS

    assert DEFAULT_RUNS == 22


def test_benchmark_api_marks_slow_hot_p95_endpoints():
    from scripts.benchmark_api import find_slow_results, render_markdown

    results = [
        _sample_result("/api/fast", hot_p95=0.12),
        _sample_result("/api/slow", hot_p95=0.75),
    ]

    slow_results = find_slow_results(results, slow_ms=500)
    markdown = render_markdown(results, base_url="http://127.0.0.1:8000", slow_ms=500)

    assert [result["endpoint"] for result in slow_results] == ["/api/slow"]
    assert "Slow Endpoints (>500ms hot P95)" in markdown
    assert "`/api/slow`" in markdown
    assert "`/api/fast`" not in markdown.split("Slow Endpoints (>500ms hot P95)", 1)[1]


def test_benchmark_api_builds_machine_readable_report():
    from scripts.benchmark_api import build_json_report

    results = [
        _sample_result("/api/fast", hot_p95=0.12),
        _sample_result("/api/slow", hot_p95=0.75),
    ]

    report = build_json_report(
        results,
        base_url="http://127.0.0.1:8000",
        slow_ms=500,
    )

    assert report["base_url"] == "http://127.0.0.1:8000"
    assert report["slow_ms"] == 500
    assert report["result_count"] == 2
    assert [result["endpoint"] for result in report["slow_endpoints"]] == ["/api/slow"]


def test_benchmark_api_compression_ratio_never_goes_negative_for_tiny_payloads():
    from scripts.benchmark_api import compression_ratio

    assert compression_ratio(raw_size=15, gzip_size=35) == 0.0
    assert compression_ratio(raw_size=1000, gzip_size=250) == 75.0
