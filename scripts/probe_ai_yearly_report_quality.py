#!/usr/bin/env python3
"""Probe yearly AI report data contract against the local production DB."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.db import get_db  # noqa: E402
from backend.services.ai_insights_service import _gather_yearly_data  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    conn = get_db(readonly=True)
    try:
        data = _gather_yearly_data(
            conn,
            min_ms=30000,
            music_only=True,
            merge_enabled=True,
            year=args.year,
            dynamic_threshold=True,
            max_merge_gap_minutes=None,
        )
    finally:
        conn.close()

    summary = {
        "year": args.year,
        "reporting_period": data.get("reporting_period"),
        "top_artists": data.get("top_artists", [])[:5],
        "top_tracks": data.get("top_tracks", [])[:5],
        "top_albums": data.get("top_albums", [])[:5],
        "new_artists": data.get("new_artists", [])[:3],
        "billboard_year_end": data.get("billboard_year_end"),
        "editorial_brief": data.get("editorial_brief"),
        "personality_summary": data.get("personality_summary"),
        "genre_summary": data.get("genre_summary"),
        "year_over_year": data.get("year_over_year"),
    }

    failures = _quality_failures(summary, args.year)
    if args.json_output:
        args.json_output.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    return 0


def _quality_failures(summary: dict, year: int) -> list[str]:
    failures: list[str] = []
    period = summary.get("reporting_period") or {}
    top_artists = summary.get("top_artists") or []
    top_tracks = summary.get("top_tracks") or []
    top_albums = summary.get("top_albums") or []
    billboard_year_end = summary.get("billboard_year_end") or {}
    editorial_brief = summary.get("editorial_brief") or {}
    year_over_year = summary.get("year_over_year") or {}

    if not period.get("start_date") or not period.get("end_date"):
        failures.append("reporting period must include start_date and end_date")
    if period.get("latest_data_date") != period.get("end_date"):
        failures.append("latest_data_date must match reporting period end_date")
    if year == 2026 and period.get("is_partial_year") is not True:
        failures.append("expected 2026 to be marked partial-year")
    if not top_artists or not all(item.get("name") for item in top_artists):
        failures.append("top artist names must be populated")
    if not top_tracks or not all(item.get("name") for item in top_tracks):
        failures.append("top track names must be populated")
    if not top_albums or not all(item.get("name") for item in top_albums):
        failures.append("top album names must be populated")
    if billboard_year_end.get("available"):
        for chart_key in ("tracks", "albums", "artists"):
            rows = billboard_year_end.get(chart_key) or []
            if not rows or not all(item.get("name") for item in rows[:1]):
                failures.append(f"billboard_year_end.{chart_key} must include named rows")
    if not editorial_brief.get("thesis"):
        failures.append("editorial_brief.thesis must be populated")
    required_angles = set(editorial_brief.get("required_angles") or [])
    if top_albums and "album" not in required_angles:
        failures.append("editorial_brief.required_angles must include album")
    if billboard_year_end.get("available") and "personal_billboard" not in required_angles:
        failures.append("editorial_brief.required_angles must include personal_billboard")
    if (
        period.get("is_partial_year")
        and year_over_year.get("comparison_basis") != "same_period_ytd"
    ):
        failures.append("partial-year comparison must use same_period_ytd")
    if (
        period.get("is_partial_year")
        and year_over_year.get("full_previous_year_change") is not None
    ):
        failures.append("partial-year report must not expose full_previous_year_change")
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
