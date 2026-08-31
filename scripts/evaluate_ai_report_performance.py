#!/usr/bin/env python3
"""Run and grade yearly AI report tasks with explicit quality and latency SLOs."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TERMINAL_STATUSES = {"done", "error", "cancelled"}


def _http_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    request = Request(
        url,
        data=data,
        method=method,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode()
    except HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"{method} {url} returned HTTP {exc.code}: {body[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc}") from exc
    return json.loads(body) if body else {}


def _run_task(
    backend_url: str,
    payload: dict[str, Any],
    *,
    timeout: float,
    poll_interval: float,
) -> tuple[dict[str, Any], int]:
    started = time.monotonic()
    created = _http_json("POST", f"{backend_url.rstrip('/')}/api/ai/tasks/report", payload)
    task_id = created.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise RuntimeError(f"report task did not return task_id: {created}")
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = _http_json("GET", f"{backend_url.rstrip('/')}/api/ai/tasks/{task_id}")
        if last.get("status") in TERMINAL_STATUSES:
            return last, max(0, round((time.monotonic() - started) * 1000))
        time.sleep(poll_interval)
    raise TimeoutError(f"report task {task_id} did not finish within {timeout:.0f}s; last={last}")


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(percentile * len(ordered)) - 1)], 2)


def grade_report_task(task: dict[str, Any], client_elapsed_ms: int) -> dict[str, Any]:
    result = _dict(task.get("result"))
    metadata = _dict(result.get("metadata"))
    runtime = _dict(result.get("runtime_metrics") or metadata.get("runtime_metrics"))
    section_writer = _dict(result.get("section_writer_metadata"))
    issues: list[str] = []
    if task.get("status") != "done":
        issues.append(
            f"task status is {task.get('status')}: {task.get('error') or task.get('message')}"
        )
    for key in (
        "critic_passed",
        "fact_validation_passed",
        "final_artifact_quality_passed",
        "section_checkpoints_passed",
    ):
        if metadata.get(key) is not True:
            issues.append(f"quality gate {key} did not pass")
    if int(metadata.get("section_count") or 0) < 6:
        issues.append("report contains fewer than six sections")
    if not runtime:
        issues.append("runtime_metrics is missing")
    if not section_writer:
        issues.append("section_writer_metadata is missing")
    return {
        "task_id": task.get("task_id"),
        "status": task.get("status"),
        "ok": not issues,
        "issues": issues,
        "client_elapsed_ms": client_elapsed_ms,
        "runtime_metrics": runtime,
        "section_writer": {
            "model_accepted_count": int(section_writer.get("model_accepted_count") or 0),
            "fallback_count": int(section_writer.get("fallback_count") or 0),
            "attempt_count": int(section_writer.get("attempt_count") or 0),
            "empty_reasons": section_writer.get("empty_reasons") or {},
        },
        "quality": {
            "section_count": int(metadata.get("section_count") or 0),
            "article_length": int(metadata.get("article_length") or 0),
            "critic_passed": metadata.get("critic_passed") is True,
            "fact_validation_passed": metadata.get("fact_validation_passed") is True,
            "final_artifact_quality_passed": metadata.get("final_artifact_quality_passed") is True,
            "section_checkpoints_passed": metadata.get("section_checkpoints_passed") is True,
            "fallback_level": metadata.get("fallback_level"),
        },
    }


def evaluate_report_runs(
    runs: list[dict[str, Any]],
    *,
    max_cold_ms: float,
    max_warm_ms: float,
    max_fallback_sections: int,
    expect_first: str,
) -> dict[str, Any]:
    failures: list[str] = []
    for index, run in enumerate(runs):
        failures.extend(f"run {index + 1}: {issue}" for issue in run.get("issues", []))
        runtime = _dict(run.get("runtime_metrics"))
        fallback_count = int(_dict(run.get("section_writer")).get("fallback_count") or 0)
        if fallback_count > max_fallback_sections:
            failures.append(
                f"run {index + 1}: section fallback count {fallback_count} > {max_fallback_sections}"
            )
        if int(runtime.get("context_build_count") or 0) > 1:
            failures.append(f"run {index + 1}: context built more than once")

    if runs:
        first_runtime = _dict(runs[0].get("runtime_metrics"))
        first_hit = first_runtime.get("context_snapshot_hit") is True
        if expect_first == "cold" and first_hit:
            failures.append("first run expected a cold context build but hit a snapshot")
        if expect_first == "warm" and not first_hit:
            failures.append("first run expected a warm snapshot hit")
        if expect_first == "cold" and int(first_runtime.get("context_build_count") or 0) != 1:
            failures.append("cold run must build the yearly context exactly once")
        if float(runs[0].get("client_elapsed_ms") or 0) > max_cold_ms:
            failures.append(
                f"cold/client run latency {runs[0]['client_elapsed_ms']}ms > {max_cold_ms:.0f}ms"
            )
    for index, run in enumerate(runs[1:], start=2):
        runtime = _dict(run.get("runtime_metrics"))
        if runtime.get("context_snapshot_hit") is not True:
            failures.append(f"run {index}: expected exact snapshot hit")
        if int(runtime.get("context_build_count") or 0) != 0:
            failures.append(f"run {index}: warm run rebuilt context")
        if float(run.get("client_elapsed_ms") or 0) > max_warm_ms:
            failures.append(
                f"run {index}: warm latency {run['client_elapsed_ms']}ms > {max_warm_ms:.0f}ms"
            )

    elapsed = [float(run.get("client_elapsed_ms") or 0) for run in runs]
    fallback_counts = [
        int(_dict(run.get("section_writer")).get("fallback_count") or 0) for run in runs
    ]
    return {
        "schema_version": "ai_report_performance_v1",
        "ok": not failures,
        "failures": failures,
        "sample_count": len(runs),
        "latency_ms": {
            "p50": _percentile(elapsed, 0.50),
            "p95": _percentile(elapsed, 0.95),
            "max": max(elapsed, default=None),
        },
        "fallback_sections": {
            "total": sum(fallback_counts),
            "max_per_run": max(fallback_counts, default=0),
        },
        "runs": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--poll-interval", type=float, default=1.5)
    parser.add_argument("--expect-first", choices=("cold", "warm", "either"), default="either")
    parser.add_argument("--max-cold-ms", type=float, default=240_000.0)
    parser.add_argument("--max-warm-ms", type=float, default=180_000.0)
    parser.add_argument("--max-fallback-sections", type=int, default=2)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")

    request_payload = {
        "report_type": "yearly",
        "action": "generate",
        "report_mode": "visual_yearly_artifact",
        "writer_pipeline": "agent_synthesis_v2",
        "force": True,
        "year": args.year,
        "min_ms": 30000,
        "music_only": True,
        "merge_enabled": True,
        "dynamic_threshold": True,
        "max_merge_gap_minutes": 5,
    }
    runs: list[dict[str, Any]] = []
    for index in range(args.runs):
        print(f"[{index + 1}/{args.runs}] yearly report {args.year}", flush=True)
        try:
            task, elapsed_ms = _run_task(
                args.backend_url,
                request_payload,
                timeout=args.timeout,
                poll_interval=args.poll_interval,
            )
            graded = grade_report_task(task, elapsed_ms)
        except Exception as exc:
            graded = {
                "task_id": None,
                "status": "error",
                "ok": False,
                "issues": [str(exc)],
                "client_elapsed_ms": 0,
                "runtime_metrics": {},
                "section_writer": {},
                "quality": {},
            }
        print(
            f"  -> {'Pass' if graded['ok'] else 'Fail'} "
            f"{graded.get('task_id') or ''} {graded['client_elapsed_ms']}ms",
            flush=True,
        )
        runs.append(graded)

    result = evaluate_report_runs(
        runs,
        max_cold_ms=args.max_cold_ms,
        max_warm_ms=args.max_warm_ms,
        max_fallback_sections=args.max_fallback_sections,
        expect_first=args.expect_first,
    )
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("AI yearly report performance evaluation")
        print(f"samples: {result['sample_count']}")
        print(f"p95: {result['latency_ms']['p95']}ms")
        print(f"fallback sections: {result['fallback_sections']['total']}")
        print("PASS" if result["ok"] else "FAIL")
        for failure in result["failures"]:
            print(f"- {failure}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
