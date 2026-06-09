"""Movement and breakthrough Billboard record families."""

import pandas as pd


def compute_movement_records(records, weekly, track_summary, weekly_album=None):
    """Populate movement records: biggest jump/drop, album simul, longest/fastest to #1, most top10 simul."""

    # ── 9. Biggest Jump / Drop ─────────────────────────────────────────
    changes = []
    for tid, grp in weekly.sort_values(["track_id", "billboard_week"]).groupby("track_id"):
        grp = grp.sort_values("billboard_week")
        rows = grp.to_dict("records")
        for i in range(1, len(rows)):
            prev, curr = rows[i - 1], rows[i]
            if (curr["billboard_week"] - prev["billboard_week"]).days <= 8:
                change = prev["rank"] - curr["rank"]
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
    from backend.domains.billboard.version_merge import _normalize_album_column

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
