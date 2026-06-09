"""Championship and #1 Billboard record families."""

import pandas as pd


def compute_championship_records(records, weekly, track_summary, weekly_album=None):
    """Populate championship records: artist simul, most #1, return to #1, debut #1."""

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

    track_no1_weeks = (
        track_summary.groupby("artist_name")["weeks_at_no1"].sum().reset_index(name="单曲冠军周数")
    )
    records["artist_most_no1"] = records["artist_most_no1"].merge(
        track_no1_weeks, on="artist_name", how="left"
    )
    records["artist_most_no1"]["单曲冠军周数"] = (
        records["artist_most_no1"]["单曲冠军周数"].fillna(0).astype(int)
    )

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
                if gap > 8:
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
