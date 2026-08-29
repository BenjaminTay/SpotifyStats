"""時間密碼：時間維度的峰值與偏好（P1 section）。"""

from __future__ import annotations

import pandas as pd

from backend.domains.playback.records_helpers import (
    TOP_RECORD_LIMIT,
    safe_groupby_cols,
    safe_rename,
)
from backend.domains.playback.records_sorting import select_period_winners, sort_and_limit

LATE_NIGHT_MONTHLY_MIN_PLAYS = 500
LATE_NIGHT_QUARTERLY_MIN_PLAYS = 1500


def _entity_hourly_dominance(frame, group_col, name_col, artist_col, entity_type):
    """每小時段播放最多的 entity。"""
    if frame.empty:
        return pd.DataFrame()
    gb_cols = safe_groupby_cols(["ts_hour"], group_col, name_col, artist_col)
    hourly = (
        frame.groupby(gb_cols)
        .agg(plays=("play_id", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
    )
    if hourly.empty:
        return pd.DataFrame()
    best = select_period_winners(
        hourly,
        "ts_hour",
        "plays",
        group_col,
        secondary_column="total_ms",
    )
    best = sort_and_limit(
        best,
        ["ts_hour", group_col],
        [True, True],
        limit=24,
    )
    best["entity_type"] = entity_type
    best["entity_id"] = best[group_col].astype(str)
    best["value"] = best["plays"].astype(float)
    best["unit"] = "次"
    best["secondary_value"] = (best["total_ms"] / 3_600_000).round(1)
    best["secondary_unit"] = "小时"
    best["total_ms"] = best["total_ms"].astype(float)
    best["date"] = best["ts_hour"].apply(lambda h: f"{h}:00")
    best = safe_rename(best, name_col, artist_col)
    return best


def _entity_monthly_peak(frame, group_col, name_col, artist_col, entity_type):
    """每月播放最多的 entity。"""
    if frame.empty:
        return pd.DataFrame()
    fm = frame.copy()
    fm["_ym"] = fm["ts_date"].astype(str).str[:7]
    gb_cols = safe_groupby_cols(["_ym"], group_col, name_col, artist_col)
    monthly = (
        fm.groupby(gb_cols)
        .agg(plays=("play_id", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
    )
    if monthly.empty:
        return pd.DataFrame()
    best = select_period_winners(
        monthly,
        "_ym",
        "plays",
        group_col,
        secondary_column="total_ms",
    )
    best = sort_and_limit(
        best,
        ["plays", "total_ms", "_ym", group_col],
        [False, False, False, True],
    )
    best["entity_type"] = entity_type
    best["entity_id"] = best[group_col].astype(str)
    best["value"] = best["plays"].astype(float)
    best["unit"] = "次"
    best["secondary_value"] = (best["total_ms"] / 3_600_000).round(1)
    best["secondary_unit"] = "小时"
    best["total_ms"] = best["total_ms"].astype(float)
    best["date"] = best["_ym"]
    best = safe_rename(best, name_col, artist_col)
    return best


def _entity_yearly_peak(frame, group_col, name_col, artist_col, entity_type):
    """每年播放最多的 entity。"""
    if frame.empty:
        return pd.DataFrame()
    gb_cols = safe_groupby_cols(["ts_year"], group_col, name_col, artist_col)
    yearly = (
        frame.groupby(gb_cols)
        .agg(plays=("play_id", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
    )
    if yearly.empty:
        return pd.DataFrame()
    best = select_period_winners(
        yearly,
        "ts_year",
        "plays",
        group_col,
        secondary_column="total_ms",
    )
    best = sort_and_limit(
        best,
        ["ts_year", group_col],
        [False, True],
    )
    best["entity_type"] = entity_type
    best["entity_id"] = best[group_col].astype(str)
    best["value"] = best["plays"].astype(float)
    best["unit"] = "次"
    best["secondary_value"] = (best["total_ms"] / 3_600_000).round(1)
    best["secondary_unit"] = "小时"
    best["total_ms"] = best["total_ms"].astype(float)
    best["date"] = best["ts_year"].astype(str)
    best = safe_rename(best, name_col, artist_col)
    return best


def _group_col_for(frame, entity_type):
    if entity_type == "track":
        return (
            "canonical_track_id" if "canonical_track_id" in frame.columns else "track_id",
            "canonical_track_name" if "canonical_track_name" in frame.columns else "track_name",
            "artist_name",
        )
    elif entity_type == "album":
        return (
            "album_project_id" if "album_project_id" in frame.columns else "album_name",
            "album_project_name" if "album_project_name" in frame.columns else "album_name",
            "artist_name",
        )
    else:
        return "artist_name", "artist_name", "artist_name"


def compute_time_pattern_records(
    records: dict,
    event_frame: pd.DataFrame,
    track_frame: pd.DataFrame,
    album_frame: pd.DataFrame,
    artist_frame: pd.DataFrame,
):
    """Populate time pattern records."""

    for entity_type, frame in [
        ("track", track_frame),
        ("album", album_frame),
        ("artist", artist_frame),
    ]:
        if frame.empty:
            records[f"time_hourly_dominance_{entity_type}"] = pd.DataFrame()
            records[f"time_monthly_peak_{entity_type}"] = pd.DataFrame()
            records[f"time_yearly_peak_{entity_type}"] = pd.DataFrame()
        else:
            gcol, ncol, acol = _group_col_for(frame, entity_type)
            records[f"time_hourly_dominance_{entity_type}"] = _entity_hourly_dominance(
                frame, gcol, ncol, acol, entity_type
            )
            records[f"time_monthly_peak_{entity_type}"] = _entity_monthly_peak(
                frame, gcol, ncol, acol, entity_type
            )
            records[f"time_yearly_peak_{entity_type}"] = _entity_yearly_peak(
                frame, gcol, ncol, acol, entity_type
            )

    # Late night peak day
    records["time_late_night_peak_day"] = _late_night_peak_day(event_frame)
    monthly_late, quarterly_late = _late_night_trajectory(event_frame)
    records["time_late_night_trajectory_monthly"] = monthly_late
    records["time_late_night_trajectory_quarterly"] = quarterly_late
    records["time_late_night_monthly_min_plays"] = LATE_NIGHT_MONTHLY_MIN_PLAYS
    records["time_late_night_quarterly_min_plays"] = LATE_NIGHT_QUARTERLY_MIN_PLAYS
    records["time_weekday_preference"] = _weekday_preference(event_frame)
    records["time_new_year_eve"] = _new_year_eve(event_frame)


def _late_night_peak_day(event_frame):
    if event_frame.empty:
        return pd.DataFrame()
    late = event_frame[event_frame["ts_hour"].between(0, 4)]
    if late.empty:
        return pd.DataFrame()
    daily_total = (
        event_frame.groupby("ts_date")
        .agg(total_plays=("play_id", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
    )
    daily_late = late.groupby("ts_date").size().reset_index(name="late_plays")
    merged = daily_late.merge(daily_total, on="ts_date")
    merged = merged[merged["total_plays"] >= 20]
    if merged.empty:
        return pd.DataFrame()
    merged["late_ratio"] = merged["late_plays"] / merged["total_plays"]
    merged = merged.sort_values(
        ["late_ratio", "late_plays", "total_plays", "ts_date"],
        ascending=[False, False, False, False],
        kind="stable",
    )
    best = merged.head(TOP_RECORD_LIMIT)
    rows = []
    for _, row in best.iterrows():
        rows.append(
            {
                "rank": len(rows) + 1,
                "name": str(row["ts_date"]),
                "value": round(float(row["late_ratio"]) * 100, 1),
                "unit": "% 深夜播放",
                "date": str(row["ts_date"]),
                "secondary_value": float(row["late_plays"]),
                "secondary_unit": "次深夜播放",
                "total_plays": int(row["total_plays"]),
                "total_ms": float(row["total_ms"]),
            }
        )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _late_night_trajectory(event_frame):
    """按月/季度计算 0:00–4:59 深夜有效播放占比。"""
    empty = pd.DataFrame()
    if event_frame.empty:
        return empty, empty

    frame = event_frame.copy()
    dates = pd.to_datetime(frame["ts_date"], errors="coerce")
    frame = frame[dates.notna()].copy()
    if frame.empty:
        return empty, empty
    dates = dates[dates.notna()]
    frame["_month"] = dates.dt.strftime("%Y-%m")
    frame["_quarter"] = dates.dt.to_period("Q").astype(str)
    frame["_is_late"] = frame["ts_hour"].between(0, 4)

    def aggregate(period_col, threshold):
        grouped = (
            frame.groupby(period_col)
            .agg(total_plays=("_is_late", "size"), late_plays=("_is_late", "sum"))
            .reset_index()
            .rename(columns={period_col: "name"})
            .sort_values("name")
        )
        if grouped.empty:
            return empty
        grouped["rank"] = range(1, len(grouped) + 1)
        grouped["value"] = (grouped["late_plays"] / grouped["total_plays"] * 100).round(1)
        grouped["unit"] = "% 深夜播放"
        grouped["date"] = grouped["name"]
        grouped["secondary_value"] = grouped["late_plays"].astype(float)
        grouped["secondary_unit"] = "次深夜播放"
        grouped["qualified"] = grouped["total_plays"] >= threshold
        grouped["caption"] = grouped.apply(
            lambda row: f"{int(row['late_plays'])} / {int(row['total_plays'])} 次有效播放",
            axis=1,
        )
        return grouped

    return (
        aggregate("_month", LATE_NIGHT_MONTHLY_MIN_PLAYS),
        aggregate("_quarter", LATE_NIGHT_QUARTERLY_MIN_PLAYS),
    )


def _weekday_preference(event_frame):
    if event_frame.empty:
        return pd.DataFrame()
    dow_labels = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
    dow = (
        event_frame.groupby("ts_dow")
        .agg(
            plays=("play_id", "count"),
            total_ms=("ms_played", "sum"),
            active_days=("ts_date", "nunique"),
        )
        .reset_index()
    )
    dow["name"] = dow["ts_dow"].map(dow_labels)
    dow["value"] = dow["plays"].astype(float)
    dow["unit"] = "次"
    dow["avg_plays_per_active_day"] = dow["plays"] / dow["active_days"].clip(lower=1)
    dow = sort_and_limit(
        dow,
        ["plays", "avg_plays_per_active_day", "ts_dow"],
        [False, False, True],
        limit=None,
    )
    return dow


def _new_year_eve(event_frame):
    """跨年時刻：跨年午夜前後播放的歌曲。"""
    if event_frame.empty:
        return pd.DataFrame()

    # Find plays on Dec 31 (late night) and Jan 1 (early morning)
    nye = event_frame[
        (
            (event_frame["ts_date"].astype(str).str.endswith("-12-31"))
            & (event_frame["ts_hour"] >= 20)
        )
        | (
            (event_frame["ts_date"].astype(str).str.endswith("-01-01"))
            & (event_frame["ts_hour"] <= 4)
        )
    ].copy()

    if nye.empty:
        return pd.DataFrame()

    # Group by year (use Jan 1 year as the "new year")
    nye["_ny_year"] = (
        nye["ts_date"]
        .astype(str)
        .apply(
            lambda d: (
                str(int(d[:4]) - 1) + "-" + d[:4]
                if d.endswith("-01-01")
                else d[:4] + "-" + str(int(d[:4]) + 1)
            )
        )
    )

    results = []
    for ny_year, grp in nye.groupby("_ny_year"):
        if len(grp) < 3:
            continue
        top_track = (
            grp.groupby("track_name")
            .size()
            .reset_index(name="count")
            .sort_values(["count", "track_name"], ascending=[False, True], kind="stable")
        )
        top_artist = (
            grp.groupby("artist_name")
            .size()
            .reset_index(name="count")
            .sort_values(["count", "artist_name"], ascending=[False, True], kind="stable")
        )
        results.append(
            {
                "name": ny_year,
                "value": float(len(grp)),
                "unit": "次跨年播放",
                "date": ny_year,
                "secondary_value": float(grp["ms_played"].sum() / 3_600_000),
                "secondary_unit": "小时",
                "total_plays": int(len(grp)),
                "total_ms": float(grp["ms_played"].sum()),
                "caption": f"Top: {top_track.iloc[0]['track_name']} — {top_artist.iloc[0]['artist_name']}",
            }
        )

    if not results:
        return pd.DataFrame()
    return sort_and_limit(
        pd.DataFrame(results),
        ["value", "total_ms", "date"],
        [False, False, False],
    )
