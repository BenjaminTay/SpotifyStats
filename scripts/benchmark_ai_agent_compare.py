#!/usr/bin/env python3
"""Repeatable cold/hot benchmark for the read-only compare_entities tool."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

from backend.core import db as db_module
from backend.domains.ai_agent.tool_cache import (
    agent_tool_cache_stats,
    clear_agent_tool_cache,
)
from backend.domains.ai_agent.tool_registry import dispatch_tool


def _run(params: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    started = time.perf_counter()
    result = dispatch_tool("compare_entities", params)
    return time.perf_counter() - started, result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entity-type", choices=("track", "album", "artist"), required=True)
    parser.add_argument("--name", action="append", required=True, dest="names")
    parser.add_argument(
        "--database",
        type=Path,
        help="Optional SQLite database path; it is opened through the normal read-only tool path.",
    )
    parser.add_argument("--period", default="lifetime")
    parser.add_argument("--include-billboard", action="store_true")
    parser.add_argument("--hot-runs", type=int, default=5)
    args = parser.parse_args()
    if not 2 <= len(args.names) <= 4:
        parser.error("--name must be supplied two to four times")
    if args.database is not None:
        database = args.database.expanduser().resolve()
        if not database.is_file():
            parser.error(f"database does not exist: {database}")
        db_module.DB_PATH = str(database)

    params = {
        "entity_type": args.entity_type,
        "names": args.names,
        "period": args.period,
        "include_billboard": args.include_billboard,
    }
    clear_agent_tool_cache()
    cold_seconds, cold_result = _run(params)
    hot_seconds = [_run(params)[0] for _ in range(max(1, args.hot_runs))]
    median_hot = statistics.median(hot_seconds)
    print(
        json.dumps(
            {
                "params": params,
                "cold_seconds": round(cold_seconds, 6),
                "hot_seconds": [round(value, 6) for value in hot_seconds],
                "hot_median_seconds": round(median_hot, 6),
                "cold_to_hot_speedup": (
                    round(cold_seconds / median_hot, 2) if median_hot > 0 else None
                ),
                "cache": agent_tool_cache_stats(),
                "result_summary": cold_result.get("result_summary"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
