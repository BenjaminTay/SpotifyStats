"""個人王朝：某 entity 在日/月/年維度的統治記錄（P0 核心 section）。"""

from __future__ import annotations

import pandas as pd

from backend.domains.playback.records_helpers import (
    safe_groupby_cols,
    safe_rename,
)
from backend.domains.playback.records_sorting import select_period_winners, sort_and_limit

MILESTONE_THRESHOLDS = {"track": 50, "album": 100, "artist": 250}


def _daily_champion(frame, group_col, name_col, artist_col, entity_type="track"):
    """每日冠軍次數。"""
    if frame.empty:
        return pd.DataFrame()
    gb_cols = safe_groupby_cols(["ts_date"], group_col, name_col, artist_col)
    daily = (
        frame.groupby(gb_cols)
        .agg(plays=("play_id", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
    )
    if daily.empty:
        return pd.DataFrame()
    champions = select_period_winners(
        daily,
        "ts_date",
        "plays",
        group_col,
        secondary_column="total_ms",
    )

    # Group by entity to count champion days
    ent_cols = safe_groupby_cols([], group_col, name_col, artist_col)
    counts = (
        champions.groupby(ent_cols)
        .agg(
            champion_days=("ts_date", "count"),
            winning_plays=("plays", "sum"),
            winning_ms=("total_ms", "sum"),
        )
        .reset_index()
    )
    counts = sort_and_limit(
        counts,
        ["champion_days", "winning_plays", "winning_ms", group_col],
        [False, False, False, True],
    )
    counts["entity_type"] = entity_type
    counts["entity_id"] = counts[group_col].astype(str)
    counts["value"] = counts["champion_days"].astype(float)
    counts["unit"] = "天冠軍"
    counts["total_plays"] = counts["winning_plays"].astype(int)
    counts["total_ms"] = counts["winning_ms"].astype(float)
    counts["total_hours"] = (counts["winning_ms"] / 3_600_000).round(1)
    counts = safe_rename(counts, name_col, artist_col)
    return counts


def _monthly_reign(frame, group_col, name_col, artist_col, entity_type="track"):
    """月度統治。"""
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
    champions = select_period_winners(
        monthly,
        "_ym",
        "plays",
        group_col,
        secondary_column="total_ms",
    )

    ent_cols = safe_groupby_cols([], group_col, name_col, artist_col)
    counts = (
        champions.groupby(ent_cols)
        .agg(
            month_champion=("_ym", "count"),
            winning_plays=("plays", "sum"),
            winning_ms=("total_ms", "sum"),
        )
        .reset_index()
    )
    counts = sort_and_limit(
        counts,
        ["month_champion", "winning_plays", "winning_ms", group_col],
        [False, False, False, True],
    )
    counts["entity_type"] = entity_type
    counts["entity_id"] = counts[group_col].astype(str)
    counts["value"] = counts["month_champion"].astype(float)
    counts["unit"] = "月冠軍"
    counts["total_plays"] = counts["winning_plays"].astype(int)
    counts["total_ms"] = counts["winning_ms"].astype(float)
    counts["total_hours"] = (counts["winning_ms"] / 3_600_000).round(1)
    counts = safe_rename(counts, name_col, artist_col)
    return counts


def _yearly_reign(frame, group_col, name_col, artist_col, entity_type="track"):
    """年度統治。"""
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
    champions = select_period_winners(
        yearly,
        "ts_year",
        "plays",
        group_col,
        secondary_column="total_ms",
    )
    champions = sort_and_limit(
        champions,
        ["ts_year", "plays", "total_ms", group_col],
        [True, False, False, True],
    )
    champions["entity_type"] = entity_type
    champions["entity_id"] = champions[group_col].astype(str)
    champions["value"] = champions["plays"].astype(float)
    champions["unit"] = "次"
    champions["total_plays"] = champions["plays"].astype(int)
    champions["total_ms"] = champions["total_ms"].astype(float)
    champions["total_hours"] = (champions["total_ms"] / 3_600_000).round(1)
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
    """最快里程碑：专辑忽略发行前播放，并从首次发行后播放开始计时。"""
    if frame.empty:
        return pd.DataFrame()

    threshold = MILESTONE_THRESHOLDS.get(entity_type, 50)

    results = []
    for entity_id, grp in frame.groupby(group_col):
        sequence_columns = ["ts_date"]
        if "ts" in grp.columns:
            sequence_columns.append("ts")
        if "play_id" in grp.columns:
            sequence_columns.append("play_id")
        grp_sorted = grp.sort_values(sequence_columns, kind="stable").copy()
        if entity_type == "album":
            if "album_release_date" not in grp_sorted.columns:
                continue
            release_values = (
                grp_sorted["album_release_date"].dropna().astype(str).drop_duplicates().tolist()
            )
            if (
                len(release_values) != 1
                or not pd.Series(release_values).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()
            ):
                continue
            release_date = pd.to_datetime(release_values[0], errors="coerce")
            if pd.isna(release_date):
                continue
            event_dates = pd.to_datetime(grp_sorted["ts_date"], errors="coerce")
            grp_sorted = grp_sorted[event_dates >= release_date]
            if grp_sorted.empty:
                continue
            first_date = pd.to_datetime(grp_sorted["ts_date"].iloc[0])
        else:
            first_date = pd.to_datetime(grp_sorted["ts_date"].iloc[0])

        if len(grp_sorted) < threshold:
            continue
        milestone_date = pd.to_datetime(grp_sorted["ts_date"].iloc[threshold - 1])

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
                    "milestone_target": threshold,
                    "first_date": str(first_date.date()),
                    "milestone_date": str(milestone_date.date()),
                }
            )

    if not results:
        return pd.DataFrame()
    df = pd.DataFrame(results)
    df = sort_and_limit(
        df,
        ["days_to_milestone", "milestone_date", "first_date", "entity_id"],
        [True, True, True, True],
    )
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
    daily = (
        frame.groupby(gb_cols)
        .agg(plays=("play_id", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
    )
    if daily.empty:
        return pd.DataFrame()
    champions = select_period_winners(
        daily,
        "ts_date",
        "plays",
        group_col,
        secondary_column="total_ms",
    )
    champions["ts_date"] = pd.to_datetime(champions["ts_date"])
    champions = champions.sort_values("ts_date")

    # Find longest consecutive champion streak per entity
    results = []
    for entity_id, grp in champions.groupby(group_col):
        if len(grp) < 2:
            continue
        grp = grp.sort_values("ts_date", kind="stable")
        grp["_streak_group"] = grp["ts_date"].diff().dt.days.ne(1).cumsum()
        candidates = []
        for _, streak in grp.groupby("_streak_group", sort=False):
            if len(streak) < 2:
                continue
            candidates.append(
                {
                    "streak_days": len(streak),
                    "start_date": streak["ts_date"].iloc[0].date(),
                    "end_date": streak["ts_date"].iloc[-1].date(),
                    "total_plays": int(streak["plays"].sum()),
                    "total_ms": float(streak["total_ms"].sum()),
                }
            )

        if candidates:
            best = max(
                candidates,
                key=lambda item: (
                    item["streak_days"],
                    item["total_plays"],
                    item["total_ms"],
                    item["end_date"],
                ),
            )
            name = str(grp[name_col].iloc[0]) if name_col in grp.columns else str(entity_id)
            artist = str(grp[artist_col].iloc[0]) if artist_col in grp.columns else ""
            results.append(
                {
                    "entity_id": str(entity_id),
                    "name": name,
                    "artist_name": artist,
                    "streak_days": best["streak_days"],
                    "start_date": str(best["start_date"]),
                    "end_date": str(best["end_date"]),
                    "total_plays": best["total_plays"],
                    "total_ms": best["total_ms"],
                }
            )

    if not results:
        return pd.DataFrame()
    df = sort_and_limit(
        pd.DataFrame(results),
        ["streak_days", "total_plays", "total_ms", "end_date", "entity_id"],
        [False, False, False, False, True],
    )
    df["entity_type"] = entity_type
    df["value"] = df["streak_days"].astype(float)
    df["unit"] = "天連續冠軍"
    df["total_hours"] = (df["total_ms"] / 3_600_000).round(1)
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
