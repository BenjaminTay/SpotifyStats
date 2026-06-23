"""狂熱時刻：極端播放行為記錄（P0 核心 section）。"""

from __future__ import annotations

import pandas as pd

from backend.domains.playback.records_helpers import (
    TOP_RECORD_LIMIT,
    safe_groupby_cols,
    safe_rename,
)

# ── 最小樣本門檻 ──
MIN_SAMPLE_PLAYS = 10
MIN_DAILY_PLAYS = 20


def _daily_binge(frame, group_col, name_col, artist_col, entity_type="track"):
    """單日爆聽：單日內某 entity 播放次數最高。"""
    if frame.empty:
        return pd.DataFrame()
    gb_cols = safe_groupby_cols(["ts_date"], group_col, name_col, artist_col or name_col)
    daily = frame.groupby(gb_cols).size().reset_index(name="plays")
    if daily.empty:
        return pd.DataFrame()
    idx = daily.groupby("ts_date")["plays"].idxmax()
    best = daily.loc[idx].sort_values("plays", ascending=False).head(TOP_RECORD_LIMIT).copy()
    best["rank"] = range(1, len(best) + 1)
    best["entity_type"] = entity_type
    best["entity_id"] = best[group_col].astype(str)
    best["value"] = best["plays"].astype(float)
    best["unit"] = "次"
    best["date"] = best["ts_date"].astype(str)
    best = safe_rename(best, name_col, artist_col)
    return best


def _daily_duration(frame, group_col, name_col, artist_col, entity_type="track"):
    """單日聆聽時長：單日內某 entity 累計播放時長最高。"""
    if frame.empty:
        return pd.DataFrame()
    gb_cols = safe_groupby_cols(["ts_date"], group_col, name_col, artist_col or name_col)
    daily = frame.groupby(gb_cols)["ms_played"].sum().reset_index(name="total_ms")
    if daily.empty:
        return pd.DataFrame()
    idx = daily.groupby("ts_date")["total_ms"].idxmax()
    best = daily.loc[idx].sort_values("total_ms", ascending=False).head(TOP_RECORD_LIMIT).copy()
    best["rank"] = range(1, len(best) + 1)
    best["entity_type"] = entity_type
    best["entity_id"] = best[group_col].astype(str)
    best["value"] = (best["total_ms"] / 3_600_000).round(1)
    best["unit"] = "小时"
    best["date"] = best["ts_date"].astype(str)
    best = safe_rename(best, name_col, artist_col)
    return best


def _consecutive_marathon(frame, group_col, name_col, artist_col, entity_type="track"):
    """連續播放馬拉松：播放序列中連續出現同一 entity 的最長 run。"""
    if frame.empty:
        return pd.DataFrame()
    df = frame.sort_values("ts").copy()
    df["_entity"] = df[group_col].astype(str)
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
    best = runs.sort_values("run_length", ascending=False).head(TOP_RECORD_LIMIT).copy()
    best["rank"] = range(1, len(best) + 1)
    best["entity_type"] = entity_type
    best["entity_id"] = best["_entity"]
    best["value"] = best["run_length"].astype(float)
    best["unit"] = "次連續播放"
    best["secondary_value"] = (best["total_ms"] / 3_600_000).round(1)
    best["secondary_unit"] = "小時"
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

    counts = (
        frame.groupby(gb_cols, dropna=False)
        .agg(
            entity_plays=("play_id", "count"),
            entity_ms=("ms_played", "sum"),
        )
        .reset_index()
    )
    if counts.empty:
        return {}

    counts = counts.sort_values(
        ["ts_date", "entity_plays", "entity_ms", name_col],
        ascending=[True, False, False, True],
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
            total_hours=("ms_played", lambda s: round(float(s.sum()) / 3_600_000, 1)),
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
            daily.sort_values("total_plays", ascending=False)
            .head(TOP_RECORD_LIMIT)["ts_date"]
            .astype(str)
            .tolist()
            + daily.sort_values("total_hours", ascending=False)
            .head(TOP_RECORD_LIMIT)["ts_date"]
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
    for rank, (_, row) in enumerate(daily.iterrows(), start=1):
        date = str(row["ts_date"])
        record = {
            "rank": rank,
            "entity_type": "day",
            "name": date,
            "value": float(row["total_plays"]),
            "unit": "次",
            "date": date,
            "secondary_value": float(row["total_hours"]),
            "secondary_unit": "小時",
            "total_plays": int(row["total_plays"]),
            "total_hours": float(row["total_hours"]),
            "unique_tracks": int(row["unique_tracks"]),
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
