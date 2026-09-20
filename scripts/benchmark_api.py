#!/usr/bin/env python3
"""Measure observed local HTTP requests; first-request is never inferred cold."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import performance_contract as contract
from scripts.performance_catalog import endpoint_catalog

DEFAULT_BASE_URL = "http://localhost:8000"
TIMEOUT = 120.0
DEFAULT_SLOW_MS = 500
DEFAULT_RUNS = 22
ENDPOINTS = [
    r["endpoint"]
    for r in endpoint_catalog()
    if r["usage"] in {"current", "compatible"} and r["configured"]
]


def measure(
    endpoint,
    runs=DEFAULT_RUNS,
    base_url=DEFAULT_BASE_URL,
    *,
    context=None,
    params=None,
    warmup=False,
    headers=None,
    process_id=None,
    process_cold=False,
):
    import httpx

    context = context or contract.metadata()
    values = []
    previous_pid = None
    with httpx.Client(
        base_url=contract.local_url(base_url), timeout=TIMEOUT, trust_env=False
    ) as client:
        for i in range(runs + int(warmup)):
            # A live external process cannot be identified as cold. Warm is only a
            # repeated request in this series; no claim of memory-cache hit.
            observed_pid = process_id or contract.process_identity(base_url)
            state = (
                "cold"
                if i == 0 and process_cold
                else "warm"
                if i > 0 and observed_pid and observed_pid == previous_pid
                else "unknown"
            )
            value, _ = contract.request(
                client,
                endpoint,
                params,
                context=context,
                process={
                    "state": state,
                    "id": observed_pid,
                    "evidence": "owned_fresh_process"
                    if process_cold
                    else "same_service_request_sequence",
                },
                sequence=i,
                headers=headers,
            )
            value["role"] = "warmup" if warmup and i == 0 else "measurement"
            previous_pid = observed_pid
            values.append(value)
    warm = contract.summarize([v for v in values if v["process"]["state"] == "warm"])
    last = values[-1]["http"]
    return {
        "endpoint": endpoint,
        "status": last["status"],
        "samples": values,
        "summary": contract.summarize(values),
        "cold_p50": None,
        "cold_p95": None,
        "cold_samples": [],
        "hot_p50": warm["median_ms"] / 1000 if warm["median_ms"] is not None else None,
        "hot_p95": warm["p95_ms"] / 1000 if warm["p95_ms"] is not None else None,
        "hot_samples": [
            v["timing"]["total_ms"] / 1000
            for v in values
            if v["process"]["state"] == "warm" and v["success"]
        ],
        "raw_kb": last["raw_bytes"] / 1024 if last["raw_bytes"] is not None else None,
        "gzip_kb": last["compressed_bytes"] / 1024 if last["content_encoding"] == "gzip" else None,
        "compression_ratio": compression_ratio(
            last["raw_bytes"] or 0, last["compressed_bytes"] or 0
        ),
    }


def compression_ratio(raw_size, gzip_size):
    return round(max(0, (1 - gzip_size / raw_size) * 100), 1) if raw_size else 0


def find_slow_results(results, slow_ms=DEFAULT_SLOW_MS):
    return sorted(
        [
            r
            for r in results
            if isinstance(r.get("hot_p95"), (float, int)) and r["hot_p95"] > slow_ms / 1000
        ],
        key=lambda r: r["hot_p95"],
        reverse=True,
    )


def build_json_report(results, base_url=DEFAULT_BASE_URL, slow_ms=DEFAULT_SLOW_MS, context=None):
    slow = find_slow_results(results, slow_ms)
    samples = [s for r in results for s in r.get("samples", [])]
    return contract.report(
        "benchmark_api",
        context or contract.metadata(),
        samples,
        base_url=base_url,
        slow_ms=slow_ms,
        result_count=len(results),
        slow_count=len(slow),
        slow_endpoints=slow,
        results=results,
    )


def render_markdown(results, base_url=DEFAULT_BASE_URL, slow_ms=DEFAULT_SLOW_MS):
    lines = [
        "# API Performance Benchmark",
        "",
        f"Base URL: {base_url}",
        "",
        "| Endpoint | HTTP | Warm median s | Warm P95 s | Success / Failure |",
        "|---|---:|---:|---:|---|",
    ]
    for r in results:
        summary = r.get("summary", {})
        lines.append(
            f"| `{r['endpoint']}` | {r.get('status')} | {r.get('hot_p50')} | {r.get('hot_p95')} | {summary.get('success_count', '?')} / {summary.get('failure_count', '?')} |"
        )
    lines += ["", f"## Slow Endpoints (>{slow_ms:.0f}ms hot P95)", ""]
    lines += [
        f"- `{r['endpoint']}`: {r['hot_p95'] * 1000:.2f}ms"
        for r in find_slow_results(results, slow_ms)
    ]
    lines += [
        "",
        "First request has unknown process state unless owned fresh process evidence exists. Warm does not mean cache hit.",
        "P95 requires 20 valid warm samples per state. Null P95 is insufficient evidence, not a pass. Compressed bytes come from the HTTP stream.",
    ]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--endpoint")
    p.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help="default 22: first observed + 21 same-process warm requests",
    )
    p.add_argument("--warmup", action="store_true", help="Record an additional warmup attempt")
    p.add_argument("--slow-ms", type=float, default=DEFAULT_SLOW_MS)
    p.add_argument("--fail-on-slow", action="store_true")
    p.add_argument("--output", type=Path)
    p.add_argument("--json-output", type=Path)
    p.add_argument("--catalog", action="store_true")
    p.add_argument("--track-id", type=int)
    p.add_argument("--album-project-id", type=int)
    p.add_argument("--artist")
    p.add_argument("--year", type=int)
    p.add_argument("--entity-key")
    p.add_argument("--job-id")
    p.add_argument("--post-id")
    p.add_argument("--params", default="{}", help="JSON request parameters")
    p.add_argument(
        "--surface",
        choices=["auto", "public-readonly", "private-admin"],
        default="auto",
        help="auto uses each consumer's actual surface; explicit values override it",
    )
    p.add_argument(
        "--independent-processes",
        type=int,
        default=0,
        help="At least 3 owned backend processes on a temporary copy",
    )
    p.add_argument("--snapshot-root", type=Path)
    contract.add_context_args(p)
    a = p.parse_args()
    if a.runs < 1:
        p.error("--runs must be positive")
    catalog = endpoint_catalog(
        a.track_id, a.album_project_id, a.artist, a.year, a.entity_key, a.job_id, a.post_id
    )
    if a.catalog:
        print(json.dumps(catalog, ensure_ascii=False, indent=2))
        return 0
    context = contract.context_from_args(a)
    targets = (
        [{"endpoint": a.endpoint, "params": json.loads(a.params)}]
        if a.endpoint
        else [r for r in catalog if r["usage"] in {"current", "compatible"} and r["configured"]]
    )
    if not targets:
        p.error("No configured benchmark targets; an empty run cannot pass")
    results = []
    if a.independent_processes:
        from scripts.performance_server import owned_server

        if a.independent_processes < 3 or not a.db_path or not a.snapshot_root:
            p.error("cold requires >=3 processes, --db-path and --snapshot-root")
        for target in targets:
            for _ in range(a.independent_processes):
                with owned_server(a.db_path, a.snapshot_root) as (url, pid):
                    results.append(
                        measure(
                            target["endpoint"],
                            a.runs,
                            url,
                            context=context,
                            params=target["params"],
                            process_id=pid,
                            process_cold=True,
                            headers={
                                "X-SpotifyStats-Surface": target.get("surface", "public-readonly")
                                if a.surface == "auto"
                                else a.surface
                            },
                        )
                    )
    else:
        for target in targets:
            results.append(
                measure(
                    target["endpoint"],
                    a.runs,
                    a.base_url,
                    context=context,
                    params=target["params"],
                    warmup=a.warmup,
                    headers={
                        "X-SpotifyStats-Surface": target.get("surface", "public-readonly")
                        if a.surface == "auto"
                        else a.surface
                    },
                )
            )
    output = build_json_report(results, a.base_url, a.slow_ms, context)
    output["catalog"] = catalog
    output["unconfigured_targets"] = [r for r in catalog if not r["configured"]]
    markdown = render_markdown(results, a.base_url, a.slow_ms)
    print(markdown)
    if a.output:
        a.output.write_text(markdown + "\n")
    if a.json_output:
        a.json_output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    failed = any(not s["success"] for s in output["samples"])
    insufficient = any(r.get("hot_p95") is None for r in results)
    return int(
        bool(failed or (a.fail_on_slow and (find_slow_results(results, a.slow_ms) or insufficient)))
    )


if __name__ == "__main__":
    raise SystemExit(main())
