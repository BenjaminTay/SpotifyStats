"""Championship and #1 Billboard record families."""

import pandas as pd

from backend.core.db import fan_out_weekly_for_artists
from backend.domains.billboard.record_sorting import stable_record_sort


def compute_championship_records(
    records, weekly, track_summary, weekly_album=None, weekly_artist=None
):
    """Populate championship records: artist simul, most #1, return to #1, debut #1."""

    credited_weekly = fan_out_weekly_for_artists(weekly).drop_duplicates(
        ["billboard_week", "track_id", "artist_name"]
    )

    # ── 1. Most simultaneous chart entries by artist (full chart) ──────
    artist_weekly = (
        credited_weekly.groupby(["billboard_week", "artist_name"])["track_id"]
        .nunique()
        .reset_index(name="track_count")
    )
    if not artist_weekly.empty:
        sorted_artist_weekly = stable_record_sort(
            artist_weekly,
            [("track_count", False), ("billboard_week", False)],
            stable_columns=("artist_name",),
        )
        best_full = sorted_artist_weekly.iloc[0]
        records["artist_simul"] = {
            "artist": best_full["artist_name"],
            "week": best_full["billboard_week"],
            "count": int(best_full["track_count"]),
        }
        records["artist_simul_list"] = sorted_artist_weekly.head(15)

    # ── 3. Most #1 songs by artist ─────────────────────────────────────
    no1_tracks = credited_weekly[credited_weekly["rank"] == 1][
        ["track_id", "artist_name"]
    ].drop_duplicates()
    artist_no1 = no1_tracks.groupby("artist_name").size().reset_index(name="冠单数")

    track_no1_weeks = (
        no1_tracks.merge(
            track_summary[["track_id", "weeks_at_no1"]].drop_duplicates("track_id"),
            on="track_id",
            how="left",
        )
        .groupby("artist_name", as_index=False)["weeks_at_no1"]
        .sum()
        .rename(columns={"weeks_at_no1": "单曲冠军周数"})
    )
    artist_track_metrics = artist_no1.merge(track_no1_weeks, on="artist_name", how="left")
    artist_track_metrics["单曲冠军周数"] = (
        artist_track_metrics["单曲冠军周数"].fillna(0).astype(int)
    )

    if weekly_album is not None:
        album_no1 = weekly_album[weekly_album["rank"] == 1]
        album_no1_cnt = (
            album_no1.groupby("artist_name")["album_name"].nunique().reset_index(name="冠军专辑数")
        )
        album_no1_weeks = (
            album_no1.groupby("artist_name")["billboard_week"]
            .nunique()
            .reset_index(name="专辑冠军周数")
        )
        artist_album_metrics = album_no1_cnt.merge(album_no1_weeks, on="artist_name", how="left")
    else:
        artist_album_metrics = pd.DataFrame(columns=["artist_name", "冠军专辑数", "专辑冠军周数"])

    artist_metrics = artist_track_metrics.merge(artist_album_metrics, on="artist_name", how="outer")
    for column in ("冠单数", "单曲冠军周数", "冠军专辑数", "专辑冠军周数"):
        artist_metrics[column] = (
            pd.to_numeric(artist_metrics[column], errors="coerce").fillna(0).astype(int)
        )

    artist_track_rows = artist_metrics[artist_metrics["冠单数"] > 0]
    records["artist_most_no1"] = stable_record_sort(
        artist_track_rows,
        [("冠单数", False), ("单曲冠军周数", False)],
        stable_columns=("artist_name",),
        limit=15,
    )

    artist_album_rows = artist_metrics[artist_metrics["冠军专辑数"] > 0]
    records["artist_most_no1_album"] = stable_record_sort(
        artist_album_rows,
        [("冠军专辑数", False), ("专辑冠军周数", False)],
        stable_columns=("artist_name",),
        limit=15,
    )

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
    records["return_to_no1"] = stable_record_sort(
        pd.DataFrame(returns),
        [("间隔周数", False), ("回冠日期", False)],
        stable_columns=("track_id", "artist_name", "track_name"),
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
        records["return_to_no1_album"] = stable_record_sort(
            pd.DataFrame(album_returns),
            [("间隔周数", False), ("回冠日期", False)],
            stable_columns=("album_name", "artist_name"),
        )
    else:
        records["return_to_no1_album"] = pd.DataFrame()

    if weekly_artist is not None:
        artist_no1_weeks = (
            weekly_artist[weekly_artist["rank"] == 1][["artist_name", "billboard_week"]]
            .drop_duplicates()
            .sort_values(["artist_name", "billboard_week"])
        )
        artist_returns = []
        for aname, grp in artist_no1_weeks.groupby("artist_name"):
            if len(grp) >= 2:
                wks = grp["billboard_week"].tolist()
                for i in range(1, len(wks)):
                    gap = (wks[i] - wks[i - 1]).days
                    if gap > 8:
                        artist_returns.append(
                            {
                                "artist_name": aname,
                                "首次夺艺冠": wks[i - 1],
                                "回冠日期": wks[i],
                                "间隔周数": gap // 7,
                            }
                        )
        records["return_to_no1_artist"] = stable_record_sort(
            pd.DataFrame(artist_returns),
            [("间隔周数", False), ("回冠日期", False)],
            stable_columns=("artist_name",),
        )
    else:
        records["return_to_no1_artist"] = pd.DataFrame()

    # ── 5. Debut at #1 ─────────────────────────────────────────────────
    debut = track_summary[
        (track_summary["peak_position"] == 1)
        & (track_summary["first_week"] == track_summary["first_peak_week"])
    ].copy()
    records["debut_no1"] = stable_record_sort(
        debut,
        [("first_week", True)],
        stable_columns=("track_id", "artist_name", "track_name"),
    )[["track_id", "track_name", "artist_name", "first_week", "weeks_at_no1", "weeks_on_chart"]]
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
        album_debut_no1 = album_debut_no1.rename(columns={"billboard_week": "first_week"})
        records["debut_no1_album"] = stable_record_sort(
            album_debut_no1,
            [("first_week", True)],
            stable_columns=("album_name", "artist_name"),
        )[["album_name", "artist_name", "first_week", "weeks_at_no1", "weeks_on_chart"]]
    else:
        records["debut_no1_album"] = pd.DataFrame()
