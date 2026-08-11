"""Movement and breakthrough Billboard record families."""

import pandas as pd

from backend.core.db import fan_out_weekly_for_artists, primary_artist_names_for_tracks


def compute_movement_records(records, weekly, track_summary, weekly_album=None, weekly_artist=None):
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

    # Album ownership is keyed by the primary canonical artist, while the
    # incoming weekly frame may already contain featured artists for display.
    _weekly_norm = _normalize_album_column(primary_artist_names_for_tracks(weekly))
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

    top10_weekly = (
        fan_out_weekly_for_artists(weekly)[lambda frame: frame["rank"] <= 10]
        .drop_duplicates(["billboard_week", "track_id", "artist_name"])
        .groupby(["billboard_week", "artist_name"])["track_id"]
        .nunique()
        .reset_index(name="track_count")
    )
    if not top10_weekly.empty:
        best_top10 = top10_weekly.sort_values("track_count", ascending=False).iloc[0]
        records["most_top10_simul"] = {
            "artist": best_top10["artist_name"],
            "week": best_top10["billboard_week"],
            "count": int(best_top10["track_count"]),
        }
    else:
        records["most_top10_simul"] = {}

    week_strength = weekly.groupby("billboard_week")["play_count"].sum().reset_index()
    if not week_strength.empty:
        best_week = week_strength.sort_values("play_count", ascending=False).iloc[0]
        records["strongest_week"] = {
            "week": best_week["billboard_week"],
            "play_count": int(best_week["play_count"]),
        }
    else:
        records["strongest_week"] = {}

    # ── 17. Longest / Fastest Climb to #1 (登顶路) ─────────────────────
    to_no1 = track_summary[
        (track_summary["peak_position"] == 1) & (track_summary["first_peak_week"].notna())
    ].copy()
    if not to_no1.empty:
        # 统计首次上榜到首次夺冠之间实际在榜的周数（不含夺冠周本身）
        climb_weekly = weekly[weekly["track_id"].isin(to_no1["track_id"])]
        climb_weekly = climb_weekly.merge(
            to_no1[["track_id", "first_week", "first_peak_week"]], on="track_id"
        )
        climb_weekly = climb_weekly[
            (climb_weekly["billboard_week"] >= climb_weekly["first_week"])
            & (climb_weekly["billboard_week"] < climb_weekly["first_peak_week"])
        ]
        climb_counts = climb_weekly.groupby("track_id")["billboard_week"].nunique().reset_index()
        climb_counts.columns = ["track_id", "登顶周数"]
        to_no1 = to_no1.merge(climb_counts, on="track_id", how="left")
        to_no1["登顶周数"] = to_no1["登顶周数"].fillna(0).astype(int)
        records["longest_to_no1"] = to_no1.nlargest(20, "登顶周数")[
            ["track_id", "track_name", "artist_name", "first_week", "first_peak_week", "登顶周数"]
        ]
        records["fastest_to_no1"] = to_no1.nsmallest(20, "登顶周数")[
            ["track_id", "track_name", "artist_name", "first_week", "first_peak_week", "登顶周数"]
        ]
    else:
        records["longest_to_no1"] = pd.DataFrame()
        records["fastest_to_no1"] = pd.DataFrame()

    # ── 17b. Longest Climb to #1 — Album ──────────────────────────────
    if weekly_album is not None:
        album_summary = (
            weekly_album.groupby(["album_name", "artist_name"])
            .agg(
                peak_position=("rank", "min"),
                first_week=("billboard_week", "min"),
            )
            .reset_index()
        )
        first_peak_alb = (
            weekly_album[weekly_album["rank"] == 1]
            .groupby(["album_name", "artist_name"])["billboard_week"]
            .min()
            .reset_index()
            .rename(columns={"billboard_week": "first_peak_week"})
        )
        album_summary = album_summary.merge(
            first_peak_alb, on=["album_name", "artist_name"], how="left"
        )
        to_no1_alb = album_summary[
            (album_summary["peak_position"] == 1) & (album_summary["first_peak_week"].notna())
        ].copy()
        if not to_no1_alb.empty:
            climb_wa = weekly_album.merge(
                to_no1_alb[["album_name", "artist_name", "first_week", "first_peak_week"]],
                on=["album_name", "artist_name"],
            )
            climb_wa = climb_wa[
                (climb_wa["billboard_week"] >= climb_wa["first_week"])
                & (climb_wa["billboard_week"] < climb_wa["first_peak_week"])
            ]
            climb_counts_alb = (
                climb_wa.groupby(["album_name", "artist_name"])["billboard_week"]
                .nunique()
                .reset_index()
            )
            climb_counts_alb.columns = ["album_name", "artist_name", "登顶周数"]
            to_no1_alb = to_no1_alb.merge(
                climb_counts_alb, on=["album_name", "artist_name"], how="left"
            )
            to_no1_alb["登顶周数"] = to_no1_alb["登顶周数"].fillna(0).astype(int)
            records["longest_to_no1_album"] = to_no1_alb.nlargest(20, "登顶周数")[
                ["album_name", "artist_name", "first_week", "first_peak_week", "登顶周数"]
            ]
            records["fastest_to_no1_album"] = to_no1_alb.nsmallest(20, "登顶周数")[
                ["album_name", "artist_name", "first_week", "first_peak_week", "登顶周数"]
            ]
        else:
            records["longest_to_no1_album"] = pd.DataFrame()
            records["fastest_to_no1_album"] = pd.DataFrame()
    else:
        records["longest_to_no1_album"] = pd.DataFrame()
        records["fastest_to_no1_album"] = pd.DataFrame()

    # ── 17c. Longest Climb to #1 — Artist ─────────────────────────────
    if weekly_artist is not None:
        artist_summary = (
            weekly_artist.groupby("artist_name")
            .agg(
                peak_position=("rank", "min"),
                first_week=("billboard_week", "min"),
            )
            .reset_index()
        )
        first_peak_art = (
            weekly_artist[weekly_artist["rank"] == 1]
            .groupby("artist_name")["billboard_week"]
            .min()
            .reset_index()
            .rename(columns={"billboard_week": "first_peak_week"})
        )
        artist_summary = artist_summary.merge(first_peak_art, on="artist_name", how="left")
        to_no1_art = artist_summary[
            (artist_summary["peak_position"] == 1) & (artist_summary["first_peak_week"].notna())
        ].copy()
        if not to_no1_art.empty:
            climb_wart = weekly_artist.merge(
                to_no1_art[["artist_name", "first_week", "first_peak_week"]],
                on="artist_name",
            )
            climb_wart = climb_wart[
                (climb_wart["billboard_week"] >= climb_wart["first_week"])
                & (climb_wart["billboard_week"] < climb_wart["first_peak_week"])
            ]
            climb_counts_art = (
                climb_wart.groupby("artist_name")["billboard_week"].nunique().reset_index()
            )
            climb_counts_art.columns = ["artist_name", "登顶周数"]
            to_no1_art = to_no1_art.merge(climb_counts_art, on="artist_name", how="left")
            to_no1_art["登顶周数"] = to_no1_art["登顶周数"].fillna(0).astype(int)
            records["longest_to_no1_artist"] = to_no1_art.nlargest(20, "登顶周数")[
                ["artist_name", "first_week", "first_peak_week", "登顶周数"]
            ]
            records["fastest_to_no1_artist"] = to_no1_art.nsmallest(20, "登顶周数")[
                ["artist_name", "first_week", "first_peak_week", "登顶周数"]
            ]
        else:
            records["longest_to_no1_artist"] = pd.DataFrame()
            records["fastest_to_no1_artist"] = pd.DataFrame()
    else:
        records["longest_to_no1_artist"] = pd.DataFrame()
        records["fastest_to_no1_artist"] = pd.DataFrame()
