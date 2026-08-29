"""Championship and #1 Billboard record families."""

import pandas as pd

from backend.core.db import fan_out_weekly_for_artists
from backend.domains.billboard.chart_ranking import _normalised_text_key


def _stable_artist_metric_sort(
    frame: pd.DataFrame,
    metric: str,
    *,
    extra_columns: tuple[str, ...] = (),
) -> pd.DataFrame:
    result = frame.copy()
    result["_stable_artist_name"] = result["artist_name"].map(_normalised_text_key)
    result["_stable_artist_original"] = result["artist_name"].fillna("").astype(str)
    columns = [metric, "_stable_artist_name", "_stable_artist_original", *extra_columns]
    ascending = [False, True, True, *([True] * len(extra_columns))]
    return result.sort_values(columns, ascending=ascending, kind="stable").drop(
        columns=["_stable_artist_name", "_stable_artist_original"]
    )


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
        sorted_artist_weekly = _stable_artist_metric_sort(
            artist_weekly, "track_count", extra_columns=("billboard_week",)
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
    artist_no1 = _stable_artist_metric_sort(artist_no1, "冠单数")
    records["artist_most_no1"] = artist_no1.head(15)

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
        records["return_to_no1_artist"] = (
            pd.DataFrame(artist_returns).sort_values("间隔周数", ascending=False)
            if artist_returns
            else pd.DataFrame()
        )
    else:
        records["return_to_no1_artist"] = pd.DataFrame()

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
