#!/usr/bin/env python3
"""Refresh derived data after importing new Spotify streaming history."""
# ruff: noqa: E402,I001

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.migrations import run_migrations
from backend.services.import_maintenance_service import run_post_streaming_import_maintenance


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="refresh_import_derived_data.py",
        description=(
            "Refresh Spotify metadata, album projects, weekly aggregations, "
            "and cache state for an already-imported streaming database."
        ),
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Write a machine-readable maintenance report to this JSON file.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output except fatal errors.",
    )
    return parser.parse_args(argv)


def write_json_report(report: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    def progress(message: str, pct: float) -> None:
        if args.quiet:
            return
        print(f"[{pct * 100:5.1f}%] {message}", flush=True)

    try:
        run_migrations()
        report = run_post_streaming_import_maintenance(progress_callback=progress)
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        print(f"refresh_import_derived_data.py failed: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        write_json_report(report, args.json_output)

    if not args.quiet:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))

    return 1 if report.get("maintenance_status") == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
