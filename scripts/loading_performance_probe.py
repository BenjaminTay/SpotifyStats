#!/usr/bin/env python3
"""Measure homepage/detail loading gates against a running local backend.

For a true cold sample, restart the backend immediately before running this
probe.  The report keeps first-request and repeated-request samples separate,
captures ``Server-Timing``, and checks concurrent same/different detail keys.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

DEFAULT_PARAMS = {
    "min_ms": 30_000,
    "music_only": "true",
    "merge_enabled": "true",
    "dynamic_threshold": "true",
    "max_merge_gap_minutes": 5,
    "merge_level": 2,
    "include_compilations": "false",
    "bb_top_n": 30,
    "bb_album_top_n": 20,
    "bb_artist_top_n": 20,
    "bb_week_start_dow": 4,
    "bb_week_start_hour": 12,
}


def _request(client: httpx.Client, path: str, params: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    response = client.get(path, params=params)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    response.raise_for_status()
    return {
        "elapsed_ms": elapsed_ms,
        "status": response.status_code,
        "bytes": len(response.content),
        "server_timing": response.headers.get("server-timing"),
    }


def _samples(
    client: httpx.Client,
    path: str,
    params: dict[str, Any],
    runs: int,
) -> dict[str, Any]:
    values = [_request(client, path, params) for _ in range(runs)]
    repeated = [sample["elapsed_ms"] for sample in values[1:]]
    return {
        "path": path,
        "first": values[0],
        "repeated": values[1:],
        "warm_p50_ms": round(statistics.median(repeated), 2) if repeated else None,
        "warm_max_ms": max(repeated) if repeated else None,
    }


def _concurrency_probe(
    base_url: str,
    track_id: int,
    other_track_id: int,
) -> dict[str, Any]:
    def fetch(track: int) -> float:
        with httpx.Client(base_url=base_url, timeout=120, trust_env=False) as client:
            return _request(
                client,
                f"/api/billboard/track/{track}",
                {**DEFAULT_PARAMS, "view": "summary"},
            )["elapsed_ms"]

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as executor:
        same = list(executor.map(fetch, (track_id, track_id)))
    same_wall = round((time.perf_counter() - started) * 1000, 2)

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as executor:
        different = list(executor.map(fetch, (track_id, other_track_id)))
    different_wall = round((time.perf_counter() - started) * 1000, 2)
    return {
        "same_key_elapsed_ms": same,
        "same_key_wall_ms": same_wall,
        "different_key_elapsed_ms": different,
        "different_key_wall_ms": different_wall,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    detail = {**DEFAULT_PARAMS, "view": "summary"}
    stats = {
        "min_ms": DEFAULT_PARAMS["min_ms"],
        "music_only": DEFAULT_PARAMS["music_only"],
        "merge_enabled": DEFAULT_PARAMS["merge_enabled"],
        "dynamic_threshold": DEFAULT_PARAMS["dynamic_threshold"],
        "max_merge_gap_minutes": DEFAULT_PARAMS["max_merge_gap_minutes"],
        "period": "lifetime",
        "include_rank_context": "false",
    }
    album_path = f"/api/billboard/album/{quote(args.album_name, safe='')}"
    artist_path = f"/api/billboard/artist/{quote(args.artist_name, safe='')}"
    with httpx.Client(base_url=args.base_url, timeout=120, trust_env=False) as client:
        results = {
            "home": _samples(client, "/api/home/overview", DEFAULT_PARAMS, args.runs),
            "track_summary": _samples(
                client,
                f"/api/billboard/track/{args.track_id}",
                detail,
                args.runs,
            ),
            "album_summary": _samples(
                client,
                album_path,
                {**detail, "artist_name": args.album_artist},
                args.runs,
            ),
            "artist_summary": _samples(client, artist_path, detail, args.runs),
            "track_stats": _samples(
                client, f"/api/music/tracks/{args.track_id}/stats", stats, args.runs
            ),
            "album_stats": _samples(
                client,
                f"/api/music/albums/{quote(args.album_name, safe='')}/stats",
                {**stats, "artist": args.album_artist, "merge_level": 2},
                args.runs,
            ),
            "artist_stats": _samples(
                client,
                f"/api/music/artists/{quote(args.artist_name, safe='')}/stats",
                stats,
                args.runs,
            ),
        }

    gates: dict[str, dict[str, Any]] = {}
    for name in ("track_summary", "album_summary", "artist_summary"):
        actual = results[name]["first"]["elapsed_ms"]
        gates[f"{name}_first"] = {
            "actual_ms": actual,
            "limit_ms": args.summary_first_ms,
            "pass": actual <= args.summary_first_ms,
        }
    home_warm = results["home"]["warm_p50_ms"]
    gates["home_warm"] = {
        "actual_ms": home_warm,
        "limit_ms": args.home_warm_ms,
        "pass": home_warm is not None and home_warm <= args.home_warm_ms,
    }
    for name in ("track_stats", "album_stats", "artist_stats"):
        first = results[name]["first"]["elapsed_ms"]
        gates[f"{name}_first"] = {
            "actual_ms": first,
            "limit_ms": args.stats_first_ms,
            "pass": first <= args.stats_first_ms,
        }
        actual = results[name]["warm_p50_ms"]
        gates[f"{name}_warm"] = {
            "actual_ms": actual,
            "limit_ms": args.stats_warm_ms,
            "pass": actual is not None and actual <= args.stats_warm_ms,
        }

    report = {
        "status": "pass" if all(gate["pass"] for gate in gates.values()) else "fail",
        "base_url": args.base_url,
        "results": results,
        "concurrency": _concurrency_probe(args.base_url, args.track_id, args.other_track_id),
        "gates": gates,
        "notes": [
            "first samples are true cold only when the backend was restarted immediately before the probe",
            "CPU-heavy background jobs are serialized by the JobQueue unit gate",
        ],
    }
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--track-id", type=int, required=True)
    parser.add_argument("--other-track-id", type=int, required=True)
    parser.add_argument("--album-name", required=True)
    parser.add_argument("--album-artist", required=True)
    parser.add_argument("--artist-name", required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--summary-first-ms", type=float, default=500.0)
    parser.add_argument("--home-warm-ms", type=float, default=80.0)
    parser.add_argument("--stats-warm-ms", type=float, default=150.0)
    parser.add_argument("--stats-first-ms", type=float, default=1500.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on-slow", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run(args)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 1 if args.fail_on_slow and report["status"] != "pass" else 0


if __name__ == "__main__":
    raise SystemExit(main())
