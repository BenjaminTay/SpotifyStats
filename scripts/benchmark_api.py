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
import statistics
import time

import httpx

BASE_URL = "http://localhost:8000"
TIMEOUT = 120.0  # cold Billboard data computation can be slow

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


def measure(endpoint: str, runs: int = 3) -> dict:
    """Measure cold and hot response times for an endpoint."""
    times_cold = []
    times_hot = []
    raw_size = 0
    gzip_size = 0
    status = 0

    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
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
        "compression_ratio": round((1 - gzip_size / raw_size) * 100, 1) if raw_size > 0 else 0,
    }


def _p50(values: list[float]) -> float:
    return statistics.median(values)


def _p95(values: list[float]) -> float:
    if len(values) < 2:
        return values[0] if values else 0.0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * 0.95)
    return sorted_vals[min(idx, len(sorted_vals) - 1)]


def render_markdown(results: list[dict]) -> str:
    """Render benchmark results as a Markdown table."""
    lines = [
        "# API Performance Benchmark",
        "",
        f"> Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"> Base URL: {BASE_URL}",
        "",
        "## Response Time (seconds)",
        "",
        "| Endpoint | Status | Cold P50 | Cold P95 | Hot P50 | Hot P95 | Raw | Gzip | Ratio |",
        "|----------|--------|----------|----------|---------|---------|-----|------|-------|",
    ]

    for r in results:
        cold_p50 = f"{r['cold_p50']:.2f}" if r["cold_p50"] is not None else "—"
        cold_p95 = f"{r['cold_p95']:.2f}" if r["cold_p95"] is not None else "—"
        hot_p50 = f"{r['hot_p50']:.2f}" if r["hot_p50"] is not None else "—"
        hot_p95 = f"{r['hot_p95']:.2f}" if r["hot_p95"] is not None else "—"
        lines.append(
            f"| `{r['endpoint']}` | {r['status']} | {cold_p50} | {cold_p95} | "
            f"{hot_p50} | {hot_p95} | {r['raw_kb']}KB | {r['gzip_kb']}KB | "
            f"{r['compression_ratio']}% |"
        )

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
    parser.add_argument("--endpoint", help="Benchmark a single endpoint")
    parser.add_argument("--runs", type=int, default=3, help="Number of runs per endpoint")
    parser.add_argument(
        "--warmup", action="store_true", help="Pre-warm caches, then measure hot only"
    )
    parser.add_argument("--output", help="Write Markdown report to file")
    args = parser.parse_args()

    targets = [args.endpoint] if args.endpoint else ENDPOINTS

    if args.warmup:
        print("Pre-warming caches...")
        with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
            for ep in targets:
                client.get(ep)
        print("Warmup complete.\n")

    results = []
    for ep in targets:
        print(f"Benchmarking {ep} ...", end=" ", flush=True)
        try:
            r = measure(ep, runs=args.runs)
            results.append(r)
            cold_str = f"cold={r['cold_p50']:.2f}s" if r["cold_p50"] is not None else "cold=N/A"
            hot_str = f"hot={r['hot_p50']:.2f}s" if r["hot_p50"] is not None else "hot=N/A"
            print(f"OK ({cold_str}, {hot_str}, {r['raw_kb']}KB/{r['gzip_kb']}KB gzip)")
        except Exception as e:
            print(f"FAILED: {e}")
            results.append({"endpoint": ep, "status": "ERR", "error": str(e)})

    markdown = render_markdown(results)
    print("\n" + markdown)

    if args.output:
        with open(args.output, "w") as f:
            f.write(markdown)
        print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
