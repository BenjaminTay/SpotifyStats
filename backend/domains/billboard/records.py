"""Billboard records computation."""

import pandas as pd

from backend.core.db import get_db
from backend.core.json_helpers import df_to_json as _df_to_json
from backend.core.json_helpers import py_val as _py_val
from backend.domains.billboard.chart_compute import (
    compute_power_scores,
)
from backend.domains.billboard.data_loader import (
    _load_album_metadata,
)
from backend.domains.billboard.version_merge import (
    _normalize_album_column,
)


def compute_records(
    weekly,
    track_summary,
    top_n,
    weekly_album=None,
    weekly_artist=None,
    track_power_scores=None,
    album_power_scores=None,
    artist_power_scores=None,
):
    """Compute all-time Billboard records from weekly rankings.

    Returns a dict of record DataFrames and highlight values for the 榜单记录 tab.
    """
    records = {}

    # ── 1. Most simultaneous chart entries by artist (full chart) ──────
    artist_weekly = (
        weekly.groupby(["billboard_week", "artist_name"]).size().reset_index(name="track_count")
    )
    if not artist_weekly.empty:
        best_full = artist_weekly.sort_values("track_count", ascending=False).iloc[0]
        records["artist_simul"] = {
            "artist": best_full["artist_name"],
            "week": best_full["billboard_week"],
            "count": int(best_full["track_count"]),
        }
        records["artist_simul_list"] = artist_weekly.sort_values(
            "track_count", ascending=False
        ).head(15)

    # ── 3. Most #1 songs by artist ─────────────────────────────────────
    no1_tracks = weekly[weekly["rank"] == 1][["track_id", "artist_name"]].drop_duplicates()
    artist_no1 = (
        no1_tracks.groupby("artist_name")
        .size()
        .sort_values(ascending=False)
        .reset_index(name="冠单数")
    )
    records["artist_most_no1"] = artist_no1.head(15)

    # 单曲冠军周数：每位艺人所有#1单曲的冠周总和
    track_no1_weeks = (
        track_summary.groupby("artist_name")["weeks_at_no1"].sum().reset_index(name="单曲冠军周数")
    )
    records["artist_most_no1"] = records["artist_most_no1"].merge(
        track_no1_weeks, on="artist_name", how="left"
    )
    records["artist_most_no1"]["单曲冠军周数"] = (
        records["artist_most_no1"]["单曲冠军周数"].fillna(0).astype(int)
    )

    # Also count #1 albums per artist
    if weekly_album is not None:
        album_no1_cnt = (
            weekly_album[weekly_album["rank"] == 1]
            .groupby("artist_name")["album_name"]
            .nunique()
            .reset_index(name="冠军专辑数")
        )
        records["artist_most_no1"] = records["artist_most_no1"].merge(
            album_no1_cnt, on="artist_name", how="left"
        )
        records["artist_most_no1"]["冠军专辑数"] = (
            records["artist_most_no1"]["冠军专辑数"].fillna(0).astype(int)
        )
        # 专辑冠军周数：每位艺人所有#1专辑的冠周总和
        album_no1_weeks = (
            weekly_album[weekly_album["rank"] == 1]
            .groupby("artist_name")["billboard_week"]
            .nunique()
            .reset_index(name="专辑冠军周数")
        )
        records["artist_most_no1"] = records["artist_most_no1"].merge(
            album_no1_weeks, on="artist_name", how="left"
        )
        records["artist_most_no1"]["专辑冠军周数"] = (
            records["artist_most_no1"]["专辑冠军周数"].fillna(0).astype(int)
        )
    else:
        records["artist_most_no1"]["冠军专辑数"] = 0
        records["artist_most_no1"]["专辑冠军周数"] = 0

    # ── 4. Return to #1 ────────────────────────────────────────────────
    no1_weeks = (
        weekly[weekly["rank"] == 1][["track_id", "track_name", "artist_name", "billboard_week"]]
        .drop_duplicates()
        .sort_values(["track_id", "billboard_week"])
    )
    returns = []
    for tid, grp in no1_weeks.groupby("track_id"):
        if len(grp) >= 2:
            wks = grp["billboard_week"].tolist()
            for i in range(1, len(wks)):
                gap = (wks[i] - wks[i - 1]).days
                if gap > 8:  # More than one week apart → returned to #1
                    returns.append(
                        {
                            "track_id": tid,
                            "track_name": grp.iloc[i]["track_name"],
                            "artist_name": grp.iloc[i]["artist_name"],
                            "首次冠单": wks[i - 1],
                            "回冠日期": wks[i],
                            "间隔周数": gap // 7,
                        }
                    )
    records["return_to_no1"] = (
        pd.DataFrame(returns).sort_values("间隔周数", ascending=False)
        if returns
        else pd.DataFrame()
    )

    # ── Album: Return to #1 ────────────────────────────────────────────
    if weekly_album is not None:
        album_no1_weeks = (
            weekly_album[weekly_album["rank"] == 1][["album_name", "artist_name", "billboard_week"]]
            .drop_duplicates()
            .sort_values(["album_name", "artist_name", "billboard_week"])
        )
        album_returns = []
        for (aname, aname_artist), grp in album_no1_weeks.groupby(["album_name", "artist_name"]):
            if len(grp) >= 2:
                wks = grp["billboard_week"].tolist()
                for i in range(1, len(wks)):
                    gap = (wks[i] - wks[i - 1]).days
                    if gap > 8:
                        album_returns.append(
                            {
                                "album_name": aname,
                                "artist_name": aname_artist,
                                "首次冠专": wks[i - 1],
                                "回冠日期": wks[i],
                                "间隔周数": gap // 7,
                            }
                        )
        records["return_to_no1_album"] = (
            pd.DataFrame(album_returns).sort_values("间隔周数", ascending=False)
            if album_returns
            else pd.DataFrame()
        )
    else:
        records["return_to_no1_album"] = pd.DataFrame()

    # ── 5. Debut at #1 ─────────────────────────────────────────────────
    debut = track_summary[
        (track_summary["peak_position"] == 1)
        & (track_summary["first_week"] == track_summary["first_peak_week"])
    ].copy()
    records["debut_no1"] = debut.sort_values("first_week")[
        ["track_id", "track_name", "artist_name", "first_week", "weeks_at_no1", "weeks_on_chart"]
    ]
    # Album version
    if weekly_album is not None:
        album_first = (
            weekly_album.sort_values("billboard_week")
            .groupby(["album_name", "artist_name"])
            .first()
            .reset_index()
        )
        album_debut_no1 = album_first[album_first["rank"] == 1][
            ["album_name", "artist_name", "billboard_week"]
        ].copy()
        album_weeks = (
            weekly_album.groupby(["album_name", "artist_name"])
            .agg(weeks_on_chart=("billboard_week", "nunique"))
            .reset_index()
        )
        album_no1_week_cnt = (
            weekly_album[weekly_album["rank"] == 1]
            .groupby(["album_name", "artist_name"])["billboard_week"]
            .nunique()
            .reset_index(name="weeks_at_no1")
        )
        album_debut_no1 = album_debut_no1.merge(album_weeks, on=["album_name", "artist_name"])
        album_debut_no1 = album_debut_no1.merge(
            album_no1_week_cnt, on=["album_name", "artist_name"], how="left"
        )
        album_debut_no1["weeks_at_no1"] = album_debut_no1["weeks_at_no1"].fillna(0).astype(int)
        records["debut_no1_album"] = album_debut_no1.sort_values("billboard_week").rename(
            columns={"billboard_week": "first_week"}
        )[["album_name", "artist_name", "first_week", "weeks_at_no1", "weeks_on_chart"]]
    else:
        records["debut_no1_album"] = pd.DataFrame()

    # ── 6. Longest charting songs ──────────────────────────────────────
    records["longest_charting"] = track_summary.sort_values("weeks_on_chart", ascending=False).head(
        20
    )[["track_id", "track_name", "artist_name", "weeks_on_chart", "peak_position", "weeks_at_no1"]]
    # Album version
    if weekly_album is not None:
        album_summary = (
            weekly_album.groupby(["album_name", "artist_name"])
            .agg(
                peak_position=("rank", "min"),
                weeks_on_chart=("billboard_week", "nunique"),
                first_week=("billboard_week", "min"),
                last_week=("billboard_week", "max"),
            )
            .reset_index()
        )
        album_no1_wks = (
            weekly_album[weekly_album["rank"] == 1]
            .groupby(["album_name", "artist_name"])["billboard_week"]
            .nunique()
            .reset_index(name="weeks_at_no1")
        )
        album_summary = album_summary.merge(
            album_no1_wks, on=["album_name", "artist_name"], how="left"
        )
        album_summary["weeks_at_no1"] = album_summary["weeks_at_no1"].fillna(0).astype(int)
        records["longest_charting_album"] = album_summary.sort_values(
            "weeks_on_chart", ascending=False
        ).head(20)[["album_name", "artist_name", "weeks_on_chart", "peak_position", "weeks_at_no1"]]
    else:
        records["longest_charting_album"] = pd.DataFrame()

    # ── 7. Longest charting without Top 5 ──────────────────────────────
    no_top5 = (
        track_summary[track_summary["peak_position"] > 5]
        .sort_values("weeks_on_chart", ascending=False)
        .head(20)[["track_id", "track_name", "artist_name", "weeks_on_chart", "peak_position"]]
    )
    records["longest_no_top5"] = no_top5
    # Album version
    if weekly_album is not None:
        no_top5_album = (
            album_summary[album_summary["peak_position"] > 5]
            .sort_values("weeks_on_chart", ascending=False)
            .head(20)[["album_name", "artist_name", "weeks_on_chart", "peak_position"]]
        )
        records["longest_no_top5_album"] = no_top5_album
    else:
        records["longest_no_top5_album"] = pd.DataFrame()

    # ── 8. Longest consecutive streak ─────────────────────────────────
    streaks = []
    for tid, grp in weekly.sort_values(["track_id", "billboard_week"]).groupby("track_id"):
        wks = grp["billboard_week"].tolist()
        max_run = 1
        cur_run = 1
        run_start = wks[0]
        run_end = wks[0]
        best_start = wks[0]
        best_end = wks[0]

        for i in range(1, len(wks)):
            if (wks[i] - wks[i - 1]).days <= 8:
                cur_run += 1
                run_end = wks[i]
            else:
                if cur_run > max_run:
                    max_run = cur_run
                    best_start = run_start
                    best_end = run_end
                cur_run = 1
                run_start = wks[i]
                run_end = wks[i]

        if cur_run > max_run:
            max_run = cur_run
            best_start = run_start
            best_end = run_end

        streaks.append(
            {
                "track_id": tid,
                "track_name": grp.iloc[0]["track_name"],
                "artist_name": grp.iloc[0]["artist_name"],
                "连续周数": max_run,
                "起始周": best_start,
                "结束周": best_end,
            }
        )
    records["longest_streak"] = (
        pd.DataFrame(streaks).sort_values("连续周数", ascending=False).head(20)
    )
    # Album version
    if weekly_album is not None:
        album_streaks = []
        for (aname, aname_artist), grp in weekly_album.sort_values(
            ["album_name", "artist_name", "billboard_week"]
        ).groupby(["album_name", "artist_name"]):
            wks = grp["billboard_week"].tolist()
            max_run = 1
            cur_run = 1
            run_start = wks[0]
            run_end = wks[0]
            best_start = wks[0]
            best_end = wks[0]
            for i in range(1, len(wks)):
                if (wks[i] - wks[i - 1]).days <= 8:
                    cur_run += 1
                    run_end = wks[i]
                else:
                    if cur_run > max_run:
                        max_run = cur_run
                        best_start = run_start
                        best_end = run_end
                    cur_run = 1
                    run_start = wks[i]
                    run_end = wks[i]
            if cur_run > max_run:
                max_run = cur_run
                best_start = run_start
                best_end = run_end
            album_streaks.append(
                {
                    "album_name": aname,
                    "artist_name": aname_artist,
                    "连续周数": max_run,
                    "起始周": best_start,
                    "结束周": best_end,
                }
            )
        records["longest_streak_album"] = (
            pd.DataFrame(album_streaks).sort_values("连续周数", ascending=False).head(20)
        )
    else:
        records["longest_streak_album"] = pd.DataFrame()

    # ── 9. Biggest Jump / Drop ─────────────────────────────────────────
    changes = []
    for tid, grp in weekly.sort_values(["track_id", "billboard_week"]).groupby("track_id"):
        grp = grp.sort_values("billboard_week")
        rows = grp.to_dict("records")
        for i in range(1, len(rows)):
            prev, curr = rows[i - 1], rows[i]
            if (curr["billboard_week"] - prev["billboard_week"]).days <= 8:
                change = prev["rank"] - curr["rank"]  # positive = rise
                changes.append(
                    {
                        "track_id": tid,
                        "track_name": curr["track_name"],
                        "artist_name": curr["artist_name"],
                        "日期": curr["billboard_week"],
                        "上周排名": prev["rank"],
                        "本周排名": curr["rank"],
                        "变化": change,
                    }
                )
    if changes:
        ch_df = pd.DataFrame(changes)
        records["biggest_jump"] = ch_df.nlargest(15, "变化")
        records["biggest_drop"] = ch_df.nsmallest(15, "变化")
    else:
        records["biggest_jump"] = pd.DataFrame()
        records["biggest_drop"] = pd.DataFrame()

    # ── 10. Same album most simultaneous entries ───────────────────────
    _weekly_norm = _normalize_album_column(weekly.copy())
    album_weekly = (
        _weekly_norm.groupby(["billboard_week", "artist_name", "album_name"])
        .size()
        .reset_index(name="track_count")
    )
    if not album_weekly.empty:
        best_alb = album_weekly.sort_values("track_count", ascending=False).iloc[0]
        records["album_simul"] = {
            "album": best_alb["album_name"],
            "artist": best_alb["artist_name"],
            "week": best_alb["billboard_week"],
            "count": int(best_alb["track_count"]),
        }
        records["album_simul_list"] = album_weekly.sort_values("track_count", ascending=False).head(
            15
        )

    # ── 11. All-Time Greatest (Power Score) ──────────────────────────────
    if track_power_scores is not None:
        power_df = track_power_scores
    else:
        power_df = compute_power_scores(weekly, top_n)
    records["all_time_greatest"] = power_df.head(20)[
        [
            "track_id",
            "track_name",
            "artist_name",
            "peak_position",
            "weeks_on_chart",
            "weeks_at_no1",
            "power_score",
        ]
    ].rename(columns={"power_score": "走势评分"})

    # ── 12. Year-End #1 (per-year Power Score) ──────────────────────────
    wy = weekly.copy()
    wy["year"] = pd.to_datetime(wy["billboard_week"]).dt.year
    ye_results = []
    for year, year_df in wy.groupby("year"):
        year_power = compute_power_scores(year_df, top_n)
        if not year_power.empty:
            top = year_power.iloc[0]
            ye_results.append(
                {
                    "year": int(year),
                    "track_id": top["track_id"],
                    "track_name": top["track_name"],
                    "artist_name": top["artist_name"],
                    "peak": top["peak_position"],
                    "weeks_on_chart": top["weeks_on_chart"],
                }
            )
    records["year_end_no1"] = (
        pd.DataFrame(ye_results).sort_values("year", ascending=False)
        if ye_results
        else pd.DataFrame()
    )

    # ── 13. Double Debut #1 (双空冠) ─────────────────────────────────────
    if weekly_album is not None:
        first_track_appear = (
            weekly.sort_values("billboard_week").groupby("track_id").first().reset_index()
        )
        debut_tracks = first_track_appear[first_track_appear["rank"] == 1][
            ["track_id", "track_name", "artist_name", "billboard_week"]
        ].copy()
        debut_tracks.columns = ["debut_track_id", "debut_track", "debut_artist", "debut_week"]

        first_album_appear = (
            weekly_album.sort_values("billboard_week")
            .groupby(["album_name", "artist_name"])
            .first()
            .reset_index()
        )
        debut_albums = first_album_appear[first_album_appear["rank"] == 1][
            ["album_name", "artist_name", "billboard_week"]
        ].copy()
        debut_albums.columns = ["debut_album", "debut_artist", "debut_week"]

        double_debut = debut_tracks.merge(
            debut_albums, on=["debut_artist", "debut_week"], how="inner"
        ).sort_values("debut_week", ascending=False)
        if not double_debut.empty:
            double_debut["debut_week"] = double_debut["debut_week"].astype(str)
        records["double_debut"] = double_debut
    else:
        records["double_debut"] = pd.DataFrame()

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

    # ── 15. Self-Replacement at #1 (冠军传承) ────────────────────────────
    no1_all = (
        weekly[weekly["rank"] == 1][["billboard_week", "track_id", "track_name", "artist_name"]]
        .drop_duplicates()
        .sort_values("billboard_week")
    )
    replacements = []
    for i in range(1, len(no1_all)):
        prev = no1_all.iloc[i - 1]
        curr = no1_all.iloc[i]
        gap = (curr["billboard_week"] - prev["billboard_week"]).days
        if (
            gap <= 8
            and prev["artist_name"] == curr["artist_name"]
            and prev["track_id"] != curr["track_id"]
        ):
            replacements.append(
                {
                    "周次": curr["billboard_week"],
                    "艺人": curr["artist_name"],
                    "前冠单_id": prev["track_id"],
                    "前冠单": prev["track_name"],
                    "新冠单_id": curr["track_id"],
                    "新冠单": curr["track_name"],
                }
            )
    records["self_replacement_no1"] = (
        pd.DataFrame(replacements).sort_values("周次", ascending=False)
        if replacements
        else pd.DataFrame()
    )
    # Album version
    if weekly_album is not None:
        alb_no1_all = (
            weekly_album[weekly_album["rank"] == 1][["billboard_week", "album_name", "artist_name"]]
            .drop_duplicates()
            .sort_values("billboard_week")
        )
        alb_replacements = []
        for i in range(1, len(alb_no1_all)):
            prev = alb_no1_all.iloc[i - 1]
            curr = alb_no1_all.iloc[i]
            gap = (curr["billboard_week"] - prev["billboard_week"]).days
            if (
                gap <= 8
                and prev["artist_name"] == curr["artist_name"]
                and prev["album_name"] != curr["album_name"]
            ):
                alb_replacements.append(
                    {
                        "周次": curr["billboard_week"],
                        "艺人": curr["artist_name"],
                        "前冠专": prev["album_name"],
                        "新冠专": curr["album_name"],
                    }
                )
        records["self_replacement_no1_album"] = (
            pd.DataFrame(alb_replacements).sort_values("周次", ascending=False)
            if alb_replacements
            else pd.DataFrame()
        )
    else:
        records["self_replacement_no1_album"] = pd.DataFrame()

    # ── 16. Blocker King — #1 that blocked most #2 challengers (阻挡王) ─
    no1_weeks_all = weekly[weekly["rank"] == 1][["track_id", "billboard_week"]].drop_duplicates()
    no2_at_no1 = weekly[weekly["rank"] == 2][
        ["track_id", "track_name", "artist_name", "billboard_week"]
    ].drop_duplicates()
    if not no1_weeks_all.empty and not no2_at_no1.empty:
        merged_block = no1_weeks_all.merge(
            no2_at_no1, on="billboard_week", suffixes=("_no1", "_no2")
        )
        # Only count blocked songs that peaked at #2 (never reached #1)
        track_peaks = track_summary.set_index("track_id")["peak_position"].to_dict()
        merged_block["_peak_no2"] = merged_block["track_id_no2"].map(track_peaks)
        merged_block_true = merged_block[merged_block["_peak_no2"] == 2]
        blocker = (
            merged_block_true.groupby("track_id_no1")
            .agg(阻挡数=("track_id_no2", "nunique"))
            .reset_index()
            .sort_values("阻挡数", ascending=False)
        )
        blocker = blocker.merge(
            track_summary[["track_id", "track_name", "artist_name"]],
            left_on="track_id_no1",
            right_on="track_id",
            how="left",
        )
        records["blocker_king"] = blocker.head(20)[
            ["track_id", "track_name", "artist_name", "阻挡数"]
        ]
        # Merge power scores for secondary sort
        if track_power_scores is not None:
            records["blocker_king"] = records["blocker_king"].merge(
                track_power_scores[["track_id", "power_score"]].rename(
                    columns={"power_score": "走势评分"}
                ),
                on="track_id",
                how="left",
            )
            records["blocker_king"]["走势评分"] = (
                records["blocker_king"]["走势评分"].fillna(0).astype(int)
            )
        else:
            records["blocker_king"]["走势评分"] = 0
        # Blocked tracks detail: for each #1 track, list the #2 tracks it blocked
        blocked_detail = (
            merged_block_true.groupby("track_id_no1")
            .apply(
                lambda g: [
                    {
                        "track_id": int(r["track_id_no2"]),
                        "track_name": str(r["track_name"]),
                        "artist_name": str(r["artist_name"]),
                    }
                    for r in g.drop_duplicates(subset=["track_id_no2"]).to_dict("records")
                ],
                include_groups=False,
            )
            .to_dict()
        )
        records["blocked_tracks_map"] = blocked_detail
    else:
        records["blocker_king"] = pd.DataFrame()
        records["blocked_tracks_map"] = {}

    # ── 16b. Album Blocker King — #1 album that blocked most #2 challengers ─
    if weekly_album is not None:
        alb_no1_weeks_all = weekly_album[weekly_album["rank"] == 1][
            ["album_name", "artist_name", "billboard_week"]
        ].drop_duplicates()
        alb_no2_at_no1 = weekly_album[weekly_album["rank"] == 2][
            ["album_name", "artist_name", "billboard_week"]
        ].drop_duplicates()
        if not alb_no1_weeks_all.empty and not alb_no2_at_no1.empty:
            alb_merged = alb_no1_weeks_all.merge(
                alb_no2_at_no1, on="billboard_week", suffixes=("_no1", "_no2")
            )
            # Only count blocked albums that peaked at #2
            if weekly_album is not None:
                album_peak_map = (
                    weekly_album.groupby(["album_name", "artist_name"])["rank"].min().to_dict()
                )
                alb_merged["_peak_no2"] = alb_merged.apply(
                    lambda r: album_peak_map.get((r["album_name_no2"], r["artist_name_no2"]), 99),
                    axis=1,
                )
            else:
                alb_merged["_peak_no2"] = 99
            alb_merged_true = alb_merged[alb_merged["_peak_no2"] == 2]
            if not alb_merged_true.empty:
                alb_blocker = (
                    alb_merged_true.groupby(["album_name_no1", "artist_name_no1"])
                    .agg(阻挡数=("album_name_no2", "nunique"))
                    .reset_index()
                    .sort_values("阻挡数", ascending=False)
                )
                records["blocker_king_album"] = alb_blocker.head(20).rename(
                    columns={
                        "album_name_no1": "album_name",
                        "artist_name_no1": "artist_name",
                    }
                )[["album_name", "artist_name", "阻挡数"]]
                # Merge album power scores for secondary sort
                if album_power_scores is not None:
                    records["blocker_king_album"] = records["blocker_king_album"].merge(
                        album_power_scores[["album_name", "artist_name", "power_score"]].rename(
                            columns={"power_score": "走势评分"}
                        ),
                        on=["album_name", "artist_name"],
                        how="left",
                    )
                    records["blocker_king_album"]["走势评分"] = (
                        records["blocker_king_album"]["走势评分"].fillna(0).astype(int)
                    )
                else:
                    records["blocker_king_album"]["走势评分"] = 0
                # Blocked albums detail (string key: "album||artist")
                alb_blocked_detail = {}
                for (aname, aname_artist), grp in alb_merged_true.groupby(
                    ["album_name_no1", "artist_name_no1"]
                ):
                    alb_blocked_detail[f"{aname}||{aname_artist}"] = [
                        {
                            "album_name": str(r["album_name_no2"]),
                            "artist_name": str(r["artist_name_no2"]),
                        }
                        for r in grp.drop_duplicates(
                            subset=["album_name_no2", "artist_name_no2"]
                        ).to_dict("records")
                    ]
                records["blocked_albums_map"] = alb_blocked_detail
            else:
                records["blocker_king_album"] = pd.DataFrame()
                records["blocked_albums_map"] = {}
        else:
            records["blocker_king_album"] = pd.DataFrame()
            records["blocked_albums_map"] = {}
    else:
        records["blocker_king_album"] = pd.DataFrame()
        records["blocked_albums_map"] = {}

    # ── 17. Longest / Fastest Climb to #1 (登顶路) ─────────────────────
    to_no1 = track_summary[
        (track_summary["peak_position"] == 1) & (track_summary["first_peak_week"].notna())
    ].copy()
    if not to_no1.empty:
        to_no1["登顶周数"] = to_no1.apply(
            lambda r: max(0, (r["first_peak_week"] - r["first_week"]).days // 7), axis=1
        )
        records["longest_to_no1"] = to_no1.nlargest(20, "登顶周数")[
            ["track_id", "track_name", "artist_name", "first_week", "first_peak_week", "登顶周数"]
        ]
        records["fastest_to_no1"] = to_no1[to_no1["登顶周数"] > 0].nsmallest(20, "登顶周数")[
            ["track_id", "track_name", "artist_name", "first_week", "first_peak_week", "登顶周数"]
        ]
    else:
        records["longest_to_no1"] = pd.DataFrame()
        records["fastest_to_no1"] = pd.DataFrame()

    # ── 18. Most Weeks at #2 Without #1 (万年老二) ──────────────────────
    at_no2 = (
        weekly[weekly["rank"] == 2]
        .groupby("track_id")
        .agg(weeks_at_no2=("billboard_week", "nunique"))
        .reset_index()
    )
    if not at_no2.empty:
        no2_with_peak = at_no2.merge(
            track_summary[["track_id", "track_name", "artist_name", "peak_position"]], on="track_id"
        )
        no2_no_no1 = (
            no2_with_peak[no2_with_peak["peak_position"] > 1]
            .sort_values("weeks_at_no2", ascending=False)
            .head(20)
        )
        records["most_weeks_no2_no_no1"] = no2_no_no1[
            ["track_id", "track_name", "artist_name", "peak_position", "weeks_at_no2"]
        ]
    else:
        records["most_weeks_no2_no_no1"] = pd.DataFrame()
    # Album version
    if weekly_album is not None:
        alb_at_no2 = (
            weekly_album[weekly_album["rank"] == 2]
            .groupby(["album_name", "artist_name"])
            .agg(weeks_at_no2=("billboard_week", "nunique"))
            .reset_index()
        )
        alb_no2_with_peak = alb_at_no2.merge(
            album_summary[["album_name", "artist_name", "peak_position"]],
            on=["album_name", "artist_name"],
        )
        alb_no2_no_no1 = (
            alb_no2_with_peak[alb_no2_with_peak["peak_position"] > 1]
            .sort_values("weeks_at_no2", ascending=False)
            .head(20)
        )
        records["most_weeks_no2_no_no1_album"] = alb_no2_no_no1[
            ["album_name", "artist_name", "peak_position", "weeks_at_no2"]
        ]
    else:
        records["most_weeks_no2_no_no1_album"] = pd.DataFrame()

    # ── 19. Most Re-entries (回榜王) ─────────────────────────────────────
    reentries = []
    for tid, grp in weekly.sort_values(["track_id", "billboard_week"]).groupby("track_id"):
        wks = grp["billboard_week"].tolist()
        count = 0
        for i in range(1, len(wks)):
            if (wks[i] - wks[i - 1]).days > 8:
                count += 1
        if count > 0:
            reentries.append(
                {
                    "track_id": tid,
                    "track_name": grp.iloc[0]["track_name"],
                    "artist_name": grp.iloc[0]["artist_name"],
                    "回榜次数": count,
                    "在榜周数": len(wks),
                }
            )
    records["most_reentries"] = (
        pd.DataFrame(reentries).sort_values("回榜次数", ascending=False).head(20)
        if reentries
        else pd.DataFrame()
    )
    # Album version
    if weekly_album is not None:
        album_reentries = []
        for (aname, aname_artist), grp in weekly_album.sort_values(
            ["album_name", "artist_name", "billboard_week"]
        ).groupby(["album_name", "artist_name"]):
            wks = grp["billboard_week"].tolist()
            count = 0
            for i in range(1, len(wks)):
                if (wks[i] - wks[i - 1]).days > 8:
                    count += 1
            if count > 0:
                album_reentries.append(
                    {
                        "album_name": aname,
                        "artist_name": aname_artist,
                        "回榜次数": count,
                        "在榜周数": len(wks),
                    }
                )
        records["most_reentries_album"] = (
            pd.DataFrame(album_reentries).sort_values("回榜次数", ascending=False).head(20)
            if album_reentries
            else pd.DataFrame()
        )
    else:
        records["most_reentries_album"] = pd.DataFrame()

    # ── 20. Longest Consecutive Same Rank (稳如磐石) ────────────────────
    same_rank_streaks = []
    for tid, grp in weekly.sort_values(["track_id", "billboard_week"]).groupby("track_id"):
        wks = grp["billboard_week"].tolist()
        ranks = grp["rank"].tolist()
        cur_rank = ranks[0]
        cur_start = wks[0]
        cur_len = 1
        best_rank = cur_rank
        best_start = cur_start
        best_end = cur_start
        best_len = 1
        for i in range(1, len(wks)):
            if ranks[i] == cur_rank and (wks[i] - wks[i - 1]).days <= 8:
                cur_len += 1
            else:
                if cur_len > best_len:
                    best_len = cur_len
                    best_rank = cur_rank
                    best_start = cur_start
                    best_end = wks[i - 1]
                cur_rank = ranks[i]
                cur_start = wks[i]
                cur_len = 1
        if cur_len > best_len:
            best_len = cur_len
            best_rank = cur_rank
            best_start = cur_start
            best_end = wks[-1]
        same_rank_streaks.append(
            {
                "track_id": tid,
                "track_name": grp.iloc[0]["track_name"],
                "artist_name": grp.iloc[0]["artist_name"],
                "停留排名": best_rank,
                "连续周数": best_len,
                "起始周": best_start,
                "结束周": best_end,
            }
        )
    records["longest_consecutive_same_rank"] = (
        pd.DataFrame(same_rank_streaks).sort_values("连续周数", ascending=False).head(20)
    )
    # Album version
    if weekly_album is not None:
        alb_same_rank = []
        for (aname, aname_artist), grp in weekly_album.sort_values(
            ["album_name", "artist_name", "billboard_week"]
        ).groupby(["album_name", "artist_name"]):
            wks = grp["billboard_week"].tolist()
            ranks = grp["rank"].tolist()
            cr = ranks[0]
            cs = wks[0]
            cl = 1
            br_val = cr
            bs = cs
            be = cs
            bl = 1
            for i in range(1, len(wks)):
                if ranks[i] == cr and (wks[i] - wks[i - 1]).days <= 8:
                    cl += 1
                else:
                    if cl > bl:
                        bl = cl
                        br_val = cr
                        bs = cs
                        be = wks[i - 1]
                    cr = ranks[i]
                    cs = wks[i]
                    cl = 1
            if cl > bl:
                bl = cl
                br_val = cr
                bs = cs
                be = wks[-1]
            alb_same_rank.append(
                {
                    "album_name": aname,
                    "artist_name": aname_artist,
                    "停留排名": br_val,
                    "连续周数": bl,
                    "起始周": bs,
                    "结束周": be,
                }
            )
        records["longest_consecutive_same_rank_album"] = (
            pd.DataFrame(alb_same_rank).sort_values("连续周数", ascending=False).head(20)
        )
    else:
        records["longest_consecutive_same_rank_album"] = pd.DataFrame()

    # ── 21. Longest Artist Chart Span (最长艺人生涯) ────────────────────
    artist_span = (
        track_summary.groupby("artist_name")
        .agg(
            首次上榜=("first_week", "min"),
            最近上榜=("last_week", "max"),
            上榜歌曲数=("track_id", "nunique"),
        )
        .reset_index()
    )
    artist_span["跨度天数"] = artist_span.apply(
        lambda r: (r["最近上榜"] - r["首次上榜"]).days, axis=1
    )
    records["longest_artist_span"] = artist_span.sort_values("跨度天数", ascending=False).head(20)

    # ── 22. Most Simultaneous Top 10 (Top 10 屠榜) ──────────────────────
    top10_weekly = (
        weekly[weekly["rank"] <= 10]
        .groupby(["billboard_week", "artist_name"])
        .agg(top10_count=("track_id", "nunique"))
        .reset_index()
    )
    if not top10_weekly.empty:
        best_top10 = top10_weekly.sort_values("top10_count", ascending=False).iloc[0]
        records["most_top10_simul"] = {
            "artist": best_top10["artist_name"],
            "week": best_top10["billboard_week"],
            "count": int(best_top10["top10_count"]),
        }
    else:
        records["most_top10_simul"] = {}

    # ── 23. Fastest Exit After #1 (最快出榜) ────────────────────────────
    exit_no1 = track_summary[
        (track_summary["peak_position"] == 1) & (track_summary["first_peak_week"].notna())
    ].copy()
    if not exit_no1.empty:
        exit_no1["巅峰后周数"] = exit_no1.apply(
            lambda r: max(0, (r["last_week"] - r["first_peak_week"]).days // 7), axis=1
        )
        records["fastest_exit_after_no1"] = exit_no1.nsmallest(20, "巅峰后周数")[
            ["track_id", "track_name", "artist_name", "first_peak_week", "last_week", "巅峰后周数"]
        ]
    else:
        records["fastest_exit_after_no1"] = pd.DataFrame()

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

    # ── 25-26. Album & Artist Power Ranking (专辑/艺人综合评分总榜) ──────
    if album_power_scores is not None and not album_power_scores.empty:
        records["album_power_ranking"] = album_power_scores.head(20).rename(
            columns={"power_score": "走势评分"}
        )[["album_name", "artist_name", "peak_position", "weeks_on_chart", "走势评分"]]
    else:
        records["album_power_ranking"] = pd.DataFrame()

    if artist_power_scores is not None and not artist_power_scores.empty:
        records["artist_power_ranking"] = artist_power_scores.head(20).rename(
            columns={"power_score": "走势评分"}
        )[["artist_name", "peak_position", "weeks_on_chart", "走势评分"]]
    else:
        records["artist_power_ranking"] = pd.DataFrame()

    # ── 27. Decade Best (年代之王) ──────────────────────────────────────
    # 以专辑实际发行日期判定年代，无发行日期的回退到首次上榜时间
    try:
        album_meta = _load_album_metadata()
        release_dates = album_meta["release_date"][
            ["album_name", "artist_name", "release_date"]
        ].copy()
        ts_decade = track_summary.merge(release_dates, on=["album_name", "artist_name"], how="left")
    except Exception:
        ts_decade = track_summary.copy()
        ts_decade["release_date"] = None

    ts_decade["release_year"] = pd.to_datetime(ts_decade["release_date"], errors="coerce").dt.year
    first_week_year = pd.to_datetime(ts_decade["first_week"]).dt.year
    ts_decade["release_year"] = ts_decade["release_year"].fillna(first_week_year)
    ts_decade["decade"] = (ts_decade["release_year"] // 10) * 10

    wy_decade = weekly.merge(ts_decade[["track_id", "decade"]], on="track_id", how="left")
    wy_decade["decade"] = wy_decade["decade"].fillna(0).astype(int)
    decade_results = []
    for decade, decade_df in wy_decade.groupby("decade"):
        if decade == 0:
            continue
        decade_power = compute_power_scores(decade_df, top_n)
        if not decade_power.empty:
            for i in range(min(5, len(decade_power))):
                top_d = decade_power.iloc[i]
                decade_results.append(
                    {
                        "年代": f"{int(decade)}s",
                        "track_id": top_d["track_id"],
                        "track_name": top_d["track_name"],
                        "artist_name": top_d["artist_name"],
                        "peak": top_d["peak_position"],
                        "weeks_on_chart": top_d["weeks_on_chart"],
                        "走势评分": top_d["power_score"],
                    }
                )
    records["decade_best"] = (
        pd.DataFrame(decade_results).sort_values(["年代", "走势评分"], ascending=[True, False])
        if decade_results
        else pd.DataFrame()
    )

    # ── 28. Triple #1 (全榜单制霸) ──────────────────────────────────────
    if weekly_album is not None and weekly_artist is not None:
        track_no1_w = weekly[weekly["rank"] == 1][
            ["billboard_week", "artist_name"]
        ].drop_duplicates()
        album_no1_w = weekly_album[weekly_album["rank"] == 1][
            ["billboard_week", "artist_name"]
        ].drop_duplicates()
        artist_no1_w = weekly_artist[weekly_artist["rank"] == 1][
            ["billboard_week", "artist_name"]
        ].drop_duplicates()
        triple = track_no1_w.merge(
            album_no1_w, on="billboard_week", suffixes=("_track", "_album")
        ).merge(artist_no1_w, on="billboard_week")
        triple = triple[
            (triple["artist_name_track"] == triple["artist_name_album"])
            & (triple["artist_name_album"] == triple["artist_name"])
        ]
        triple = triple.rename(columns={"artist_name": "艺人"}).drop(
            columns=["artist_name_track", "artist_name_album"]
        )
        triple["billboard_week"] = triple["billboard_week"].astype(str)
        records["triple_no1"] = triple.sort_values("billboard_week", ascending=False)
    else:
        records["triple_no1"] = pd.DataFrame()

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

    return records


# ═══════════════════════════════════════════════════════════════════════════
# Main Billboard computation — mirrors app/pages/billboard/__init__.py:run()
# ═══════════════════════════════════════════════════════════════════════════


def _add_cover_urls(weekly, weekly_album, weekly_artist):
    """为三个周榜 DataFrame 添加 cover_url 列。

    cover_url 统一指向智能封面端点 /covers/{type}/{id}.jpg：
    - 本地有缓存 → 直接返回文件
    - 本地缺失 → 重定向到 Spotify CDN + 后台下载缓存
    - 无任何数据 → null（前端回退 emoji 占位符）
    """
    conn = get_db()

    def _build_url(image_path, image_url, cover_type, entity_id):
        """只要有任何封面数据就返回智能端点 URL，由端点处理回退链。"""
        if image_path or image_url:
            return f"/covers/{cover_type}/{entity_id}.jpg"
        return None

    # ── 曲目榜：track_id → album_id → albums ─────────────────────────
    if not weekly.empty and "track_id" in weekly.columns:
        track_ids = weekly["track_id"].unique().tolist()
        placeholders = ",".join("?" for _ in track_ids)
        rows = conn.execute(
            f"""SELECT t.track_id, al.album_id, al.image_path, al.image_url
                FROM tracks t
                LEFT JOIN albums al ON t.album_id = al.album_id
                WHERE t.track_id IN ({placeholders})""",
            track_ids,
        ).fetchall()
        cover_map = {
            r["track_id"]: _build_url(r["image_path"], r["image_url"], "albums", r["album_id"])
            if r["album_id"]
            else None
            for r in rows
        }
        weekly = weekly.copy()
        weekly["cover_url"] = weekly["track_id"].map(cover_map)

    # ── 专辑榜：(album_name, artist_name) → album_id → albums ────────
    if not weekly_album.empty:
        album_rows = conn.execute(
            """SELECT al.album_id, al.album_name, a.artist_name,
                      al.image_path, al.image_url
               FROM albums al
               JOIN artists a ON al.artist_id = a.artist_id"""
        ).fetchall()
        album_cover_map = {}
        for r in album_rows:
            key = (r["album_name"], r["artist_name"])
            url = _build_url(r["image_path"], r["image_url"], "albums", r["album_id"])
            # 只保留有封面的；None 不覆盖已有有效 URL
            if url or key not in album_cover_map:
                album_cover_map[key] = url
        # 也查 release_groups: canonical_name → 封面（优先主专辑，回退到成员）
        rg_rows = conn.execute(
            """SELECT rg.group_id, rg.canonical_name, a.artist_name,
                      pa.album_id, pa.image_path, pa.image_url
               FROM release_groups rg
               JOIN albums pa ON rg.primary_album_id = pa.album_id
               JOIN artists a ON pa.artist_id = a.artist_id"""
        ).fetchall()
        for r in rg_rows:
            key = (r["canonical_name"], r["artist_name"])
            if album_cover_map.get(key) is None:
                url = _build_url(r["image_path"], r["image_url"], "albums", r["album_id"])
                if url is None:
                    # 主专辑无封面 → 回退到有封面的成员专辑
                    member_row = conn.execute(
                        """SELECT al.album_id, al.image_path, al.image_url
                           FROM release_group_members rgm
                           JOIN albums al ON rgm.album_id = al.album_id
                           WHERE rgm.group_id = ?
                             AND (al.image_path IS NOT NULL AND al.image_path != ''
                                  OR al.image_url IS NOT NULL AND al.image_url != '')
                           ORDER BY al.album_id
                           LIMIT 1""",
                        (r["group_id"],),
                    ).fetchone()
                    if member_row:
                        url = _build_url(
                            member_row["image_path"],
                            member_row["image_url"],
                            "albums",
                            member_row["album_id"],
                        )
                album_cover_map[key] = url

        weekly_album = weekly_album.copy()
        weekly_album["cover_url"] = weekly_album.apply(
            lambda row: album_cover_map.get((row["album_name"], row["artist_name"])), axis=1
        )

    # ── 艺人榜：artist_name → artist_id → artists ────────────────────
    if not weekly_artist.empty:
        artist_rows = conn.execute(
            """SELECT artist_id, artist_name, image_path, image_url
               FROM artists
               WHERE image_path IS NOT NULL AND image_path != ''
                  OR image_url IS NOT NULL AND image_url != ''"""
        ).fetchall()
        artist_cover_map = {
            r["artist_name"]: _build_url(r["image_path"], r["image_url"], "artists", r["artist_id"])
            for r in artist_rows
        }
        weekly_artist = weekly_artist.copy()
        weekly_artist["cover_url"] = weekly_artist["artist_name"].map(artist_cover_map)

    conn.close()
    return weekly, weekly_album, weekly_artist


def _serialize_records(records):
    """Convert the records dict to JSON-safe format.

    Each value is either a DataFrame (→ list of dicts) or a scalar dict (→ native types).
    """
    result = {}
    for key, val in records.items():
        if isinstance(val, pd.DataFrame):
            result[key] = _df_to_json(val)
        elif isinstance(val, dict):
            result[key] = {k: _py_val(v) for k, v in val.items()}
        elif isinstance(val, list):
            result[key] = val
        else:
            result[key] = _py_val(val)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Track History Detail
# ═══════════════════════════════════════════════════════════════════════════
