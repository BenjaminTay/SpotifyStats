"""Market overview Billboard record families."""

import pandas as pd


def compute_market_records(records, weekly, weekly_album=None, weekly_artist=None):
    """Populate market records: week total plays, strongest week, closest/largest #1 vs #2, new entry ratio."""

    # ── 14. Weekly Total Plays Ranking (大盘) ────────────────────────────
    if weekly_album is not None and weekly_artist is not None:
        week_total_plays = (
            weekly.groupby("billboard_week")
            .agg(
                total_plays=("play_count", "sum"),
                tracks_count=("track_id", "nunique"),
            )
            .reset_index()
        )
        week_no1 = weekly[weekly["rank"] == 1][
            ["billboard_week", "track_id", "track_name", "artist_name", "play_count"]
        ].copy()
        week_no1.columns = [
            "billboard_week",
            "no1_track_id",
            "no1_track",
            "no1_track_artist",
            "no1_track_plays",
        ]
        week_total_plays = week_total_plays.merge(week_no1, on="billboard_week", how="left")
        week_album_no1 = weekly_album[weekly_album["rank"] == 1][
            ["billboard_week", "album_name", "artist_name", "play_count"]
        ].copy()
        week_album_no1.columns = [
            "billboard_week",
            "no1_album",
            "no1_album_artist",
            "no1_album_plays",
        ]
        week_total_plays = week_total_plays.merge(week_album_no1, on="billboard_week", how="left")
        week_artist_no1 = weekly_artist[weekly_artist["rank"] == 1][
            ["billboard_week", "artist_name", "play_count"]
        ].copy()
        week_artist_no1.columns = [
            "billboard_week",
            "no1_chart_artist",
            "no1_chart_artist_plays",
        ]
        week_total_plays = week_total_plays.merge(week_artist_no1, on="billboard_week", how="left")
        week_total_plays = week_total_plays.sort_values("total_plays", ascending=False)
        week_total_plays.index = week_total_plays.index + 1
        week_total_plays["billboard_week"] = week_total_plays["billboard_week"].astype(str)
        records["week_total_plays"] = week_total_plays
    else:
        records["week_total_plays"] = pd.DataFrame()

    # ── 24. Strongest Week (最强单周) ────────────────────────────────────
    if not records["week_total_plays"].empty:
        sw = records["week_total_plays"].iloc[0]
        records["strongest_week"] = {
            "week": str(sw["billboard_week"]),
            "total_plays": int(sw["total_plays"]),
            "tracks_count": int(sw["tracks_count"]),
        }
    else:
        records["strongest_week"] = {}

    # ── 29. Closest / Largest #1 vs #2 (最激烈/最悬殊竞争) ──────────────
    no1_data = weekly[weekly["rank"] == 1][
        ["billboard_week", "track_name", "artist_name", "play_count"]
    ].copy()
    no1_data.columns = ["billboard_week", "no1_track", "no1_artist", "no1_plays"]
    no2_data = weekly[weekly["rank"] == 2][
        ["billboard_week", "track_name", "artist_name", "play_count"]
    ].copy()
    no2_data.columns = ["billboard_week", "no2_track", "no2_artist", "no2_plays"]
    gaps = no1_data.merge(no2_data, on="billboard_week")
    if not gaps.empty:
        gaps["play_gap"] = gaps["no1_plays"] - gaps["no2_plays"]
        gaps["gap_pct"] = (gaps["play_gap"] / gaps["no2_plays"] * 100).round(1)
        total_plays_by_week = weekly.groupby("billboard_week")["play_count"].sum().reset_index()
        total_plays_by_week.columns = ["billboard_week", "week_total"]
        gaps = gaps.merge(total_plays_by_week, on="billboard_week", how="left")
        gaps["week_total"] = gaps["week_total"].fillna(0).astype(int)
        closest = gaps.sort_values(["play_gap", "week_total"], ascending=[True, False]).iloc[0]
        records["closest_no1_vs_no2"] = {
            "week": str(closest["billboard_week"]),
            "no1_track": closest["no1_track"],
            "no1_artist": closest["no1_artist"],
            "no1_plays": int(closest["no1_plays"]),
            "no2_track": closest["no2_track"],
            "no2_artist": closest["no2_artist"],
            "no2_plays": int(closest["no2_plays"]),
            "gap": int(closest["play_gap"]),
            "gap_pct": float(closest["gap_pct"]),
        }
        largest = gaps.sort_values(["play_gap", "week_total"], ascending=[False, False]).iloc[0]
        records["largest_no1_vs_no2"] = {
            "week": str(largest["billboard_week"]),
            "no1_track": largest["no1_track"],
            "no1_artist": largest["no1_artist"],
            "no1_plays": int(largest["no1_plays"]),
            "no2_track": largest["no2_track"],
            "no2_artist": largest["no2_artist"],
            "no2_plays": int(largest["no2_plays"]),
            "gap": int(largest["play_gap"]),
            "gap_pct": float(largest["gap_pct"]),
        }
    else:
        records["closest_no1_vs_no2"] = {}
        records["largest_no1_vs_no2"] = {}

    # ── 30. New Entry Ratio (新歌活跃度) ─────────────────────────────────
    first_appear = weekly.sort_values("billboard_week").groupby("track_id").first().reset_index()
    first_appear["is_new"] = 1
    weekly_with_flag = weekly.merge(
        first_appear[["track_id", "billboard_week", "is_new"]],
        on=["track_id", "billboard_week"],
        how="left",
    )
    weekly_with_flag["is_new"] = weekly_with_flag["is_new"].fillna(0).astype(int)
    new_ratio = (
        weekly_with_flag.groupby("billboard_week")
        .agg(
            总歌曲数=("track_id", "nunique"),
            新入榜歌曲数=("is_new", "sum"),
        )
        .reset_index()
    )
    new_ratio["新歌占比"] = (new_ratio["新入榜歌曲数"] / new_ratio["总歌曲数"] * 100).round(1)
    week_totals = weekly.groupby("billboard_week")["play_count"].sum().reset_index()
    week_totals.columns = ["billboard_week", "大盘播放"]
    new_ratio = new_ratio.merge(week_totals, on="billboard_week", how="left")
    new_ratio["大盘播放"] = new_ratio["大盘播放"].fillna(0).astype(int)
    records["new_entry_ratio"] = new_ratio.sort_values(
        ["新歌占比", "大盘播放"], ascending=[False, False]
    )
