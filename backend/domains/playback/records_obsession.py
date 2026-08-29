"""狂熱時刻：極端播放行為記錄（P0 核心 section）。"""

from __future__ import annotations

import pandas as pd

from backend.domains.playback.records_helpers import (
    safe_groupby_cols,
    safe_rename,
)
from backend.domains.playback.records_sorting import select_period_winners, sort_and_limit

# ── 最小樣本門檻 ──
MIN_SAMPLE_PLAYS = 10
MIN_DAILY_PLAYS = 20


def _daily_binge(frame, group_col, name_col, artist_col, entity_type="track"):
    """單日爆聽：單日內某 entity 播放次數最高。"""
    if frame.empty:
        return pd.DataFrame()
    gb_cols = safe_groupby_cols(["ts_date"], group_col, name_col, artist_col or name_col)
    daily = (
        frame.groupby(gb_cols)
        .agg(plays=("play_id", "count"), total_ms=("ms_played", "sum"))
        .reset_index()
    )
    if daily.empty:
        return pd.DataFrame()
    best = select_period_winners(
        daily,
        "ts_date",
        "plays",
        group_col,
        secondary_column="total_ms",
    )
    best = sort_and_limit(
        best,
        ["plays", "total_ms", "ts_date", group_col],
        [False, False, False, True],
    )
    best["entity_type"] = entity_type
    best["entity_id"] = best[group_col].astype(str)
    best["value"] = best["plays"].astype(float)
    best["unit"] = "次"
    best["secondary_value"] = (best["total_ms"] / 3_600_000).round(1)
    best["secondary_unit"] = "小时"
    best["total_ms"] = best["total_ms"].astype(float)
    best["date"] = best["ts_date"].astype(str)
    best = safe_rename(best, name_col, artist_col)
    return best


def _daily_duration(frame, group_col, name_col, artist_col, entity_type="track"):
    """單日聆聽時長：單日內某 entity 累計播放時長最高。"""
    if frame.empty:
        return pd.DataFrame()
    gb_cols = safe_groupby_cols(["ts_date"], group_col, name_col, artist_col or name_col)
    daily = (
        frame.groupby(gb_cols)
        .agg(total_ms=("ms_played", "sum"), plays=("play_id", "count"))
        .reset_index()
    )
    if daily.empty:
        return pd.DataFrame()
    best = select_period_winners(
        daily,
        "ts_date",
        "total_ms",
        group_col,
        secondary_column="plays",
    )
    best = sort_and_limit(
        best,
        ["total_ms", "plays", "ts_date", group_col],
        [False, False, False, True],
    )
    best["entity_type"] = entity_type
    best["entity_id"] = best[group_col].astype(str)
    best["value"] = (best["total_ms"] / 3_600_000).round(1)
    best["unit"] = "小时"
    best["secondary_value"] = best["plays"].astype(float)
    best["secondary_unit"] = "次"
    best["total_ms"] = best["total_ms"].astype(float)
    best["date"] = best["ts_date"].astype(str)
    best = safe_rename(best, name_col, artist_col)
    return best


def _consecutive_marathon(frame, group_col, name_col, artist_col, entity_type="track"):
    """連續播放馬拉松：播放序列中連續出現同一 entity 的最長 run。"""
    if frame.empty:
        return pd.DataFrame()
    df = frame.copy()
    df["_entity"] = df[group_col].astype(str)

    if entity_type == "artist" and "_artist_event_id" in df.columns:
        # Artist statistics fan one logical play out to every credited artist.
        # A featured artist row must not break the primary artist's streak:
        # continuity means that the artist is credited on adjacent logical
        # events, not that their fan-out rows happen to be adjacent.
        df = (
            df.drop_duplicates(["_entity", "_artist_event_id"])
            .sort_values(["_entity", "_artist_event_id", "ts"])
            .copy()
        )
        event_gap = df.groupby("_entity", sort=False)["_artist_event_id"].diff()
        df["_group"] = event_gap.ne(1).groupby(df["_entity"], sort=False).cumsum()
    else:
        sequence_columns = ["ts"]
        if "play_id" in df.columns:
            sequence_columns.append("play_id")
        df = df.sort_values(sequence_columns, kind="stable").copy()
        df["_group"] = (df["_entity"] != df["_entity"].shift(1)).cumsum()

    gb_cols = ["_entity", "_group"]
    if name_col in df.columns and name_col not in gb_cols:
        gb_cols.append(name_col)
    if artist_col in df.columns and artist_col not in gb_cols:
        gb_cols.append(artist_col)

    runs = (
        df.groupby(gb_cols)
        .agg(
            run_length=("play_id", "count"),
            total_ms=("ms_played", "sum"),
            start_ts=("ts", "first"),
            end_ts=("ts", "last"),
        )
        .reset_index()
    )
    if runs.empty:
        return pd.DataFrame()
    runs["_stable_run_key"] = (
        runs["_entity"].astype(str)
        + "|"
        + runs["start_ts"].astype(str)
        + "|"
        + runs["end_ts"].astype(str)
    )
    best = sort_and_limit(
        runs,
        ["run_length", "total_ms", "end_ts", "_stable_run_key"],
        [False, False, False, True],
    )
    best["entity_type"] = entity_type
    best["entity_id"] = best["_entity"]
    best["value"] = best["run_length"].astype(float)
    best["unit"] = "次連續播放"
    best["secondary_value"] = (best["total_ms"] / 3_600_000).round(1)
    best["secondary_unit"] = "小時"
    best["total_ms"] = best["total_ms"].astype(float)
    best["start_date"] = best["start_ts"].astype(str)
    best["end_date"] = best["end_ts"].astype(str)
    best = safe_rename(best, name_col, artist_col)
    return best


def _top_daily_entity(frame, group_col, name_col, artist_col=None, prefix="track"):
    """Return top-played entity labels by day."""
    if frame is None or frame.empty or "ts_date" not in frame.columns:
        return {}

    gb_cols = safe_groupby_cols(["ts_date"], group_col, name_col, artist_col or name_col)
    if len(gb_cols) <= 1:
        return {}

    aggregations = {
        "entity_plays": ("play_id", "count"),
        "entity_ms": ("ms_played", "sum"),
    }
    # A canonical track group is not itself a routable track detail ID. Keep a
    # real member track ID from the winning group so the daily snapshot can link
    # to an existing song detail page.
    if prefix == "track" and "track_id" in frame.columns:
        aggregations["detail_track_id"] = ("track_id", "first")

    counts = frame.groupby(gb_cols, dropna=False).agg(**aggregations).reset_index()
    if counts.empty:
        return {}

    counts = counts.sort_values(
        ["ts_date", "entity_plays", "entity_ms", group_col],
        ascending=[True, False, False, True],
        kind="stable",
    )
    best = counts.drop_duplicates("ts_date")

    result = {}
    for _, row in best.iterrows():
        date = str(row["ts_date"])
        item = {
            f"top_{prefix}_name": str(row[name_col]) if pd.notna(row[name_col]) else "",
            f"top_{prefix}_plays": int(row["entity_plays"]),
        }
        if artist_col and artist_col in row.index and artist_col != name_col:
            item[f"top_{prefix}_artist_name"] = (
                str(row[artist_col]) if pd.notna(row[artist_col]) else ""
            )
        if prefix == "track" and "detail_track_id" in row.index:
            detail_track_id = row["detail_track_id"]
            if pd.notna(detail_track_id):
                try:
                    item["top_track_entity_id"] = str(int(float(detail_track_id)))
                except (TypeError, ValueError, OverflowError):
                    item["top_track_entity_id"] = str(detail_track_id)
        result[date] = item
    return result


def _daily_total_record(event_frame, track_frame=None, album_frame=None, artist_frame=None):
    """單日總量紀錄。"""
    if event_frame.empty:
        return pd.DataFrame()

    track_source = track_frame if track_frame is not None and not track_frame.empty else event_frame
    track_group_col = (
        "canonical_track_id" if "canonical_track_id" in track_source.columns else "track_id"
    )
    track_name_col = (
        "canonical_track_name" if "canonical_track_name" in track_source.columns else "track_name"
    )

    daily = (
        event_frame.groupby("ts_date")
        .agg(
            total_plays=("play_id", "count"),
            total_ms=("ms_played", "sum"),
        )
        .reset_index()
    )
    unique_tracks = (
        track_source.groupby("ts_date")[track_group_col].nunique().reset_index(name="unique_tracks")
    )
    daily = daily.merge(unique_tracks, on="ts_date", how="left")
    daily["unique_tracks"] = daily["unique_tracks"].fillna(0).astype(int)
    if daily.empty:
        return pd.DataFrame()
    daily["total_hours"] = (daily["total_ms"] / 3_600_000).round(1)
    daily["plays_rank"] = daily["total_plays"].rank(method="min", ascending=False).astype(int)
    daily["hours_rank"] = daily["total_ms"].rank(method="min", ascending=False).astype(int)
    plays_top_tied = bool(daily["plays_rank"].eq(1).sum() > 1)
    hours_top_tied = bool(daily["hours_rank"].eq(1).sum() > 1)

    album_source = album_frame if album_frame is not None and not album_frame.empty else event_frame
    album_group_col = (
        "album_project_id" if "album_project_id" in album_source.columns else "album_name"
    )
    album_name_col = (
        "album_project_name" if "album_project_name" in album_source.columns else "album_name"
    )

    artist_source = (
        artist_frame if artist_frame is not None and not artist_frame.empty else event_frame
    )

    top_track = _top_daily_entity(
        track_source, track_group_col, track_name_col, "artist_name", "track"
    )
    top_album = _top_daily_entity(
        album_source, album_group_col, album_name_col, "artist_name", "album"
    )
    top_artist = _top_daily_entity(artist_source, "artist_name", "artist_name", None, "artist")

    selected_dates = list(
        dict.fromkeys(
            sort_and_limit(
                daily,
                ["total_plays", "total_ms", "ts_date"],
                [False, False, False],
                assign_rank=False,
            )["ts_date"]
            .astype(str)
            .tolist()
            + sort_and_limit(
                daily,
                ["total_ms", "total_plays", "ts_date"],
                [False, False, False],
                assign_rank=False,
            )["ts_date"]
            .astype(str)
            .tolist()
        )
    )
    daily = daily[daily["ts_date"].astype(str).isin(selected_dates)].copy()
    daily["_date_order"] = (
        daily["ts_date"].astype(str).map({date: idx for idx, date in enumerate(selected_dates)})
    )
    daily = daily.sort_values("_date_order")

    records = []
    for _, row in daily.iterrows():
        date = str(row["ts_date"])
        record = {
            "rank": int(row["plays_rank"]),
            "plays_rank": int(row["plays_rank"]),
            "hours_rank": int(row["hours_rank"]),
            "entity_type": "day",
            "name": date,
            "value": float(row["total_plays"]),
            "unit": "次",
            "date": date,
            "secondary_value": float(row["total_hours"]),
            "secondary_unit": "小時",
            "total_plays": int(row["total_plays"]),
            "total_ms": float(row["total_ms"]),
            "total_hours": float(row["total_hours"]),
            "unique_tracks": int(row["unique_tracks"]),
            "rank_basis": "total_plays",
            "is_top": bool(int(row["plays_rank"]) == 1),
            "is_tied_top": plays_top_tied,
            "plays_top_tied": plays_top_tied,
            "hours_top_tied": hours_top_tied,
            "caption": (
                f"當日播放 {int(row['total_plays'])} 次，共 {row['total_hours']} 小時，"
                f"涵蓋 {int(row['unique_tracks'])} 首歌曲"
            ),
        }
        record.update(top_track.get(date, {}))
        record.update(top_album.get(date, {}))
        record.update(top_artist.get(date, {}))
        records.append(record)

    return pd.DataFrame(records) if records else pd.DataFrame()


def _build_entity_records(frame, group_col, name_col, artist_col, entity_type):
    """為一個 entity type 構建三種記錄。"""
    if frame.empty:
        return {
            "daily_binge": pd.DataFrame(),
            "daily_duration": pd.DataFrame(),
            "consecutive_marathon": pd.DataFrame(),
        }
    return {
        "daily_binge": _daily_binge(frame, group_col, name_col, artist_col, entity_type),
        "daily_duration": _daily_duration(frame, group_col, name_col, artist_col, entity_type),
        "consecutive_marathon": _consecutive_marathon(
            frame, group_col, name_col, artist_col, entity_type
        ),
    }


def _group_col_for(frame, entity_type):
    """Get appropriate grouping columns for a given entity type."""
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
    else:  # artist
        return "artist_name", "artist_name", "artist_name"


def compute_obsession_records(
    records: dict,
    event_frame: pd.DataFrame,
    track_frame: pd.DataFrame,
    album_frame: pd.DataFrame,
    artist_frame: pd.DataFrame,
):
    """Populate obsession records."""
    for entity_type, frame in [
        ("track", track_frame),
        ("album", album_frame),
        ("artist", artist_frame),
    ]:
        if frame.empty:
            tr = {
                "daily_binge": pd.DataFrame(),
                "daily_duration": pd.DataFrame(),
                "consecutive_marathon": pd.DataFrame(),
            }
        else:
            gcol, ncol, acol = _group_col_for(frame, entity_type)
            tr = _build_entity_records(frame, gcol, ncol, acol, entity_type)

        records[f"obsession_daily_binge_{entity_type}"] = tr["daily_binge"]
        records[f"obsession_daily_duration_{entity_type}"] = tr["daily_duration"]
        records[f"obsession_consecutive_marathon_{entity_type}"] = tr["consecutive_marathon"]

    records["obsession_daily_total"] = _daily_total_record(
        event_frame, track_frame, album_frame, artist_frame
    )
