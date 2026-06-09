"""Endurance, persistence, and rank-stability Billboard record families."""

import pandas as pd


def compute_endurance_records(
    records, weekly, track_summary, weekly_album=None, weekly_artist=None
):
    """Populate records about rank persistence, re-entries, and consecutive patterns."""

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
        album_summary = (
            weekly_album.groupby(["album_name", "artist_name"])
            .agg(
                peak_position=("rank", "min"),
                weeks_on_chart=("billboard_week", "nunique"),
            )
            .reset_index()
        )
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

    if weekly_artist is not None:
        art_at_no2 = (
            weekly_artist[weekly_artist["rank"] == 2]
            .groupby("artist_name")
            .agg(weeks_at_no2=("billboard_week", "nunique"))
            .reset_index()
        )
        if not art_at_no2.empty:
            art_peak = (
                weekly_artist.groupby("artist_name")
                .agg(peak_position=("rank", "min"))
                .reset_index()
            )
            art_no2_with_peak = art_at_no2.merge(art_peak, on="artist_name")
            art_no2_no_no1 = (
                art_no2_with_peak[art_no2_with_peak["peak_position"] > 1]
                .sort_values("weeks_at_no2", ascending=False)
                .head(20)
            )
            records["most_weeks_no2_no_no1_artist"] = art_no2_no_no1[
                ["artist_name", "peak_position", "weeks_at_no2"]
            ]
        else:
            records["most_weeks_no2_no_no1_artist"] = pd.DataFrame()
    else:
        records["most_weeks_no2_no_no1_artist"] = pd.DataFrame()

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

    if weekly_artist is not None:
        artist_reentries = []
        for aname, grp in weekly_artist.sort_values(["artist_name", "billboard_week"]).groupby(
            "artist_name"
        ):
            wks = grp["billboard_week"].tolist()
            count = 0
            for i in range(1, len(wks)):
                if (wks[i] - wks[i - 1]).days > 8:
                    count += 1
            if count > 0:
                artist_reentries.append(
                    {
                        "artist_name": aname,
                        "回榜次数": count,
                        "在榜周数": len(wks),
                    }
                )
        records["most_reentries_artist"] = (
            pd.DataFrame(artist_reentries).sort_values("回榜次数", ascending=False).head(20)
            if artist_reentries
            else pd.DataFrame()
        )
    else:
        records["most_reentries_artist"] = pd.DataFrame()

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

    if weekly_artist is not None:
        art_same_rank = []
        for aname, grp in weekly_artist.sort_values(["artist_name", "billboard_week"]).groupby(
            "artist_name"
        ):
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
            art_same_rank.append(
                {
                    "artist_name": aname,
                    "停留排名": br_val,
                    "连续周数": bl,
                    "起始周": bs,
                    "结束周": be,
                }
            )
        records["longest_consecutive_same_rank_artist"] = (
            pd.DataFrame(art_same_rank).sort_values("连续周数", ascending=False).head(20)
        )
    else:
        records["longest_consecutive_same_rank_artist"] = pd.DataFrame()
