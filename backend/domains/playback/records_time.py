"""時間密碼：時間維度的峰值與偏好（P1 section）。"""

from __future__ import annotations

import pandas as pd

from backend.domains.playback.records_helpers import safe_groupby_cols, safe_rename


def _entity_hourly_dominance(frame, group_col, name_col, artist_col, entity_type):
    """每小時段播放最多的 entity。"""
    if frame.empty:
        return pd.DataFrame()
    gb_cols = safe_groupby_cols(["ts_hour"], group_col, name_col, artist_col)
    hourly = frame.groupby(gb_cols).size().reset_index(name="plays")
    if hourly.empty:
        return pd.DataFrame()
    idx = hourly.groupby("ts_hour")["plays"].idxmax()
    best = hourly.loc[idx].sort_values("ts_hour").head(24).copy()
    best["rank"] = range(1, len(best) + 1)
    best["entity_type"] = entity_type
    best["entity_id"] = best[group_col].astype(str)
    best["value"] = best["plays"].astype(float)
    best["unit"] = "次"
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
    monthly = fm.groupby(gb_cols).size().reset_index(name="plays")
    if monthly.empty:
        return pd.DataFrame()
    idx = monthly.groupby("_ym")["plays"].idxmax()
    best = monthly.loc[idx].sort_values("plays", ascending=False).head(15).copy()
    best["rank"] = range(1, len(best) + 1)
    best["entity_type"] = entity_type
    best["entity_id"] = best[group_col].astype(str)
    best["value"] = best["plays"].astype(float)
    best["unit"] = "次"
    best["date"] = best["_ym"]
    best = safe_rename(best, name_col, artist_col)
    return best


def _entity_yearly_peak(frame, group_col, name_col, artist_col, entity_type):
    """每年播放最多的 entity。"""
    if frame.empty:
        return pd.DataFrame()
    gb_cols = safe_groupby_cols(["ts_year"], group_col, name_col, artist_col)
    yearly = frame.groupby(gb_cols).size().reset_index(name="plays")
    if yearly.empty:
        return pd.DataFrame()
    idx = yearly.groupby("ts_year")["plays"].idxmax()
    best = yearly.loc[idx].sort_values("ts_year", ascending=False).copy()
    best["rank"] = range(1, len(best) + 1)
    best["entity_type"] = entity_type
    best["entity_id"] = best[group_col].astype(str)
    best["value"] = best["plays"].astype(float)
    best["unit"] = "次"
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
    records["time_weekday_preference"] = _weekday_preference(event_frame)
    records["time_new_year_eve"] = _new_year_eve(event_frame)


def _late_night_peak_day(event_frame):
    if event_frame.empty:
        return pd.DataFrame()
    late = event_frame[event_frame["ts_hour"].between(0, 4)]
    if late.empty:
        return pd.DataFrame()
    daily_total = event_frame.groupby("ts_date").size().reset_index(name="total_plays")
    daily_late = late.groupby("ts_date").size().reset_index(name="late_plays")
    merged = daily_late.merge(daily_total, on="ts_date")
    merged = merged[merged["total_plays"] >= 20]
    if merged.empty:
        return pd.DataFrame()
    merged["late_ratio"] = merged["late_plays"] / merged["total_plays"]
    best = merged.sort_values("late_ratio", ascending=False).head(5)
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
            }
        )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _weekday_preference(event_frame):
    if event_frame.empty:
        return pd.DataFrame()
    dow_labels = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
    dow = event_frame.groupby("ts_dow").size().reset_index(name="plays")
    dow["name"] = dow["ts_dow"].map(dow_labels)
    dow["rank"] = range(1, len(dow) + 1)
    dow["value"] = dow["plays"].astype(float)
    dow["unit"] = "次"
    return dow.sort_values("plays", ascending=False)


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
            lambda d: str(int(d[:4]) - 1) + "-" + d[:4]
            if d.endswith("-01-01")
            else d[:4] + "-" + str(int(d[:4]) + 1)
        )
    )

    results = []
    for ny_year, grp in nye.groupby("_ny_year"):
        if len(grp) < 3:
            continue
        top_track = grp.groupby("track_name").size().sort_values(ascending=False)
        top_artist = grp.groupby("artist_name").size().sort_values(ascending=False)
        results.append(
            {
                "rank": len(results) + 1,
                "name": ny_year,
                "value": float(len(grp)),
                "unit": "次跨年播放",
                "date": ny_year,
                "caption": f"Top: {top_track.index[0]} — {top_artist.index[0]}",
            }
        )

    return pd.DataFrame(results).head(5) if results else pd.DataFrame()
