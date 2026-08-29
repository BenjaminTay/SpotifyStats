"""Longevity and persistence Billboard record families."""

import pandas as pd

from backend.core.db import fan_out_weekly_for_artists
from backend.domains.billboard.record_sorting import stable_record_sort


def _rank(frame, sort_keys, stable_columns, columns=None):
    ranked = stable_record_sort(frame, sort_keys, stable_columns=stable_columns, limit=20)
    return ranked[columns] if columns else ranked


def compute_longevity_records(
    records, weekly, track_summary, weekly_album=None, weekly_artist=None
):
    """Populate chart longevity, streak, re-entry, and career-span records."""
    # ── 6. Longest charting songs ──────────────────────────────────────
    records["longest_charting"] = _rank(
        track_summary,
        [
            ("weeks_on_chart", False),
            ("peak_position", True),
            ("weeks_at_no1", False),
            ("first_week", True),
        ],
        ("track_id", "artist_name", "track_name"),
        [
            "track_id",
            "track_name",
            "artist_name",
            "weeks_on_chart",
            "peak_position",
            "weeks_at_no1",
        ],
    )
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
        records["longest_charting_album"] = _rank(
            album_summary,
            [
                ("weeks_on_chart", False),
                ("peak_position", True),
                ("weeks_at_no1", False),
                ("first_week", True),
            ],
            ("album_name", "artist_name"),
            ["album_name", "artist_name", "weeks_on_chart", "peak_position", "weeks_at_no1"],
        )
    else:
        album_summary = pd.DataFrame()
        records["longest_charting_album"] = pd.DataFrame()

    if weekly_artist is not None:
        artist_summary = (
            weekly_artist.groupby("artist_name")
            .agg(
                peak_position=("rank", "min"),
                weeks_on_chart=("billboard_week", "nunique"),
                first_week=("billboard_week", "min"),
                last_week=("billboard_week", "max"),
            )
            .reset_index()
        )
        artist_no1_wks = (
            weekly_artist[weekly_artist["rank"] == 1]
            .groupby("artist_name")["billboard_week"]
            .nunique()
            .reset_index(name="weeks_at_no1")
        )
        artist_summary = artist_summary.merge(artist_no1_wks, on="artist_name", how="left")
        artist_summary["weeks_at_no1"] = artist_summary["weeks_at_no1"].fillna(0).astype(int)
        records["longest_charting_artist"] = _rank(
            artist_summary,
            [
                ("weeks_on_chart", False),
                ("peak_position", True),
                ("weeks_at_no1", False),
                ("first_week", True),
            ],
            ("artist_name",),
            ["artist_name", "weeks_on_chart", "peak_position", "weeks_at_no1"],
        )
    else:
        records["longest_charting_artist"] = pd.DataFrame()

    # ── 7. Longest charting without Top 5 ──────────────────────────────
    no_top5 = _rank(
        track_summary[track_summary["peak_position"] > 5],
        [("weeks_on_chart", False), ("peak_position", True), ("first_week", True)],
        ("track_id", "artist_name", "track_name"),
        ["track_id", "track_name", "artist_name", "weeks_on_chart", "peak_position"],
    )
    records["longest_no_top5"] = no_top5
    # Album version
    if weekly_album is not None:
        no_top5_album = _rank(
            album_summary[album_summary["peak_position"] > 5],
            [("weeks_on_chart", False), ("peak_position", True), ("first_week", True)],
            ("album_name", "artist_name"),
            ["album_name", "artist_name", "weeks_on_chart", "peak_position"],
        )
        records["longest_no_top5_album"] = no_top5_album
    else:
        records["longest_no_top5_album"] = pd.DataFrame()

    if weekly_artist is not None:
        no_top5_artist = _rank(
            artist_summary[artist_summary["peak_position"] > 5],
            [("weeks_on_chart", False), ("peak_position", True), ("first_week", True)],
            ("artist_name",),
            ["artist_name", "weeks_on_chart", "peak_position"],
        )
        records["longest_no_top5_artist"] = no_top5_artist
    else:
        records["longest_no_top5_artist"] = pd.DataFrame()

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
    records["longest_streak"] = _rank(
        pd.DataFrame(streaks),
        [("连续周数", False), ("起始周", True), ("结束周", False)],
        ("track_id", "artist_name", "track_name"),
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
        records["longest_streak_album"] = _rank(
            pd.DataFrame(album_streaks),
            [("连续周数", False), ("起始周", True), ("结束周", False)],
            ("album_name", "artist_name"),
        )
    else:
        records["longest_streak_album"] = pd.DataFrame()

    if weekly_artist is not None:
        artist_streaks = []
        for aname, grp in weekly_artist.sort_values(["artist_name", "billboard_week"]).groupby(
            "artist_name"
        ):
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
            artist_streaks.append(
                {
                    "artist_name": aname,
                    "连续周数": max_run,
                    "起始周": best_start,
                    "结束周": best_end,
                }
            )
        records["longest_streak_artist"] = _rank(
            pd.DataFrame(artist_streaks),
            [("连续周数", False), ("起始周", True), ("结束周", False)],
            ("artist_name",),
        )
    else:
        records["longest_streak_artist"] = pd.DataFrame()

    # ── 21. Longest Artist Chart Span (最长艺人生涯) ────────────────────
    credited_weekly = fan_out_weekly_for_artists(weekly).drop_duplicates(
        ["billboard_week", "track_id", "artist_name"]
    )
    artist_span = (
        credited_weekly.groupby("artist_name")
        .agg(
            首次上榜=("billboard_week", "min"),
            最近上榜=("billboard_week", "max"),
            上榜歌曲数=("track_id", "nunique"),
        )
        .reset_index()
    )
    artist_span["跨度天数"] = artist_span.apply(
        lambda r: (r["最近上榜"] - r["首次上榜"]).days, axis=1
    )
    records["longest_artist_span"] = _rank(
        artist_span,
        [("跨度天数", False), ("上榜歌曲数", False), ("最近上榜", False), ("首次上榜", True)],
        ("artist_name",),
    )

    # ── 23. Fastest Exit After #1 (最快出榜) ────────────────────────────
    exit_no1 = track_summary[
        (track_summary["peak_position"] == 1) & (track_summary["first_peak_week"].notna())
    ].copy()
    if not exit_no1.empty:
        exit_no1["巅峰后周数"] = exit_no1.apply(
            lambda r: max(0, (r["last_week"] - r["first_peak_week"]).days // 7), axis=1
        )
        records["fastest_exit_after_no1"] = _rank(
            exit_no1,
            [("巅峰后周数", True), ("last_week", False), ("first_peak_week", False)],
            ("track_id", "artist_name", "track_name"),
            ["track_id", "track_name", "artist_name", "first_peak_week", "last_week", "巅峰后周数"],
        )
    else:
        records["fastest_exit_after_no1"] = pd.DataFrame()
