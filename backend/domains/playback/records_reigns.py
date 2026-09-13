"""個人王朝：某 entity 在日/月/年維度的統治記錄（P0 核心 section）。"""

from __future__ import annotations

import pandas as pd

from backend.domains.playback.records_helpers import (
    grouped_records_duration,
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
    daily = frame.groupby(gb_cols).agg(plays=("play_id", "count")).reset_index()
    daily = daily.merge(grouped_records_duration(frame, gb_cols), on=gb_cols, how="left")
    daily["total_ms"] = daily["total_ms"].fillna(0)
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
    monthly = fm.groupby(gb_cols).agg(plays=("play_id", "count")).reset_index()
    duration = grouped_records_duration(frame, ["ts_date", *gb_cols[1:]])
    if not duration.empty:
        duration["_ym"] = duration["ts_date"].astype(str).str[:7]
        duration = duration.groupby(gb_cols, dropna=False)["total_ms"].sum().reset_index()
    else:
        duration = grouped_records_duration(fm, gb_cols)
    monthly = monthly.merge(duration, on=gb_cols, how="left")
    monthly["total_ms"] = monthly["total_ms"].fillna(0)
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
    yearly = frame.groupby(gb_cols).agg(plays=("play_id", "count")).reset_index()
    yearly = yearly.merge(grouped_records_duration(frame, gb_cols), on=gb_cols, how="left")
    yearly["total_ms"] = yearly["total_ms"].fillna(0)
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

    # Sorting every entity group separately copies the full-width play frame
    # thousands of times on a real library.  Order the event stream once, then
    # select the first and Nth event with a vectorized per-entity ordinal.
    sequence_columns = ["ts_date"]
    if "ts" in frame.columns:
        sequence_columns.append("ts")
    if "play_id" in frame.columns:
        sequence_columns.append("play_id")
    ordered = frame.sort_values(sequence_columns, kind="stable").copy()
    ordered["_milestone_event_date"] = pd.to_datetime(ordered["ts_date"], errors="coerce")
    ordered = ordered[ordered["_milestone_event_date"].notna()]

    if entity_type == "album":
        if "album_release_date" not in ordered.columns:
            return pd.DataFrame()
        release_text = ordered["album_release_date"].astype("string")
        release_values = (
            ordered.loc[release_text.notna(), [group_col, "album_release_date"]]
            .assign(album_release_date=lambda data: data["album_release_date"].astype(str))
            .drop_duplicates()
        )
        release_counts = release_values.groupby(group_col, sort=False).size()
        single_release_values = release_values[
            release_values[group_col].isin(release_counts[release_counts == 1].index)
        ]
        single_release_values = single_release_values[
            single_release_values["album_release_date"].str.fullmatch(r"\d{4}-\d{2}-\d{2}")
        ]
        if single_release_values.empty:
            return pd.DataFrame()
        release_lookup = pd.to_datetime(
            single_release_values.set_index(group_col)["album_release_date"],
            errors="coerce",
        )
        ordered["_milestone_release_date"] = ordered[group_col].map(release_lookup)
        ordered = ordered[
            ordered["_milestone_release_date"].notna()
            & (ordered["_milestone_event_date"] >= ordered["_milestone_release_date"])
        ]

    if ordered.empty:
        return pd.DataFrame()

    ordered["_milestone_ordinal"] = ordered.groupby(group_col, sort=False).cumcount()
    first_rows = ordered[ordered["_milestone_ordinal"] == 0].set_index(group_col)
    milestone_rows = ordered[ordered["_milestone_ordinal"] == threshold - 1].set_index(group_col)
    if milestone_rows.empty:
        return pd.DataFrame()

    entity_ids = milestone_rows.index
    first_dates = first_rows.loc[entity_ids, "_milestone_event_date"]
    milestone_dates = milestone_rows["_milestone_event_date"]

    def metadata_values(column: str, fallback: str | None = None) -> pd.Series:
        if column == group_col:
            return pd.Series(entity_ids.astype(str), index=entity_ids)
        if column in frame.columns:
            return (
                frame[[group_col, column]]
                .drop_duplicates(subset=group_col, keep="first")
                .set_index(group_col)[column]
                .loc[entity_ids]
                .astype(str)
            )
        return pd.Series(entity_ids.astype(str) if fallback is None else fallback, index=entity_ids)

    names = metadata_values(name_col)
    artists = metadata_values(artist_col, "")
    df = pd.DataFrame(
        {
            "entity_id": entity_ids.astype(str),
            "name": names.to_numpy(),
            "artist_name": artists.to_numpy(),
            "days_to_milestone": (milestone_dates - first_dates).dt.days.to_numpy(),
            "milestone_target": threshold,
            "first_date": first_dates.dt.date.astype(str).to_numpy(),
            "milestone_date": milestone_dates.dt.date.astype(str).to_numpy(),
        }
    )
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
    daily = frame.groupby(gb_cols).agg(plays=("play_id", "count")).reset_index()
    daily = daily.merge(grouped_records_duration(frame, gb_cols), on=gb_cols, how="left")
    daily["total_ms"] = daily["total_ms"].fillna(0)
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
