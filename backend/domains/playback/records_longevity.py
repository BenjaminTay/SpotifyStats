"""長線陪伴：連續天數、跨度、回歸和長期陪伴記錄（P0 核心 section）。"""

from __future__ import annotations

import pandas as pd

from backend.domains.playback.records_helpers import (
    TOP_RECORD_LIMIT,
    safe_groupby_cols,
    safe_rename,
    unique_cols,
)


def _longest_streak_days(frame, group_col, name_col, artist_col, entity_type="track"):
    """最長連續播放天數。"""
    if frame.empty:
        return pd.DataFrame()

    cols = unique_cols(group_col, name_col, artist_col, "ts_date")
    presence = frame[cols].drop_duplicates()
    sort_cols = unique_cols(group_col, "ts_date")
    presence = presence.sort_values(sort_cols)
    presence["ts_date"] = pd.to_datetime(presence["ts_date"])

    results = []
    for entity_id, grp in presence.groupby(group_col):
        name = str(grp[name_col].iloc[0]) if name_col in grp.columns else str(entity_id)
        artist = str(grp[artist_col].iloc[0]) if artist_col in grp.columns else ""

        if len(grp) < 2:
            results.append(
                {
                    "entity_id": str(entity_id),
                    "name": name,
                    "artist_name": artist,
                    "streak_days": 1,
                    "start_date": str(grp["ts_date"].iloc[0].date()),
                    "end_date": str(grp["ts_date"].iloc[-1].date()),
                    "total_plays": len(grp),
                    "total_hours": 0.0,
                }
            )
            continue

        dates = grp["ts_date"].dt.date.sort_values().tolist()
        max_streak = 1
        current_streak = 1
        streak_start = dates[0]
        best_start = dates[0]
        best_end = dates[0]

        for i in range(1, len(dates)):
            diff = (dates[i] - dates[i - 1]).days
            if diff == 1:
                current_streak += 1
                if current_streak > max_streak:
                    max_streak = current_streak
                    best_start = streak_start
                    best_end = dates[i]
            elif diff > 1:
                current_streak = 1
                streak_start = dates[i]

        # Total stats
        entity_frame = frame[frame[group_col] == entity_id]
        total_plays = len(entity_frame)
        total_hours = round(float(entity_frame["ms_played"].sum()) / 3_600_000, 1)

        results.append(
            {
                "entity_id": str(entity_id),
                "name": name,
                "artist_name": artist,
                "streak_days": max_streak,
                "start_date": str(best_start),
                "end_date": str(best_end),
                "total_plays": total_plays,
                "total_hours": total_hours,
            }
        )

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df = df.sort_values(
        ["streak_days", "total_plays", "end_date"], ascending=[False, False, False]
    ).head(TOP_RECORD_LIMIT)
    df["rank"] = range(1, len(df) + 1)
    df["entity_type"] = entity_type
    df["value"] = df["streak_days"].astype(float)
    df["unit"] = "天連續播放"
    df["secondary_value"] = df["total_hours"].astype(float)
    df["secondary_unit"] = "小時"
    return df


def _longest_span(frame, group_col, name_col, artist_col, entity_type="track"):
    """最長陪伴跨度。"""
    if frame.empty:
        return pd.DataFrame()

    gb_cols = safe_groupby_cols([], group_col, name_col, artist_col)
    span = (
        frame.groupby(gb_cols)
        .agg(
            first_date=("ts_date", "min"),
            last_date=("ts_date", "max"),
            total_plays=("play_id", "count"),
            total_hours=("ms_played", lambda s: round(float(s.sum()) / 3_600_000, 1)),
        )
        .reset_index()
    )
    span["first_date"] = pd.to_datetime(span["first_date"])
    span["last_date"] = pd.to_datetime(span["last_date"])
    span["span_days"] = (span["last_date"] - span["first_date"]).dt.days + 1
    span = span.sort_values("span_days", ascending=False).head(TOP_RECORD_LIMIT)
    span["rank"] = range(1, len(span) + 1)
    span["entity_type"] = entity_type
    span["entity_id"] = span[group_col].astype(str)
    span["value"] = span["span_days"].astype(float)
    span["unit"] = "天跨度"
    span["start_date"] = span["first_date"].dt.strftime("%Y-%m-%d")
    span["end_date"] = span["last_date"].dt.strftime("%Y-%m-%d")
    span["secondary_value"] = span["total_hours"].astype(float)
    span["secondary_unit"] = "小時"
    span = safe_rename(span, name_col, artist_col)
    return span


def _comeback_after_sleep(frame, group_col, name_col, artist_col, entity_type="track"):
    """沉睡後回歸。"""
    if frame.empty:
        return pd.DataFrame()

    cols = unique_cols(group_col, name_col, artist_col, "ts_date")
    presence = frame[cols].drop_duplicates()
    sort_cols = unique_cols(group_col, "ts_date")
    presence = presence.sort_values(sort_cols)
    presence["ts_date"] = pd.to_datetime(presence["ts_date"])

    results = []
    for entity_id, grp in presence.groupby(group_col):
        if len(grp) < 2:
            continue
        dates = grp["ts_date"].dt.date.sort_values().tolist()
        max_gap = 0
        gap_before = None
        gap_after = None
        for i in range(1, len(dates)):
            gap = (dates[i] - dates[i - 1]).days
            if gap > max_gap:
                max_gap = gap
                gap_before = dates[i - 1]
                gap_after = dates[i]

        if max_gap >= 7:
            name = str(grp[name_col].iloc[0]) if name_col in grp.columns else str(entity_id)
            artist = str(grp[artist_col].iloc[0]) if artist_col in grp.columns else ""
            total_plays = len(frame[frame[group_col] == entity_id])
            total_hours = round(
                float(frame[frame[group_col] == entity_id]["ms_played"].sum()) / 3_600_000, 1
            )
            results.append(
                {
                    "entity_id": str(entity_id),
                    "name": name,
                    "artist_name": artist,
                    "gap_days": max_gap,
                    "sleep_start": str(gap_before),
                    "wake_date": str(gap_after),
                    "total_plays": total_plays,
                    "total_hours": total_hours,
                }
            )

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df = df.sort_values("gap_days", ascending=False).head(TOP_RECORD_LIMIT)
    df["rank"] = range(1, len(df) + 1)
    df["entity_type"] = entity_type
    df["value"] = df["gap_days"].astype(float)
    df["unit"] = "天後回歸"
    df["start_date"] = df["sleep_start"]
    df["end_date"] = df["wake_date"]
    df["secondary_value"] = df["total_hours"].astype(float)
    df["secondary_unit"] = "小時"
    return df


def _most_active_months(frame, group_col, name_col, artist_col, entity_type="track"):
    """最活躍月份。"""
    if frame.empty:
        return pd.DataFrame()
    fm = frame.copy()
    fm["_ym"] = fm["ts_date"].astype(str).str[:7]
    gb_cols = safe_groupby_cols([], group_col, name_col, artist_col)
    active = (
        fm.groupby(gb_cols)["_ym"]
        .nunique()
        .reset_index(name="active_months")
        .sort_values("active_months", ascending=False)
        .head(TOP_RECORD_LIMIT)
    )
    active["rank"] = range(1, len(active) + 1)
    active["entity_type"] = entity_type
    active["entity_id"] = active[group_col].astype(str)
    active["value"] = active["active_months"].astype(float)
    active["unit"] = "個活躍月份"
    active = safe_rename(active, name_col, artist_col)
    return active


def _user_active_streak(event_frame):
    """用戶連續活躍天數。"""
    if event_frame.empty:
        return pd.DataFrame()
    dates = sorted(
        event_frame["ts_date"].drop_duplicates().apply(lambda x: pd.to_datetime(x).date()).tolist()
    )
    if not dates:
        return pd.DataFrame()

    max_streak = 1
    current_streak = 1
    best_start = dates[0]
    best_end = dates[0]
    streak_start = dates[0]

    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days == 1:
            current_streak += 1
        else:
            if current_streak > max_streak:
                max_streak = current_streak
                best_start = streak_start
                best_end = dates[i - 1]
            current_streak = 1
            streak_start = dates[i]

    if current_streak > max_streak:
        max_streak = current_streak
        best_start = streak_start
        best_end = dates[-1]

    return pd.DataFrame(
        [
            {
                "rank": 1,
                "name": "最長連續活躍",
                "value": float(max_streak),
                "unit": "天連續活躍",
                "start_date": str(best_start),
                "end_date": str(best_end),
                "secondary_value": float(len(dates)),
                "secondary_unit": "天活躍總數",
                "caption": f"從 {dates[0]} 到 {dates[-1]}，共 {len(dates)} 天有播放記錄",
            }
        ]
    )


def _entity_longevity_records(frame, group_col, name_col, artist_col, entity_type):
    if frame.empty:
        return {
            "longest_streak_days": pd.DataFrame(),
            "longest_span": pd.DataFrame(),
            "comeback_after_sleep": pd.DataFrame(),
            "most_active_months": pd.DataFrame(),
        }
    return {
        "longest_streak_days": _longest_streak_days(
            frame, group_col, name_col, artist_col, entity_type
        ),
        "longest_span": _longest_span(frame, group_col, name_col, artist_col, entity_type),
        "comeback_after_sleep": _comeback_after_sleep(
            frame, group_col, name_col, artist_col, entity_type
        ),
        "most_active_months": _most_active_months(
            frame, group_col, name_col, artist_col, entity_type
        ),
    }


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


def compute_longevity_records(
    records: dict,
    event_frame: pd.DataFrame,
    track_frame: pd.DataFrame,
    album_frame: pd.DataFrame,
    artist_frame: pd.DataFrame,
):
    """Populate longevity records."""
    for entity_type, frame in [
        ("track", track_frame),
        ("album", album_frame),
        ("artist", artist_frame),
    ]:
        if frame.empty:
            tr = {
                "longest_streak_days": pd.DataFrame(),
                "longest_span": pd.DataFrame(),
                "comeback_after_sleep": pd.DataFrame(),
                "most_active_months": pd.DataFrame(),
            }
        else:
            gcol, ncol, acol = _group_col_for(frame, entity_type)
            tr = _entity_longevity_records(frame, gcol, ncol, acol, entity_type)

        records[f"longevity_streak_{entity_type}"] = tr["longest_streak_days"]
        records[f"longevity_span_{entity_type}"] = tr["longest_span"]
        records[f"longevity_comeback_{entity_type}"] = tr["comeback_after_sleep"]
        records[f"longevity_active_months_{entity_type}"] = tr["most_active_months"]

    records["longevity_user_streak"] = _user_active_streak(event_frame)
