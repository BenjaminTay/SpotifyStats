#!/usr/bin/env python3
"""Validate Billboard Year-End rows against the canonical weekly charts.

This probe is read-only. It checks every available year and requested merge
level with the persisted Billboard settings, then verifies that the annual
metrics are exact aggregations of the same weekly chart rows.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.db import get_db  # noqa: E402
from backend.domains.billboard.chart_power_score import (  # noqa: E402
    _aggregate_scored_rows,
    _score_ranked_rows,
)
from backend.domains.settings.repository import SettingsRepository  # noqa: E402
from backend.services.billboard_service import (  # noqa: E402
    compute_weekly_data,
    compute_year_end_staged,
)


def _parse_merge_levels(value: str) -> list[int]:
    levels = sorted({int(item.strip()) for item in value.split(",") if item.strip()})
    if not levels or any(level not in {1, 2, 3} for level in levels):
        raise argparse.ArgumentTypeError("merge levels must be a comma-separated subset of 1,2,3")
    return levels


def _settings() -> dict[str, Any]:
    conn = get_db(readonly=True)
    try:
        return SettingsRepository(conn).load_all()
    finally:
        conn.close()


def _base_params(settings: dict[str, Any], merge_level: int) -> dict[str, Any]:
    return {
        "min_ms": int(settings["min_ms"]),
        "music_only": bool(settings["music_only"]),
        "bb_top_n": int(settings["bb_top_n"]),
        "bb_album_top_n": int(settings["bb_album_top_n"]),
        "bb_artist_top_n": int(settings["bb_artist_top_n"]),
        "bb_week_start_dow": int(settings["bb_week_start_dow"]),
        "bb_week_start_hour": int(settings["bb_week_start_hour"]),
        "merge_level": merge_level,
        "dynamic_threshold": True,
        "max_merge_gap_minutes": 5,
        "include_compilations": bool(settings["include_compilations"]),
    }


def _track_key(row: dict[str, Any]) -> int:
    return int(row["track_id"])


def _album_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row["album_name"]), str(row["artist_name"])


def _artist_key(row: dict[str, Any]) -> str:
    return str(row["artist_name"])


def _weekly_metrics(
    rows: list[dict[str, Any]],
    *,
    year: int,
    key_fn,
    group_cols: str | list[str],
) -> dict[Any, dict[str, int]]:
    grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if int(str(row["billboard_week"])[:4]) == year:
            grouped[key_fn(row)].append(row)

    metrics: dict[Any, dict[str, int]] = {}
    for key, entity_rows in grouped.items():
        ranks = [int(row["rank"]) for row in entity_rows]
        peak = min(ranks)
        metrics[key] = {
            "weeks_on_chart": len({str(row["billboard_week"]) for row in entity_rows}),
            "peak_position": peak,
            "weeks_at_peak": sum(rank == peak for rank in ranks),
            "weeks_at_no1": sum(rank == 1 for rank in ranks),
            "weeks_top5": sum(rank <= 5 for rank in ranks),
            "weeks_top10": sum(rank <= 10 for rank in ranks),
            "chart_plays": sum(int(row["play_count"]) for row in entity_rows),
        }

    annual_rows = [row for row in rows if int(str(row["billboard_week"])[:4]) == year]
    if annual_rows:
        scored = _score_ranked_rows(pd.DataFrame(annual_rows))
        annual_scores = _aggregate_scored_rows(scored, group_cols)
        for row in annual_scores.to_dict("records"):
            key = key_fn(row)
            metrics[key]["year_end_score"] = round(float(row["raw_score"]))
    return metrics


def _check_family(
    *,
    family: str,
    rows: list[dict[str, Any]],
    weekly_rows: list[dict[str, Any]],
    year: int,
    key_fn,
    group_cols: str | list[str],
) -> list[str]:
    issues: list[str] = []
    expected = _weekly_metrics(
        weekly_rows,
        year=year,
        key_fn=key_fn,
        group_cols=group_cols,
    )
    expected_ranks = list(range(1, len(rows) + 1))
    actual_ranks = [int(row["year_end_rank"]) for row in rows]
    if actual_ranks != expected_ranks:
        issues.append(f"{family}: non-contiguous Year-End ranks {actual_ranks[:10]}")

    metric_names = (
        "weeks_on_chart",
        "peak_position",
        "weeks_at_peak",
        "weeks_at_no1",
        "weeks_top5",
        "weeks_top10",
        "chart_plays",
        "year_end_score",
    )
    for row in rows:
        key = key_fn(row)
        weekly_metric = expected.get(key)
        if weekly_metric is None:
            issues.append(f"{family}: Year-End row missing from weekly chart: {key!r}")
            continue
        for metric in metric_names:
            if int(row[metric]) != weekly_metric[metric]:
                issues.append(
                    f"{family}: {key!r} {metric}={row[metric]} "
                    f"but weekly aggregation={weekly_metric[metric]}"
                )
        if int(row["annual_plays"]) < int(row["chart_plays"]):
            issues.append(
                f"{family}: {key!r} annual_plays={row['annual_plays']} "
                f"is below chart_plays={row['chart_plays']}"
            )
    return issues


def run_probe(merge_levels: list[int]) -> dict[str, Any]:
    settings = _settings()
    checks: list[dict[str, Any]] = []
    all_issues: list[str] = []

    for merge_level in merge_levels:
        params = _base_params(settings, merge_level)
        weekly = compute_weekly_data(**params)
        latest = compute_year_end_staged(**params)
        years = [int(year) for year in latest["meta"]["available_years"]]

        for year in years:
            payload = compute_year_end_staged(**params, year=year)
            issues: list[str] = []
            issues.extend(
                _check_family(
                    family="tracks",
                    rows=payload["tracks"],
                    weekly_rows=weekly["weekly"],
                    year=year,
                    key_fn=_track_key,
                    group_cols="track_id",
                )
            )
            issues.extend(
                _check_family(
                    family="albums",
                    rows=payload["albums"],
                    weekly_rows=weekly["weekly_album"],
                    year=year,
                    key_fn=_album_key,
                    group_cols=["album_name", "artist_name"],
                )
            )
            issues.extend(
                _check_family(
                    family="artists",
                    rows=payload["artists"],
                    weekly_rows=weekly["weekly_artist"],
                    year=year,
                    key_fn=_artist_key,
                    group_cols="artist_name",
                )
            )

            meta = payload["meta"]
            if meta["semantics_version"] != "year_end_v4":
                issues.append(f"meta: unexpected semantics_version={meta['semantics_version']!r}")
            if int(meta["weekly_top_n"]) != int(settings["bb_top_n"]):
                issues.append("meta: track weekly cutoff differs from persisted settings")
            if int(meta["weekly_album_top_n"]) != int(settings["bb_album_top_n"]):
                issues.append("meta: album weekly cutoff differs from persisted settings")
            if int(meta["weekly_artist_top_n"]) != int(settings["bb_artist_top_n"]):
                issues.append("meta: artist weekly cutoff differs from persisted settings")

            compact = compute_year_end_staged(
                **params,
                year=year,
                year_end_top_n=1,
                year_end_album_top_n=1,
                year_end_artist_top_n=1,
            )
            for family in ("tracks", "albums", "artists"):
                if payload[family] and compact[family]:
                    full_top = payload[family][0]
                    compact_top = compact[family][0]
                    if (
                        full_top["year_end_score"] != compact_top["year_end_score"]
                        or full_top["year_end_rank"] != compact_top["year_end_rank"]
                    ):
                        issues.append(f"{family}: output limit changed the top row score or rank")

            check = {
                "merge_level": merge_level,
                "year": year,
                "coverage_status": meta["coverage_status"],
                "observed_weeks": meta["observed_weeks"],
                "expected_weeks": meta["expected_weeks"],
                "row_counts": {
                    "tracks": len(payload["tracks"]),
                    "albums": len(payload["albums"]),
                    "artists": len(payload["artists"]),
                },
                "issues": issues,
            }
            checks.append(check)
            all_issues.extend(f"L{merge_level} {year}: {issue}" for issue in issues)

    return {
        "ok": not all_issues,
        "settings": {
            key: settings[key]
            for key in (
                "min_ms",
                "music_only",
                "bb_top_n",
                "bb_album_top_n",
                "bb_artist_top_n",
                "bb_week_start_dow",
                "bb_week_start_hour",
                "include_compilations",
            )
        },
        "merge_levels": merge_levels,
        "checks": checks,
        "issue_count": len(all_issues),
        "issues": all_issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--merge-levels",
        type=_parse_merge_levels,
        default=[1, 2, 3],
        help="Comma-separated merge levels (default: 1,2,3)",
    )
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    result = run_probe(args.merge_levels)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_output:
        args.json_output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
