#!/usr/bin/env python3
"""API performance benchmark script.

Measures cold-start (cache miss) and hot-request (cache hit) response times
for key Billboard endpoints, plus response body sizes (raw and gzip).

Usage:
    python scripts/benchmark_api.py                    # all endpoints, 3 runs each
    python scripts/benchmark_api.py --endpoint /api/billboard/data  # single endpoint
    python scripts/benchmark_api.py --warmup           # pre-warm caches, then measure hot only
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import statistics
import time

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
TIMEOUT = 120.0  # cold Billboard data computation can be slow
DEFAULT_SLOW_MS = 500

ENDPOINTS = [
    "/api/billboard/data",
    "/api/billboard/weekly",
    "/api/billboard/records",
    "/api/billboard/power-scores",
    "/api/billboard/summaries",
    "/api/billboard/all-time",
    "/api/dashboard/full",
    "/api/health",
]


def measure(endpoint: str, runs: int = 3, base_url: str = DEFAULT_BASE_URL) -> dict:
    """Measure cold and hot response times for an endpoint."""
    times_cold = []
    times_hot = []
    raw_size = 0
    gzip_size = 0
    status = 0

    with httpx.Client(base_url=base_url, timeout=TIMEOUT) as client:
        # Cold: first run (caches likely cold if not pre-warmed)
        for i in range(runs):
            t0 = time.perf_counter()
            resp = client.get(endpoint)
            elapsed = time.perf_counter() - t0
            status = resp.status_code

            content = resp.content
            raw_size = len(content)

            # Gzip size
            buf = io.BytesIO()
            with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
                gz.write(content)
            gzip_size = buf.tell()

            if i == 0:
                times_cold.append(elapsed)
            else:
                times_hot.append(elapsed)

    return {
        "endpoint": endpoint,
        "status": status,
        "cold_p50": _p50(times_cold) if times_cold else None,
        "cold_p95": _p95(times_cold) if times_cold else None,
        "hot_p50": _p50(times_hot) if times_hot else None,
        "hot_p95": _p95(times_hot) if times_hot else None,
        "cold_samples": times_cold,
        "hot_samples": times_hot,
        "raw_kb": round(raw_size / 1024, 1),
        "gzip_kb": round(gzip_size / 1024, 1),
        "compression_ratio": compression_ratio(raw_size, gzip_size),
    }


def _p50(values: list[float]) -> float:
    return statistics.median(values)


def _p95(values: list[float]) -> float:
    if len(values) < 2:
        return values[0] if values else 0.0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * 0.95)
    return sorted_vals[min(idx, len(sorted_vals) - 1)]


def compression_ratio(raw_size: int, gzip_size: int) -> float:
    if raw_size <= 0:
        return 0.0
    ratio = (1 - gzip_size / raw_size) * 100
    return round(max(0.0, ratio), 1)


def find_slow_results(results: list[dict], slow_ms: float = DEFAULT_SLOW_MS) -> list[dict]:
    threshold_seconds = slow_ms / 1000
    slow_results = [
        result
        for result in results
        if isinstance(result.get("hot_p95"), (float, int)) and result["hot_p95"] > threshold_seconds
    ]
    return sorted(slow_results, key=lambda result: result["hot_p95"], reverse=True)


def build_json_report(
    results: list[dict], base_url: str = DEFAULT_BASE_URL, slow_ms: float = DEFAULT_SLOW_MS
) -> dict:
    slow_results = find_slow_results(results, slow_ms=slow_ms)
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base_url": base_url,
        "slow_ms": slow_ms,
        "result_count": len(results),
        "slow_count": len(slow_results),
        "slow_endpoints": slow_results,
        "results": results,
    }


def render_markdown(
    results: list[dict], base_url: str = DEFAULT_BASE_URL, slow_ms: float = DEFAULT_SLOW_MS
) -> str:
    """Render benchmark results as a Markdown table."""
    lines = [
        "# API Performance Benchmark",
        "",
        f"> Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"> Base URL: {base_url}",
        f"> Slow threshold: hot P95 > {slow_ms:.0f}ms",
        "",
        "## Response Time (seconds)",
        "",
        "| Endpoint | Status | Cold P50 | Cold P95 | Hot P50 | Hot P95 | Raw | Gzip | Ratio |",
        "|----------|--------|----------|----------|---------|---------|-----|------|-------|",
    ]

    for r in results:
        if "error" in r:
            lines.append(
                f"| `{r['endpoint']}` | ERR | — | — | — | — | — | — | — |"
            )
            continue
        cold_p50 = f"{r['cold_p50']:.2f}" if r["cold_p50"] is not None else "—"
        cold_p95 = f"{r['cold_p95']:.2f}" if r["cold_p95"] is not None else "—"
        hot_p50 = f"{r['hot_p50']:.2f}" if r["hot_p50"] is not None else "—"
        hot_p95 = f"{r['hot_p95']:.2f}" if r["hot_p95"] is not None else "—"
        lines.append(
            f"| `{r['endpoint']}` | {r['status']} | {cold_p50} | {cold_p95} | "
            f"{hot_p50} | {hot_p95} | {r['raw_kb']}KB | {r['gzip_kb']}KB | "
            f"{r['compression_ratio']}% |"
        )

    slow_results = find_slow_results(results, slow_ms=slow_ms)
    lines.extend(
        [
            "",
            f"## Slow Endpoints (>{slow_ms:.0f}ms hot P95)",
            "",
        ]
    )
    if slow_results:
        lines.extend(
            [
                "| Endpoint | Hot P95 | Hot P50 | Status |",
                "|----------|---------|---------|--------|",
            ]
        )
        for r in slow_results:
            hot_p95_ms = r["hot_p95"] * 1000
            hot_p50_ms = r["hot_p50"] * 1000 if r["hot_p50"] is not None else 0
            lines.append(
                f"| `{r['endpoint']}` | {hot_p95_ms:.1f}ms | {hot_p50_ms:.1f}ms | {r['status']} |"
            )
    else:
        lines.append("No hot endpoints exceeded the configured threshold.")

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- **Cold**: first request after server start (cache miss, full computation)")
    lines.append("- **Hot**: subsequent requests (cache hit, instant response)")
    lines.append("- **P50/P95**: median and 95th percentile across runs")
    lines.append("- **Gzip**: FastAPI auto-gzip for responses > 500 bytes")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="API performance benchmark")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API base URL")
    parser.add_argument("--endpoint", help="Benchmark a single endpoint")
    parser.add_argument("--runs", type=int, default=3, help="Number of runs per endpoint")
    parser.add_argument(
        "--warmup", action="store_true", help="Pre-warm caches, then measure hot only"
    )
    parser.add_argument(
        "--slow-ms",
        type=float,
        default=DEFAULT_SLOW_MS,
        help="Slow endpoint threshold for hot P95 in milliseconds",
    )
    parser.add_argument("--fail-on-slow", action="store_true", help="Exit 1 when hot P95 exceeds threshold")
    parser.add_argument("--output", help="Write Markdown report to file")
    parser.add_argument("--json-output", help="Write machine-readable JSON report to file")
    args = parser.parse_args()

    targets = [args.endpoint] if args.endpoint else ENDPOINTS

    if args.warmup:
        print("Pre-warming caches...")
        with httpx.Client(base_url=args.base_url, timeout=TIMEOUT) as client:
            for ep in targets:
                client.get(ep)
        print("Warmup complete.\n")

    results = []
    for ep in targets:
        print(f"Benchmarking {ep} ...", end=" ", flush=True)
        try:
            r = measure(ep, runs=args.runs, base_url=args.base_url)
            results.append(r)
            cold_str = f"cold={r['cold_p50']:.2f}s" if r["cold_p50"] is not None else "cold=N/A"
            hot_str = f"hot={r['hot_p50']:.2f}s" if r["hot_p50"] is not None else "hot=N/A"
            print(f"OK ({cold_str}, {hot_str}, {r['raw_kb']}KB/{r['gzip_kb']}KB gzip)")
        except Exception as e:
            print(f"FAILED: {e}")
            results.append({"endpoint": ep, "status": "ERR", "error": str(e)})

    markdown = render_markdown(results, base_url=args.base_url, slow_ms=args.slow_ms)
    print("\n" + markdown)

    if args.output:
        with open(args.output, "w") as f:
            f.write(markdown)
        print(f"Report written to {args.output}")

    if args.json_output:
        report = build_json_report(results, base_url=args.base_url, slow_ms=args.slow_ms)
        with open(args.json_output, "w") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"JSON report written to {args.json_output}")

    slow_results = find_slow_results(results, slow_ms=args.slow_ms)
    if args.fail_on_slow and slow_results:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
