"""個人王朝：某 entity 在日/月/年維度的統治記錄（P0 核心 section）。"""

from __future__ import annotations

import pandas as pd

from backend.domains.playback.records_helpers import (
    TOP_RECORD_LIMIT,
    safe_groupby_cols,
    safe_rename,
)


def _daily_champion(frame, group_col, name_col, artist_col, entity_type="track"):
    """每日冠軍次數。"""
    if frame.empty:
        return pd.DataFrame()
    gb_cols = safe_groupby_cols(["ts_date"], group_col, name_col, artist_col)
    daily = frame.groupby(gb_cols).size().reset_index(name="plays")
    if daily.empty:
        return pd.DataFrame()
    idx = daily.groupby("ts_date")["plays"].idxmax()
    champions = daily.loc[idx].copy()

    # Group by entity to count champion days
    ent_cols = safe_groupby_cols([], group_col, name_col, artist_col)
    counts = (
        champions.groupby(ent_cols)
        .size()
        .reset_index(name="champion_days")
        .sort_values("champion_days", ascending=False)
        .head(TOP_RECORD_LIMIT)
    )
    counts["rank"] = range(1, len(counts) + 1)
    counts["entity_type"] = entity_type
    counts["entity_id"] = counts[group_col].astype(str)
    counts["value"] = counts["champion_days"].astype(float)
    counts["unit"] = "天冠軍"
    counts = safe_rename(counts, name_col, artist_col)
    return counts


def _monthly_reign(frame, group_col, name_col, artist_col, entity_type="track"):
    """月度統治。"""
    if frame.empty:
        return pd.DataFrame()
    fm = frame.copy()
    fm["_ym"] = fm["ts_date"].astype(str).str[:7]
    gb_cols = safe_groupby_cols(["_ym"], group_col, name_col, artist_col)
    monthly = fm.groupby(gb_cols).size().reset_index(name="plays")
    if monthly.empty:
        return pd.DataFrame()
    idx = monthly.groupby("_ym")["plays"].idxmax()
    champions = monthly.loc[idx].copy()

    ent_cols = safe_groupby_cols([], group_col, name_col, artist_col)
    counts = (
        champions.groupby(ent_cols)
        .size()
        .reset_index(name="month_champion")
        .sort_values("month_champion", ascending=False)
        .head(TOP_RECORD_LIMIT)
    )
    counts["rank"] = range(1, len(counts) + 1)
    counts["entity_type"] = entity_type
    counts["entity_id"] = counts[group_col].astype(str)
    counts["value"] = counts["month_champion"].astype(float)
    counts["unit"] = "月冠軍"
    counts = safe_rename(counts, name_col, artist_col)
    return counts


def _yearly_reign(frame, group_col, name_col, artist_col, entity_type="track"):
    """年度統治。"""
    if frame.empty:
        return pd.DataFrame()
    gb_cols = safe_groupby_cols(["ts_year"], group_col, name_col, artist_col)
    yearly = frame.groupby(gb_cols).size().reset_index(name="plays")
    if yearly.empty:
        return pd.DataFrame()
    idx = yearly.groupby("ts_year")["plays"].idxmax()
    champions = (
        yearly.loc[idx].sort_values("ts_year", ascending=False).head(TOP_RECORD_LIMIT).copy()
    )
    champions["rank"] = range(1, len(champions) + 1)
    champions["entity_type"] = entity_type
    champions["entity_id"] = champions[group_col].astype(str)
    champions["value"] = champions["plays"].astype(float)
    champions["unit"] = "次"
    champions["date"] = champions["ts_year"].astype(str)
    champions = safe_rename(champions, name_col, artist_col)
    return champions


def _entity_reign_records(frame, group_col, name_col, artist_col, entity_type):
    if frame.empty:
        return {
            "daily_champion": pd.DataFrame(),
            "monthly_reign": pd.DataFrame(),
            "yearly_reign": pd.DataFrame(),
            "fastest_milestone": pd.DataFrame(),
            "consecutive_champion_days": pd.DataFrame(),
        }
    return {
        "daily_champion": _daily_champion(frame, group_col, name_col, artist_col, entity_type),
        "monthly_reign": _monthly_reign(frame, group_col, name_col, artist_col, entity_type),
        "yearly_reign": _yearly_reign(frame, group_col, name_col, artist_col, entity_type),
        "fastest_milestone": _fastest_milestone(
            frame, group_col, name_col, artist_col, entity_type
        ),
        "consecutive_champion_days": _consecutive_champion_days(
            frame, group_col, name_col, artist_col, entity_type
        ),
    }


def _fastest_milestone(frame, group_col, name_col, artist_col, entity_type="track"):
    """最快里程碑：從首次播放到達到播放次數閾值所需天數最短的 entity。"""
    if frame.empty:
        return pd.DataFrame()

    # Thresholds by entity type
    thresholds = {"track": [10, 25, 50], "album": [25, 50, 100], "artist": [50, 100, 250]}.get(
        entity_type, [50]
    )

    results = []
    for entity_id, grp in frame.groupby(group_col):
        if len(grp) < thresholds[0]:
            continue
        grp_sorted = grp.sort_values("ts_date")
        first_date = pd.to_datetime(grp_sorted["ts_date"].iloc[0])
        cumsum = 0
        milestone_date = None
        for _, row in grp_sorted.iterrows():
            cumsum += 1
            if cumsum >= thresholds[0] and milestone_date is None:
                milestone_date = pd.to_datetime(row["ts_date"])
                break

        if milestone_date is not None:
            days = (milestone_date - first_date).days
            name = str(grp[name_col].iloc[0]) if name_col in grp.columns else str(entity_id)
            artist = str(grp[artist_col].iloc[0]) if artist_col in grp.columns else ""
            results.append(
                {
                    "entity_id": str(entity_id),
                    "name": name,
                    "artist_name": artist,
                    "days_to_milestone": days,
                    "milestone_target": thresholds[0],
                    "first_date": str(first_date.date()),
                    "milestone_date": str(milestone_date.date()),
                }
            )

    if not results:
        return pd.DataFrame()
    df = pd.DataFrame(results).sort_values("days_to_milestone").head(TOP_RECORD_LIMIT)
    df["rank"] = range(1, len(df) + 1)
    df["entity_type"] = entity_type
    df["value"] = df["days_to_milestone"].astype(float)
    df["unit"] = f"天達{int(df['milestone_target'].iloc[0])}次"
    df["start_date"] = df["first_date"]
    df["end_date"] = df["milestone_date"]
    return df


def _consecutive_champion_days(frame, group_col, name_col, artist_col, entity_type="track"):
    """連續冠軍天數：連續多天成為日冠軍的 entity。"""
    if frame.empty:
        return pd.DataFrame()

    # Get daily champion for each day
    gb_cols = safe_groupby_cols(["ts_date"], group_col, name_col, artist_col)
    daily = frame.groupby(gb_cols).size().reset_index(name="plays")
    if daily.empty:
        return pd.DataFrame()
    idx = daily.groupby("ts_date")["plays"].idxmax()
    champions = daily.loc[idx].copy()
    champions["ts_date"] = pd.to_datetime(champions["ts_date"])
    champions = champions.sort_values("ts_date")

    # Find longest consecutive champion streak per entity
    results = []
    for entity_id, grp in champions.groupby(group_col):
        if len(grp) < 2:
            continue
        dates = sorted(grp["ts_date"].dt.date.tolist())
        max_streak = 1
        cur = 1
        best_start = dates[0]
        best_end = dates[0]
        streak_start = dates[0]

        for i in range(1, len(dates)):
            if (dates[i] - dates[i - 1]).days == 1:
                cur += 1
                if cur > max_streak:
                    max_streak = cur
                    best_start = streak_start
                    best_end = dates[i]
            else:
                cur = 1
                streak_start = dates[i]

        if max_streak >= 2:
            name = str(grp[name_col].iloc[0]) if name_col in grp.columns else str(entity_id)
            artist = str(grp[artist_col].iloc[0]) if artist_col in grp.columns else ""
            results.append(
                {
                    "entity_id": str(entity_id),
                    "name": name,
                    "artist_name": artist,
                    "streak_days": max_streak,
                    "start_date": str(best_start),
                    "end_date": str(best_end),
                }
            )

    if not results:
        return pd.DataFrame()
    df = pd.DataFrame(results).sort_values("streak_days", ascending=False).head(TOP_RECORD_LIMIT)
    df["rank"] = range(1, len(df) + 1)
    df["entity_type"] = entity_type
    df["value"] = df["streak_days"].astype(float)
    df["unit"] = "天連續冠軍"
    return df


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


def compute_reign_records(
    records: dict,
    event_frame: pd.DataFrame,
    track_frame: pd.DataFrame,
    album_frame: pd.DataFrame,
    artist_frame: pd.DataFrame,
):
    """Populate reign records."""
    for entity_type, frame in [
        ("track", track_frame),
        ("album", album_frame),
        ("artist", artist_frame),
    ]:
        if frame.empty:
            tr = {
                "daily_champion": pd.DataFrame(),
                "monthly_reign": pd.DataFrame(),
                "yearly_reign": pd.DataFrame(),
                "fastest_milestone": pd.DataFrame(),
                "consecutive_champion_days": pd.DataFrame(),
            }
        else:
            gcol, ncol, acol = _group_col_for(frame, entity_type)
            tr = _entity_reign_records(frame, gcol, ncol, acol, entity_type)

        records[f"reign_daily_champion_{entity_type}"] = tr["daily_champion"]
        records[f"reign_monthly_reign_{entity_type}"] = tr["monthly_reign"]
        records[f"reign_yearly_reign_{entity_type}"] = tr["yearly_reign"]
        records[f"reign_fastest_milestone_{entity_type}"] = tr["fastest_milestone"]
        records[f"reign_consecutive_champion_{entity_type}"] = tr["consecutive_champion_days"]
