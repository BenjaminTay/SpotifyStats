"""Time and governed taste-profile adapter for Yearly Review V2."""

from __future__ import annotations

import sqlite3
from collections import Counter
from typing import Any

import pandas as pd

from backend.core.db import load_plays
from backend.domains.metadata.genre_display_taxonomy import build_consumer_taste_profile
from backend.models.yearly_review import YearlyReviewFilterContext
from backend.services.analysis_stats_service import (
    _behavior_summary,
    _cumulative_trend,
    _daily_metrics,
    _daily_trend,
    _hourly_distribution,
    _month_distribution,
    _summary,
    _weekday_distribution,
)
from backend.services.wrapped_service import _fetch_track_release_years

TASTE_SLICES: tuple[tuple[str, str, tuple[int, ...]], ...] = (
    ("q1", "第一季度", (1, 2, 3)),
    ("q2", "第二季度", (4, 5, 6)),
    ("q3", "第三季度", (7, 8, 9)),
    ("q4", "第四季度", (10, 11, 12)),
    ("first_half", "上半年", (1, 2, 3, 4, 5, 6)),
    ("second_half", "下半年", (7, 8, 9, 10, 11, 12)),
)


def _annual_frame(frame: pd.DataFrame, year: int) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    if "ts_year" in frame.columns:
        years = pd.to_numeric(frame["ts_year"], errors="coerce")
        return frame[years == year].copy()
    dates = pd.to_datetime(frame["ts_date"], errors="coerce")
    return frame[dates.dt.year == year].copy()


def _ensure_month(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "ts_month" in frame.columns:
        return frame
    result = frame.copy()
    result["ts_month"] = pd.to_datetime(result["ts_date"], errors="coerce").dt.month
    return result


def _monthly_distribution(frame: pd.DataFrame) -> list[dict[str, Any]]:
    base = {int(row["month"]): dict(row) for row in _month_distribution(frame)}
    active_days = (
        frame.groupby("ts_month")["ts_date"].nunique().to_dict() if not frame.empty else {}
    )
    return [
        {
            **base.get(month, {"month": month, "plays": 0, "hours": 0.0}),
            "active_days": int(active_days.get(month, 0)),
        }
        for month in range(1, 13)
    ]


def build_release_era_distribution(
    conn: sqlite3.Connection,
    frame: pd.DataFrame,
) -> dict[str, Any]:
    """Resolve release decades from governed local release metadata."""
    if frame.empty or not {"track_name", "artist_name", "ms_played"}.issubset(frame.columns):
        return {"known_pct": 0.0, "unknown_hours": 0.0, "buckets": []}
    pairs = [
        (str(track), str(artist))
        for track, artist in frame[["track_name", "artist_name"]]
        .dropna()
        .drop_duplicates()
        .itertuples(index=False, name=None)
    ]
    try:
        release_years = _fetch_track_release_years(conn, pairs)
    except Exception:
        release_years = {}
    bucket_ms: Counter[str] = Counter()
    unknown_ms = 0
    for row in frame[["track_name", "artist_name", "ms_played"]].itertuples(index=False):
        release_year = release_years.get((str(row.track_name), str(row.artist_name)))
        played_ms: Any = row.ms_played
        if release_year is None or release_year < 1900:
            unknown_ms += int(played_ms)
            continue
        bucket_ms[f"{release_year // 10 * 10}s"] += int(played_ms)
    total_ms = int(frame["ms_played"].sum())
    buckets = [
        {
            "key": key,
            "label": key,
            "hours": round(value / 3_600_000, 2),
            "share_pct": round(value / max(total_ms, 1) * 100, 1),
        }
        for key, value in sorted(bucket_ms.items(), key=lambda item: (-item[1], item[0]))
    ]
    if unknown_ms:
        buckets.append(
            {
                "key": "unknown",
                "label": "未知年代",
                "hours": round(unknown_ms / 3_600_000, 2),
                "share_pct": round(unknown_ms / max(total_ms, 1) * 100, 1),
            }
        )
    return {
        "known_pct": round((total_ms - unknown_ms) / max(total_ms, 1) * 100, 2),
        "unknown_hours": round(unknown_ms / 3_600_000, 2),
        "buckets": buckets,
    }


def _taste_slices(conn: sqlite3.Connection, frame: pd.DataFrame) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for key, label, months in TASTE_SLICES:
        subset = frame[frame["ts_month"].isin(months)] if "ts_month" in frame else frame.copy()
        hours = (
            round(float(subset["ms_played"].sum()) / 3_600_000, 2) if "ms_played" in subset else 0.0
        )
        active_days = (
            int(subset["ts_date"].nunique()) if not subset.empty and "ts_date" in subset else 0
        )
        result.append(
            {
                "slice_key": key,
                "label": label,
                "months": list(months),
                "plays": int(len(subset)),
                "hours": hours,
                "active_days": active_days,
                "taste_profile": build_consumer_taste_profile(conn, subset),
                "release_era": build_release_era_distribution(conn, subset),
            }
        )
    return result


def build_yearly_stats(
    conn: sqlite3.Connection,
    year: int,
    context: YearlyReviewFilterContext,
    *,
    event_frame: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Build shared time distributions and stable taste slices from one play frame."""
    if event_frame is None:
        event_frame = load_plays(
            conn,
            min_ms=context.min_ms,
            music_only=context.music_only,
            merge_enabled=context.merge_enabled,
            dynamic_threshold=context.dynamic_threshold,
            max_merge_gap_minutes=context.max_merge_gap_minutes,
        )
    annual = _ensure_month(_annual_frame(event_frame, year))
    summary = _summary(annual)
    daily = _daily_trend(annual)
    return {
        "year": year,
        "empty": annual.empty,
        "summary": summary,
        "daily_metrics": _daily_metrics(summary),
        "daily_trend": daily,
        "cumulative_trend": _cumulative_trend(daily),
        "hourly_distribution": _hourly_distribution(annual),
        "weekday_distribution": _weekday_distribution(annual),
        "monthly_distribution": _monthly_distribution(annual),
        "behavior_summary": _behavior_summary(annual),
        "taste_profile": build_consumer_taste_profile(conn, annual),
        "release_era_profile": build_release_era_distribution(conn, annual),
        "taste_slices": _taste_slices(conn, annual),
    }
