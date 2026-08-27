#!/usr/bin/env python3
"""Audit the evidence pool for the Yearly Review V2 rebuild.

This command is intentionally read-only. It reuses the canonical playback,
album-project, artist-credit, Billboard Year-End, playback-record, taste, and
Wrapped computations, then writes a compact JSON dossier for policy review.
It does not create report caches or mutate application tables.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.db import get_db, load_plays  # noqa: E402
from backend.domains.metadata.genre_display_taxonomy import (  # noqa: E402
    build_consumer_taste_profile,
)
from backend.domains.settings.repository import SettingsRepository  # noqa: E402
from backend.services.analysis_records_service import (  # noqa: E402
    _build_entity_frames,
    _get_analysis_records_uncached,
)
from backend.services.analysis_stats_service import chart_rows  # noqa: E402
from backend.services.billboard_service import compute_year_end_staged  # noqa: E402
from backend.services.wrapped_service import (  # noqa: E402
    _build_wrapped_full,
    _fetch_track_release_years,
)

AUDIT_VERSION = "yearly_review_v2_audit_v1"
RELATIONSHIP_POLICY_VERSION = "relationship_policy_v2"
HIGHLIGHT_POLICY_VERSION = "highlight_policy_v3"
SEASON_STAGE_POLICY_VERSION = "season_stage_v2"
DEFAULT_TOP_SAMPLE = 12
DEFAULT_MIN_SAMPLE_PLAYS = 10


def parse_years(value: str) -> list[int]:
    """Parse and validate a comma-separated year list."""
    try:
        years = sorted({int(item.strip()) for item in value.split(",") if item.strip()})
    except ValueError as exc:
        raise argparse.ArgumentTypeError("years must be comma-separated integers") from exc
    current_year = datetime.now(timezone.utc).year
    if not years or any(year < 2000 or year > current_year for year in years):
        raise argparse.ArgumentTypeError(f"years must be between 2000 and {current_year}")
    return years


def _json_value(value: Any) -> Any:
    """Convert pandas/numpy/datetime values to stable JSON-compatible values."""
    if value is None:
        return None
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return _json_value(value.item())
        except (TypeError, ValueError):
            pass
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    return value


def _round(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


def _quantiles(values: Iterable[float]) -> dict[str, float | None]:
    series = pd.Series(list(values), dtype="float64").dropna()
    if series.empty:
        return {key: None for key in ("min", "p25", "median", "p75", "p90", "max")}
    return {
        "min": _round(series.min(), 3),
        "p25": _round(series.quantile(0.25), 3),
        "median": _round(series.median(), 3),
        "p75": _round(series.quantile(0.75), 3),
        "p90": _round(series.quantile(0.90), 3),
        "max": _round(series.max(), 3),
    }


def _max_consecutive_months(months: Iterable[int]) -> int:
    ordered = sorted({int(month) for month in months})
    best = current = 0
    previous: int | None = None
    for month in ordered:
        current = current + 1 if previous is not None and month == previous + 1 else 1
        best = max(best, current)
        previous = month
    return best


def _profile_entities(
    frame: pd.DataFrame,
    *,
    entity_type: str,
    id_column: str,
    name_column: str,
    artist_column: str | None = None,
    min_sample_plays: int = DEFAULT_MIN_SAMPLE_PLAYS,
    top_sample: int = DEFAULT_TOP_SAMPLE,
) -> dict[str, Any]:
    """Build relationship-strength distributions without assigning labels yet."""
    if frame.empty or id_column not in frame or name_column not in frame:
        return {
            "entity_type": entity_type,
            "entity_count": 0,
            "eligible_count": 0,
            "min_sample_plays": min_sample_plays,
            "quantiles": {},
            "top_by_volume": [],
            "top_by_persistence": [],
            "top_by_burst": [],
        }

    work = frame.copy()
    work["_date"] = pd.to_datetime(work["ts_date"], errors="coerce")
    work = work.dropna(subset=[id_column, name_column, "_date"])
    if work.empty:
        return {
            "entity_type": entity_type,
            "entity_count": 0,
            "eligible_count": 0,
            "min_sample_plays": min_sample_plays,
            "quantiles": {},
            "top_by_volume": [],
            "top_by_persistence": [],
            "top_by_burst": [],
        }

    work["_month"] = work["_date"].dt.month
    grouped_rows: list[dict[str, Any]] = []
    for entity_id, group in work.groupby(id_column, dropna=False, sort=False):
        monthly = group.groupby("_month").size().sort_index()
        plays = int(len(group))
        first_date = group["_date"].min()
        last_date = group["_date"].max()
        active_months = int(monthly.size)
        row: dict[str, Any] = {
            "entity_type": entity_type,
            "entity_id": _json_value(entity_id),
            "name": str(group[name_column].iloc[0]),
            "plays": plays,
            "hours": _round(group["ms_played"].sum() / 3_600_000),
            "active_days": int(group["_date"].dt.date.nunique()),
            "active_months": active_months,
            "consecutive_active_months": _max_consecutive_months(monthly.index),
            "span_days": int((last_date - first_date).days) + 1,
            "peak_month": int(monthly.idxmax()),
            "peak_month_plays": int(monthly.max()),
            "peak_month_share": _round(monthly.max() / max(plays, 1), 4),
            "unique_tracks": int(group["track_id"].nunique()) if "track_id" in group else None,
        }
        if artist_column and artist_column in group:
            artist = group[artist_column].dropna()
            row["artist_name"] = str(artist.iloc[0]) if not artist.empty else None
        grouped_rows.append(row)

    eligible = [row for row in grouped_rows if row["plays"] >= min_sample_plays]
    scenario_counts = {
        "sustained_companion": sum(
            row["active_months"] >= 9
            and row["consecutive_active_months"] >= 6
            and row["span_days"] >= 240
            for row in eligible
        ),
        "yearlong_companion": sum(
            row["active_months"] >= 11
            and row["consecutive_active_months"] >= 9
            and row["span_days"] >= 300
            for row in eligible
        ),
        "concentrated_burst": sum(
            row["peak_month_share"] >= 0.70 and row["active_months"] <= 4 for row in eligible
        ),
        "deep_catalog": sum(
            (row.get("unique_tracks") or 0) >= 8 and row["plays"] >= 20 and row["active_days"] >= 10
            for row in eligible
        ),
        "broad_catalog": sum(
            (row.get("unique_tracks") or 0) >= 15
            and row["plays"] >= 30
            and row["active_months"] >= 4
            for row in eligible
        ),
    }
    quantile_fields = (
        "plays",
        "hours",
        "active_days",
        "active_months",
        "consecutive_active_months",
        "span_days",
        "peak_month_share",
        "unique_tracks",
    )
    quantiles = {
        field: _quantiles(row[field] for row in eligible if row.get(field) is not None)
        for field in quantile_fields
    }
    public_fields = (
        "entity_type",
        "entity_id",
        "name",
        "artist_name",
        "plays",
        "hours",
        "active_days",
        "active_months",
        "consecutive_active_months",
        "span_days",
        "peak_month",
        "peak_month_plays",
        "peak_month_share",
        "unique_tracks",
    )

    def compact(row: dict[str, Any]) -> dict[str, Any]:
        return {field: row[field] for field in public_fields if field in row}

    return {
        "entity_type": entity_type,
        "entity_count": len(grouped_rows),
        "eligible_count": len(eligible),
        "min_sample_plays": min_sample_plays,
        "scenario_counts": scenario_counts,
        "quantiles": quantiles,
        "top_by_volume": [
            compact(row)
            for row in sorted(eligible, key=lambda item: (-item["plays"], -item["hours"]))[
                :top_sample
            ]
        ],
        "top_by_persistence": [
            compact(row)
            for row in sorted(
                eligible,
                key=lambda item: (
                    -item["active_months"],
                    -item["consecutive_active_months"],
                    -item["span_days"],
                    -item["plays"],
                ),
            )[:top_sample]
        ],
        "top_by_burst": [
            compact(row)
            for row in sorted(
                eligible,
                key=lambda item: (-item["peak_month_share"], -item["plays"]),
            )[:top_sample]
        ],
    }


def history_transition_candidates(
    frame: pd.DataFrame,
    *,
    year: int,
    entity_type: str,
    id_column: str,
    name_column: str,
    artist_column: str | None = None,
    min_sample_plays: int = DEFAULT_MIN_SAMPLE_PLAYS,
    top_sample: int = DEFAULT_TOP_SAMPLE,
) -> dict[str, Any]:
    """Audit true first-year relationships and returns after personal inactivity."""
    if frame.empty or id_column not in frame or name_column not in frame:
        return {"entity_type": entity_type, "new_count": 0, "comeback_count": 0}

    work = frame.copy()
    work["_date"] = pd.to_datetime(work["ts_date"], errors="coerce")
    work = work.dropna(subset=[id_column, name_column, "_date"])
    year_start = pd.Timestamp(f"{year}-01-01")
    year_end = pd.Timestamp(f"{year}-12-31 23:59:59")
    current = work[(work["_date"] >= year_start) & (work["_date"] <= year_end)]
    previous = work[work["_date"] < year_start]
    if current.empty:
        return {"entity_type": entity_type, "new_count": 0, "comeback_count": 0}

    previous_last = previous.groupby(id_column)["_date"].max().to_dict()
    new_rows: list[dict[str, Any]] = []
    comeback_rows: list[dict[str, Any]] = []
    for entity_id, group in current.groupby(id_column, dropna=False, sort=False):
        first_date = group["_date"].min()
        last_date = group["_date"].max()
        plays = int(len(group))
        active_days = int(group["_date"].dt.date.nunique())
        span_days = int((last_date - first_date).days) + 1
        base = {
            "entity_type": entity_type,
            "entity_id": _json_value(entity_id),
            "name": str(group[name_column].iloc[0]),
            "plays": plays,
            "active_days": active_days,
            "first_date": first_date.date().isoformat(),
            "last_date": last_date.date().isoformat(),
            "span_days": span_days,
        }
        if artist_column and artist_column in group:
            artist = group[artist_column].dropna()
            base["artist_name"] = str(artist.iloc[0]) if not artist.empty else None

        prior_date = previous_last.get(entity_id)
        if prior_date is None:
            if plays >= min_sample_plays and active_days >= 3 and span_days >= 30:
                new_rows.append(base)
            continue

        gap_days = int((first_date - prior_date).days)
        if gap_days >= 180 and plays >= min_sample_plays and active_days >= 3:
            comeback_rows.append(
                {
                    **base,
                    "previous_last_date": prior_date.date().isoformat(),
                    "inactivity_gap_days": gap_days,
                }
            )

    new_rows.sort(key=lambda row: (-row["plays"], -row["span_days"], str(row["name"])))
    comeback_rows.sort(
        key=lambda row: (-row["inactivity_gap_days"], -row["plays"], str(row["name"]))
    )
    return {
        "entity_type": entity_type,
        "new_count": len(new_rows),
        "comeback_count": len(comeback_rows),
        "new_relationships": new_rows[:top_sample],
        "true_comebacks": comeback_rows[:top_sample],
    }


def _record_signature(row: dict[str, Any]) -> str:
    ignored = {"cover_url", "image_url", "rank", "record_type", "label", "description"}
    stable = {key: value for key, value in row.items() if key not in ignored}
    return json.dumps(_json_value(stable), ensure_ascii=False, sort_keys=True, default=str)


def inventory_records(records: dict[str, Any], top_sample: int = DEFAULT_TOP_SAMPLE) -> dict:
    """Inventory non-empty record leaves and detect exact cross-leaf duplicates."""
    leaves: list[dict[str, Any]] = []
    appearances: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def walk(value: Any, path: list[str]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, [*path, str(key)])
            return
        if not isinstance(value, list) or not value:
            return
        rows = [item for item in value if isinstance(item, dict)]
        leaf_path = ".".join(path)
        leaves.append(
            {
                "path": leaf_path,
                "family": path[0] if path else "unknown",
                "row_count": len(value),
                "sample": _json_value(rows[: min(3, top_sample)]),
            }
        )
        for row in rows:
            appearances[_record_signature(row)].append({"path": leaf_path, "row": _json_value(row)})

    walk(records, [])
    family_rows: Counter[str] = Counter()
    family_leaves: Counter[str] = Counter()
    for leaf in leaves:
        family_rows[leaf["family"]] += leaf["row_count"]
        family_leaves[leaf["family"]] += 1
    duplicate_groups = [items for items in appearances.values() if len(items) > 1]
    duplicate_groups.sort(key=lambda items: (-len(items), items[0]["path"]))
    return {
        "nonempty_leaf_count": len(leaves),
        "total_candidate_rows": sum(leaf["row_count"] for leaf in leaves),
        "families": {
            family: {
                "nonempty_leaf_count": int(family_leaves[family]),
                "candidate_rows": int(row_count),
            }
            for family, row_count in sorted(family_rows.items())
        },
        "leaves": leaves,
        "exact_duplicate_group_count": len(duplicate_groups),
        "exact_duplicate_appearance_count": sum(len(items) for items in duplicate_groups),
        "duplicate_samples": duplicate_groups[:top_sample],
    }


def _bucket_map(axis: dict[str, Any] | None) -> dict[str, float]:
    if not axis:
        return {}
    return {
        str(row.get("key")): float(row.get("share_pct", 0.0))
        for row in axis.get("buckets", [])
        if row.get("key") is not None
    }


def taste_delta(
    earlier: dict[str, Any], later: dict[str, Any], *, top_sample: int = DEFAULT_TOP_SAMPLE
) -> dict[str, Any]:
    """Compare Q1 and Q4 consumer distributions by percentage-point change."""
    axes = {
        "primary_styles": "primary_styles",
        "regional_pop": "regional_pop",
        "language_dist": "language_dist",
    }
    result: dict[str, Any] = {}
    for output_key, source_key in axes.items():
        before = _bucket_map(earlier.get(source_key))
        after = _bucket_map(later.get(source_key))
        changes = [
            {
                "key": key,
                "q1_share_pct": _round(before.get(key, 0.0), 2),
                "q4_share_pct": _round(after.get(key, 0.0), 2),
                "delta_pp": _round(after.get(key, 0.0) - before.get(key, 0.0), 2),
            }
            for key in sorted(set(before) | set(after))
        ]
        changes.sort(key=lambda row: (-abs(cast(float, row["delta_pp"])), str(row["key"])))
        result[output_key] = changes[:top_sample]
    return result


def _taste_coverage(profile: dict[str, Any]) -> dict[str, Any]:
    style = profile.get("primary_styles") or {}
    scene = profile.get("regional_pop") or {}
    language = profile.get("language_dist") or {}
    return {
        "display_taxonomy_version": profile.get("display_taxonomy_version"),
        "style_known_pct": _round(
            100
            * float(style.get("known_hours", 0))
            / max(float(style.get("total_hours", 0)), 1e-9),
            2,
        ),
        "scene_known_pct": _round(
            100
            * float(scene.get("known_hours", 0))
            / max(float(scene.get("total_hours", 0)), 1e-9),
            2,
        ),
        "language_classified_pct": _round(language.get("classified_pct", 0), 2),
        "style_buckets": _json_value(style.get("buckets", [])),
        "scene_buckets": _json_value(scene.get("buckets", [])),
        "language_buckets": _json_value(language.get("buckets", [])),
    }


def _release_era_distribution(conn, frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"known_pct": 0.0, "unknown_hours": 0.0, "buckets": []}
    pairs = [
        (str(track), str(artist))
        for track, artist in frame[["track_name", "artist_name"]]
        .dropna()
        .drop_duplicates()
        .itertuples(index=False, name=None)
    ]
    release_years = _fetch_track_release_years(conn, pairs)
    bucket_ms: Counter[str] = Counter()
    unknown_ms = 0
    for row in frame[["track_name", "artist_name", "ms_played"]].itertuples(index=False):
        release_year = release_years.get((str(row.track_name), str(row.artist_name)))
        if release_year is None or release_year < 1900:
            unknown_ms += int(row.ms_played)
            continue
        decade = release_year // 10 * 10
        bucket_ms[f"{decade}s"] += int(row.ms_played)
    total_ms = int(frame["ms_played"].sum())
    buckets = [
        {
            "key": key,
            "hours": _round(ms / 3_600_000),
            "share_pct": _round(ms / max(total_ms, 1) * 100),
        }
        for key, ms in sorted(bucket_ms.items(), key=lambda item: (-item[1], item[0]))
    ]
    return {
        "known_pct": _round((total_ms - unknown_ms) / max(total_ms, 1) * 100),
        "unknown_hours": _round(unknown_ms / 3_600_000),
        "buckets": buckets,
    }


def _monthly_summary(
    track_frame: pd.DataFrame,
    album_frame: pd.DataFrame,
    artist_frame: pd.DataFrame,
) -> list[dict[str, Any]]:
    if track_frame.empty:
        return []

    def top_name(frame: pd.DataFrame, name_column: str, month: int) -> str | None:
        if frame.empty or name_column not in frame:
            return None
        dates = pd.to_datetime(frame["ts_date"], errors="coerce")
        subset = frame[dates.dt.month == month]
        if subset.empty:
            return None
        grouped = (
            subset.groupby(name_column, dropna=True)
            .agg(plays=("play_id", "count"), ms=("ms_played", "sum"))
            .sort_values(["plays", "ms"], ascending=False)
        )
        return str(grouped.index[0]) if not grouped.empty else None

    dates = pd.to_datetime(track_frame["ts_date"], errors="coerce")
    result = []
    previous_artist: str | None = None
    for month in range(1, 13):
        subset = track_frame[dates.dt.month == month]
        if subset.empty:
            continue
        top_artist = top_name(artist_frame, "artist_name", month)
        result.append(
            {
                "month": month,
                "plays": int(len(subset)),
                "hours": _round(subset["ms_played"].sum() / 3_600_000),
                "active_days": int(pd.to_datetime(subset["ts_date"]).dt.date.nunique()),
                "unique_tracks": int(subset["canonical_track_id"].nunique()),
                "top_track": top_name(track_frame, "canonical_track_name", month),
                "top_album": top_name(album_frame, "album_project_name", month),
                "top_artist": top_artist,
                "artist_leader_changed": previous_artist is not None
                and top_artist is not None
                and top_artist != previous_artist,
            }
        )
        if top_artist is not None:
            previous_artist = top_artist
    return result


def _coverage(year: int, frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "year": year,
            "status": "empty",
            "observed_start": None,
            "observed_end": None,
            "active_days": 0,
            "calendar_days_observed": 0,
            "total_plays": 0,
            "total_hours": 0.0,
        }
    dates = pd.to_datetime(frame["ts_date"], errors="coerce").dropna()
    start = dates.min()
    end = dates.max()
    calendar_end = pd.Timestamp(f"{year}-12-31")
    status = "complete_calendar_span" if start.month == 1 and end >= calendar_end else "partial"
    return {
        "year": year,
        "status": status,
        "observed_start": start.date().isoformat(),
        "observed_end": end.date().isoformat(),
        "active_days": int(dates.dt.date.nunique()),
        "calendar_days_observed": int((end - start).days) + 1,
        "total_plays": int(len(frame)),
        "total_hours": _round(frame["ms_played"].sum() / 3_600_000),
    }


def _previous_year_comparison(year: int, frame: pd.DataFrame, all_plays: pd.DataFrame) -> dict:
    previous = all_plays[all_plays["ts_year"] == year - 1]
    if previous.empty:
        return {"available": False, "previous_year": year - 1}
    current_plays = int(len(frame))
    previous_plays = int(len(previous))
    current_hours = float(frame["ms_played"].sum() / 3_600_000)
    previous_hours = float(previous["ms_played"].sum() / 3_600_000)
    return {
        "available": True,
        "previous_year": year - 1,
        "previous_total_plays": previous_plays,
        "previous_total_hours": _round(previous_hours),
        "plays_delta_pct": _round((current_plays - previous_plays) / max(previous_plays, 1) * 100),
        "hours_delta_pct": _round(
            (current_hours - previous_hours) / max(previous_hours, 1e-9) * 100
        ),
    }


def _compact_wrapped(wrapped: dict[str, Any]) -> dict[str, Any]:
    return {
        "reporting_period": _json_value(wrapped.get("reporting_period")),
        "discovery_returns": _json_value(wrapped.get("discovery_returns")),
        "listening_depth": _json_value(wrapped.get("listening_depth")),
        "special_moments": _json_value(wrapped.get("special_moments")),
    }


def _billboard_summary(payload: dict[str, Any], top_sample: int) -> dict[str, Any]:
    return {
        "meta": _json_value(payload.get("meta", {})),
        "row_counts": {
            family: len(payload.get(family, [])) for family in ("tracks", "albums", "artists")
        },
        "tracks": _json_value(payload.get("tracks", [])[:top_sample]),
        "albums": _json_value(payload.get("albums", [])[:top_sample]),
        "artists": _json_value(payload.get("artists", [])[:top_sample]),
        "honors": _json_value(payload.get("honors", {})),
    }


def ranking_billboard_gap(
    play_rows: list[dict[str, Any]],
    billboard_rows: list[dict[str, Any]],
    *,
    entity_type: str,
    top_sample: int = DEFAULT_TOP_SAMPLE,
) -> dict[str, Any]:
    """Compare annual consumption rank with the personal Billboard season rank."""

    def key(row: dict[str, Any]) -> Any:
        if entity_type == "track":
            return row.get("track_id")
        if entity_type == "album":
            return (row.get("album_name"), row.get("artist_name"))
        return row.get("artist_name")

    billboard_by_key = {key(row): row for row in billboard_rows if key(row) is not None}
    comparisons = []
    for play_row in play_rows:
        billboard_row = billboard_by_key.get(key(play_row))
        if billboard_row is None:
            continue
        play_rank = int(play_row["rank"])
        season_rank = int(billboard_row["year_end_rank"])
        comparisons.append(
            {
                "entity_type": entity_type,
                "entity_id": _json_value(key(play_row)),
                "name": play_row.get(
                    "track_name", play_row.get("album_name", play_row.get("artist_name"))
                ),
                "artist_name": play_row.get("artist_name"),
                "play_rank": play_rank,
                "billboard_year_end_rank": season_rank,
                "rank_gap": play_rank - season_rank,
                "absolute_rank_gap": abs(play_rank - season_rank),
            }
        )
    comparisons.sort(
        key=lambda row: (-row["absolute_rank_gap"], row["play_rank"], str(row["name"]))
    )
    return {
        "matched_count": len(comparisons),
        "absolute_gap_quantiles": _quantiles(row["absolute_rank_gap"] for row in comparisons),
        "gap_at_least_5_count": sum(row["absolute_rank_gap"] >= 5 for row in comparisons),
        "gap_at_least_10_count": sum(row["absolute_rank_gap"] >= 10 for row in comparisons),
        "largest_gaps": comparisons[:top_sample],
    }


def _chart_pack(
    conn,
    frame: pd.DataFrame,
    entity: str,
    metric: str,
    merge_level: int,
    include: bool,
) -> dict:
    limit = 50 if entity == "track" else 30
    total, rows = chart_rows(
        conn,
        frame,
        entity,
        metric,
        limit=limit,
        merge_level=merge_level,
        include_compilations=include,
    )
    return {
        "metric": metric,
        "available_count": total,
        "returned_count": len(rows),
        "rows": _json_value(rows),
    }


def audit_year(
    conn,
    *,
    all_plays: pd.DataFrame,
    year: int,
    settings: dict[str, Any],
    all_entity_frames: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
    merge_level: int,
    dynamic_threshold: bool,
    max_merge_gap_minutes: int | None,
    min_sample_plays: int,
    top_sample: int,
) -> dict[str, Any]:
    year_frame = all_plays[all_plays["ts_year"] == year].copy()
    coverage = _coverage(year, year_frame)
    if year_frame.empty:
        return {"year": year, "coverage": coverage, "empty": True}

    include_compilations = bool(settings["include_compilations"])
    all_track_frame, all_album_frame, all_artist_frame = all_entity_frames
    track_frame = all_track_frame[all_track_frame["ts_year"] == year].copy()
    album_frame = all_album_frame[all_album_frame["ts_year"] == year].copy()
    artist_frame = all_artist_frame[all_artist_frame["ts_year"] == year].copy()

    rankings = {
        "tracks": {
            metric: _chart_pack(
                conn,
                track_frame,
                "track",
                metric.removeprefix("by_"),
                merge_level,
                include_compilations,
            )
            for metric in ("by_plays", "by_hours")
        },
        "albums": {
            metric: _chart_pack(
                conn,
                album_frame,
                "album",
                metric.removeprefix("by_"),
                merge_level,
                include_compilations,
            )
            for metric in ("by_plays", "by_hours")
        },
        "artists": {
            metric: _chart_pack(
                conn,
                artist_frame,
                "artist",
                metric.removeprefix("by_"),
                merge_level,
                include_compilations,
            )
            for metric in ("by_plays", "by_hours")
        },
    }

    billboard = compute_year_end_staged(
        min_ms=int(settings["min_ms"]),
        music_only=bool(settings["music_only"]),
        bb_top_n=int(settings["bb_top_n"]),
        bb_album_top_n=int(settings["bb_album_top_n"]),
        bb_artist_top_n=int(settings["bb_artist_top_n"]),
        bb_week_start_dow=int(settings["bb_week_start_dow"]),
        bb_week_start_hour=int(settings["bb_week_start_hour"]),
        year=year,
        merge_level=merge_level,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        include_compilations=include_compilations,
        year_end_top_n=50,
        year_end_album_top_n=30,
        year_end_artist_top_n=30,
    )

    records = _get_analysis_records_uncached(
        conn=conn,
        min_ms=int(settings["min_ms"]),
        music_only=bool(settings["music_only"]),
        merge_enabled=bool(settings["merge_enabled"]),
        period="custom",
        start_date=f"{year}-01-01",
        end_date=f"{year}-12-31",
        merge_level=merge_level,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        include_compilations=include_compilations,
    )
    wrapped = _build_wrapped_full(
        conn=conn,
        min_ms=int(settings["min_ms"]),
        music_only=bool(settings["music_only"]),
        merge_enabled=bool(settings["merge_enabled"]),
        year=year,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        merge_level=merge_level,
    )

    full_taste = build_consumer_taste_profile(conn, year_frame)
    dates = pd.to_datetime(year_frame["ts_date"], errors="coerce")
    q1_taste = build_consumer_taste_profile(conn, year_frame[dates.dt.month <= 3])
    q4_taste = build_consumer_taste_profile(conn, year_frame[dates.dt.month >= 10])

    relationships = {
        "tracks": _profile_entities(
            track_frame,
            entity_type="track",
            id_column="canonical_track_id",
            name_column="canonical_track_name",
            artist_column="artist_name",
            min_sample_plays=min_sample_plays,
            top_sample=top_sample,
        ),
        "albums": _profile_entities(
            album_frame,
            entity_type="album",
            id_column="album_project_id",
            name_column="album_project_name",
            artist_column="artist_name",
            min_sample_plays=min_sample_plays,
            top_sample=top_sample,
        ),
        "artists": _profile_entities(
            artist_frame,
            entity_type="artist",
            id_column="artist_name",
            name_column="artist_name",
            min_sample_plays=min_sample_plays,
            top_sample=top_sample,
        ),
        "ranking_billboard_gap": {
            "tracks": ranking_billboard_gap(
                rankings["tracks"]["by_plays"]["rows"],
                billboard.get("tracks", []),
                entity_type="track",
                top_sample=top_sample,
            ),
            "albums": ranking_billboard_gap(
                rankings["albums"]["by_plays"]["rows"],
                billboard.get("albums", []),
                entity_type="album",
                top_sample=top_sample,
            ),
            "artists": ranking_billboard_gap(
                rankings["artists"]["by_plays"]["rows"],
                billboard.get("artists", []),
                entity_type="artist",
                top_sample=top_sample,
            ),
        },
        "history_transitions": {
            "tracks": history_transition_candidates(
                all_track_frame,
                year=year,
                entity_type="track",
                id_column="canonical_track_id",
                name_column="canonical_track_name",
                artist_column="artist_name",
                min_sample_plays=min_sample_plays,
                top_sample=top_sample,
            ),
            "albums": history_transition_candidates(
                all_album_frame,
                year=year,
                entity_type="album",
                id_column="album_project_id",
                name_column="album_project_name",
                artist_column="artist_name",
                min_sample_plays=min_sample_plays,
                top_sample=top_sample,
            ),
            "artists": history_transition_candidates(
                all_artist_frame,
                year=year,
                entity_type="artist",
                id_column="artist_name",
                name_column="artist_name",
                min_sample_plays=min_sample_plays,
                top_sample=top_sample,
            ),
        },
    }

    return {
        "year": year,
        "empty": False,
        "coverage": coverage,
        "comparison": _previous_year_comparison(year, year_frame, all_plays),
        "rankings": rankings,
        "billboard": _billboard_summary(billboard, top_sample),
        "records": inventory_records(records.get("records", {}), top_sample),
        "monthly": _monthly_summary(track_frame, album_frame, artist_frame),
        "relationships": relationships,
        "taste": {
            "coverage_and_buckets": _taste_coverage(full_taste),
            "q1_to_q4_delta": taste_delta(q1_taste, q4_taste, top_sample=top_sample),
            "release_eras": _release_era_distribution(conn, year_frame),
        },
        "wrapped_evidence": _compact_wrapped(wrapped),
    }


def _cross_year_summary(years: list[dict[str, Any]]) -> dict[str, Any]:
    nonempty = [item for item in years if not item.get("empty")]
    relationship_eligible: dict[str, list[int]] = defaultdict(list)
    record_rows = []
    record_leaves = []
    monthly_counts = []
    for item in nonempty:
        record_rows.append(int(item["records"]["total_candidate_rows"]))
        record_leaves.append(int(item["records"]["nonempty_leaf_count"]))
        monthly_counts.append(len(item["monthly"]))
        for family, profile in item["relationships"].items():
            if family in {"ranking_billboard_gap", "history_transitions"}:
                continue
            relationship_eligible[family].append(int(profile["eligible_count"]))
    return {
        "audited_year_count": len(years),
        "nonempty_year_count": len(nonempty),
        "coverage_statuses": Counter(item["coverage"]["status"] for item in years),
        "relationship_eligible_count_quantiles": {
            family: _quantiles(counts) for family, counts in relationship_eligible.items()
        },
        "record_candidate_row_quantiles": _quantiles(record_rows),
        "record_nonempty_leaf_quantiles": _quantiles(record_leaves),
        "months_with_data_quantiles": _quantiles(monthly_counts),
        "policy_status": {
            "relationship_policy_version": RELATIONSHIP_POLICY_VERSION,
            "highlight_policy_version": HIGHLIGHT_POLICY_VERSION,
            "season_stage_policy_version": SEASON_STAGE_POLICY_VERSION,
            "status": "frozen_after_2023_2025_distribution_audit",
        },
    }


def run_audit(
    *,
    years: list[int],
    merge_level: int,
    dynamic_threshold: bool = True,
    max_merge_gap_minutes: int | None = None,
    min_sample_plays: int = DEFAULT_MIN_SAMPLE_PLAYS,
    top_sample: int = DEFAULT_TOP_SAMPLE,
) -> dict[str, Any]:
    conn = get_db(readonly=True)
    try:
        settings = SettingsRepository(conn).load_all()
        if max_merge_gap_minutes is None:
            max_merge_gap_minutes = int(settings.get("max_merge_gap_minutes", 5))
        all_plays = load_plays(
            conn,
            min_ms=int(settings["min_ms"]),
            music_only=bool(settings["music_only"]),
            merge_enabled=bool(settings["merge_enabled"]),
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
        )
        all_entity_frames = _build_entity_frames(
            all_plays,
            conn,
            merge_level,
            bool(settings["include_compilations"]),
            min_ms=int(settings["min_ms"]),
            music_only=bool(settings["music_only"]),
            merge_enabled=bool(settings["merge_enabled"]),
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
        )
        audited = [
            audit_year(
                conn,
                all_plays=all_plays,
                year=year,
                settings=settings,
                all_entity_frames=all_entity_frames,
                merge_level=merge_level,
                dynamic_threshold=dynamic_threshold,
                max_merge_gap_minutes=max_merge_gap_minutes,
                min_sample_plays=min_sample_plays,
                top_sample=top_sample,
            )
            for year in years
        ]
    finally:
        conn.close()

    context = {
        key: settings[key]
        for key in (
            "min_ms",
            "music_only",
            "merge_enabled",
            "bb_top_n",
            "bb_album_top_n",
            "bb_artist_top_n",
            "bb_week_start_dow",
            "bb_week_start_hour",
            "include_compilations",
        )
    }
    context.update(
        {
            "merge_level": merge_level,
            "dynamic_threshold": dynamic_threshold,
            "max_merge_gap_minutes": max_merge_gap_minutes,
            "min_sample_plays": min_sample_plays,
        }
    )
    return _json_value(
        {
            "audit_version": AUDIT_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "read_only": True,
            "context": context,
            "requested_years": years,
            "years": audited,
            "cross_year": _cross_year_summary(audited),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=parse_years, required=True)
    parser.add_argument("--merge-level", type=int, choices=(2, 3), default=2)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--top-sample", type=int, default=DEFAULT_TOP_SAMPLE)
    parser.add_argument("--min-sample-plays", type=int, default=DEFAULT_MIN_SAMPLE_PLAYS)
    parser.add_argument(
        "--dynamic-threshold",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--max-merge-gap-minutes", type=int)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.top_sample < 1 or args.min_sample_plays < 1:
        raise SystemExit("--top-sample and --min-sample-plays must be positive")
    report = run_audit(
        years=args.years,
        merge_level=args.merge_level,
        dynamic_threshold=args.dynamic_threshold,
        max_merge_gap_minutes=args.max_merge_gap_minutes,
        min_sample_plays=args.min_sample_plays,
        top_sample=args.top_sample,
    )
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(args.json_output),
                "years": args.years,
                "nonempty_years": report["cross_year"]["nonempty_year_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
