"""行為奇觀：快進、Shuffle、平台、離線、里程碑（P1/P2 section）。"""

from __future__ import annotations

import pandas as pd

from backend.domains.playback.records_helpers import (
    TOP_RECORD_LIMIT,
    safe_groupby_cols,
    safe_rename,
)


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


def _skip_storm(frame, group_col, name_col, artist_col, entity_type):
    """快進風暴：被快進 (reason_end='fwdbtn') 比例最高的 entity。"""
    if frame.empty or "reason_end" not in frame.columns:
        return pd.DataFrame()
    gb_cols = safe_groupby_cols([], group_col, name_col, artist_col)
    agg = (
        frame.groupby(gb_cols)
        .agg(
            total_plays=("play_id", "count"),
            fwd_plays=("reason_end", lambda x: (x == "fwdbtn").sum()),
        )
        .reset_index()
    )
    agg = agg[agg["total_plays"] >= 10]
    if agg.empty:
        return pd.DataFrame()
    agg["fwd_rate"] = agg["fwd_plays"] / agg["total_plays"]
    best = agg.sort_values("fwd_rate", ascending=False).head(TOP_RECORD_LIMIT).copy()
    best["rank"] = range(1, len(best) + 1)
    best["entity_type"] = entity_type
    best["entity_id"] = best[group_col].astype(str)
    best["value"] = (best["fwd_rate"] * 100).round(1)
    best["unit"] = "% 快進率"
    best["secondary_value"] = best["total_plays"].astype(float)
    best["secondary_unit"] = "次總播放"
    best = safe_rename(best, name_col, artist_col)
    return best


def _shuffle_peak(event_frame):
    """Shuffle 率最高日。"""
    if event_frame.empty or "shuffle" not in event_frame.columns:
        return pd.DataFrame()
    daily = (
        event_frame.groupby("ts_date")
        .agg(
            total_plays=("play_id", "count"),
            shuffle_plays=("shuffle", "sum"),
        )
        .reset_index()
    )
    daily = daily[daily["total_plays"] >= 20]
    if daily.empty:
        return pd.DataFrame()
    daily["shuffle_rate"] = daily["shuffle_plays"] / daily["total_plays"]
    best = daily.sort_values("shuffle_rate", ascending=False).head(TOP_RECORD_LIMIT)
    rows = []
    for _, row in best.iterrows():
        rows.append(
            {
                "rank": len(rows) + 1,
                "name": str(row["ts_date"]),
                "value": round(float(row["shuffle_rate"]) * 100, 1),
                "unit": "% Shuffle",
                "date": str(row["ts_date"]),
                "secondary_value": float(row["shuffle_plays"]),
                "secondary_unit": "次隨機播放",
            }
        )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _platform_reign(event_frame):
    """平台播放排名。"""
    if event_frame.empty or "platform" not in event_frame.columns:
        return pd.DataFrame()
    platform = event_frame.groupby("platform").size().reset_index(name="plays")
    platform = platform.sort_values("plays", ascending=False)
    if platform.empty:
        return pd.DataFrame()
    total = platform["plays"].sum()
    platform["rank"] = range(1, len(platform) + 1)
    platform["name"] = platform["platform"]
    platform["value"] = platform["plays"].astype(float)
    platform["unit"] = "次"
    platform["share_pct"] = (platform["plays"] / total * 100).round(1)
    return platform


def _platform_switch_day(event_frame):
    """平台切換最頻繁的日期。"""
    if event_frame.empty or "platform" not in event_frame.columns:
        return pd.DataFrame()
    df_sorted = event_frame.sort_values(["ts_date", "ts"])
    df_sorted["_prev_platform"] = df_sorted.groupby("ts_date")["platform"].shift(1)
    df_sorted["_switched"] = (
        (df_sorted["platform"] != df_sorted["_prev_platform"]) & df_sorted["_prev_platform"].notna()
    ).astype(int)
    switches = df_sorted.groupby("ts_date")["_switched"].sum().reset_index(name="switch_count")
    best = switches.sort_values("switch_count", ascending=False).head(TOP_RECORD_LIMIT)
    rows = []
    for _, row in best.iterrows():
        rows.append(
            {
                "rank": len(rows) + 1,
                "name": str(row["ts_date"]),
                "value": float(row["switch_count"]),
                "unit": "次平台切換",
                "date": str(row["ts_date"]),
            }
        )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _playback_milestones(event_frame):
    """播放里程碑。"""
    if event_frame.empty:
        return pd.DataFrame()
    df_sorted = event_frame.sort_values("ts").copy()
    milestones = []
    for target in [1000, 5000, 10000, 50000]:
        if target > len(df_sorted):
            break
        row = df_sorted.iloc[target - 1]
        milestones.append(
            {
                "rank": len(milestones) + 1,
                "name": str(row.get("track_name", "")),
                "artist_name": str(row.get("artist_name", "")),
                "value": float(target),
                "unit": "次播放里程碑",
                "date": str(row["ts_date"]),
                "caption": f"第 {target} 次有效播放",
            }
        )
    return pd.DataFrame(milestones) if milestones else pd.DataFrame()


def compute_behavior_records(
    records: dict,
    event_frame: pd.DataFrame,
    track_frame: pd.DataFrame,
    album_frame: pd.DataFrame,
    artist_frame: pd.DataFrame,
):
    """Populate behavior records."""
    for entity_type, frame in [
        ("track", track_frame),
        ("album", album_frame),
        ("artist", artist_frame),
    ]:
        if frame.empty:
            records[f"behavior_skip_storm_{entity_type}"] = pd.DataFrame()
        else:
            gcol, ncol, acol = _group_col_for(frame, entity_type)
            records[f"behavior_skip_storm_{entity_type}"] = _skip_storm(
                frame, gcol, ncol, acol, entity_type
            )

    records["behavior_shuffle_peak"] = _shuffle_peak(event_frame)
    records["behavior_platform_reign"] = _platform_reign(event_frame)
    records["behavior_platform_switch_day"] = _platform_switch_day(event_frame)
    records["behavior_playback_milestones"] = _playback_milestones(event_frame)
