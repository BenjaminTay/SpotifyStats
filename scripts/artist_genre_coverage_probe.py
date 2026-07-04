#!/usr/bin/env python3
"""Report resolved artist genre coverage weighted by main-artist play hours."""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.db import get_db
from backend.domains.metadata.artist_genres import compute_genre_coverage


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="artist_genre_coverage_probe.py",
        description="Measure artist genre coverage by main-artist play hours.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Write a machine-readable coverage report to this JSON file.",
    )
    parser.add_argument(
        "--max-unknown-pct",
        type=float,
        help="Exit non-zero when unknown play-hour percentage exceeds this value.",
    )
    return parser.parse_args(argv)


def write_json_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_artist_play_hours(conn) -> dict[str, float]:
    rows = conn.execute(
        """SELECT a.artist_name AS artist_name,
                  SUM(p.ms_played) / 3600000.0 AS hours
           FROM plays p
           JOIN tracks t ON p.track_id = t.track_id
           JOIN artists a ON t.artist_id = a.artist_id
           WHERE p.track_id IS NOT NULL
             AND COALESCE(p.content_type, 'audio') = 'audio'
           GROUP BY a.artist_name
           HAVING hours > 0
           ORDER BY hours DESC"""
    ).fetchall()
    return {
        row["artist_name"]: float(row["hours"] or 0)
        for row in rows
        if row["artist_name"] and float(row["hours"] or 0) > 0
    }


def build_report(max_unknown_pct: float | None = None, conn=None) -> dict[str, Any]:
    close_conn = conn is None
    if conn is None:
        conn = get_db(readonly=True)
    try:
        artist_hours = load_artist_play_hours(conn)
        report = compute_genre_coverage(conn, artist_hours)
        report["artist_count"] = len(artist_hours)
        report["total_hours"] = round(sum(artist_hours.values()), 1)
        if max_unknown_pct is not None:
            report["max_unknown_pct"] = max_unknown_pct
            report["threshold_exceeded"] = report["unknown_pct"] > max_unknown_pct
        return report
    finally:
        if close_conn:
            conn.close()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = build_report(args.max_unknown_pct)
    except Exception as exc:
        print(f"artist_genre_coverage_probe.py failed: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        write_json_report(report, args.json_output)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if report.get("threshold_exceeded") else 0


if __name__ == "__main__":
    raise SystemExit(main())
