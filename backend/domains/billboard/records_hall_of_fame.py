"""Hall of Fame and power ranking Billboard record families."""

import pandas as pd

from backend.core.db import primary_artist_names_for_tracks
from backend.domains.billboard.chart_compute import compute_power_scores
from backend.domains.billboard.data_loader import _load_album_metadata


def compute_hall_of_fame_records(
    records,
    weekly,
    track_summary,
    top_n,
    track_power_scores=None,
    album_power_scores=None,
    artist_power_scores=None,
):
    """Populate hall of fame records: all-time greatest, year-end #1, power rankings, decade best."""

    # ── 11. All-Time Greatest (Power Score) ──────────────────────────────
    if track_power_scores is not None:
        power_df = track_power_scores
    else:
        power_df = compute_power_scores(weekly, top_n)
    no1_weeks_map = track_summary[["track_id", "weeks_at_no1"]].drop_duplicates()
    power_df = power_df.merge(no1_weeks_map, on="track_id", how="left")
    power_df["weeks_at_no1"] = power_df["weeks_at_no1"].fillna(0).astype(int)
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
    try:
        album_meta = _load_album_metadata()
        release_dates = album_meta["release_date"][
            ["album_name", "artist_name", "release_date"]
        ].copy()
        track_summary_for_album_join = primary_artist_names_for_tracks(track_summary).rename(
            columns={"artist_name": "_primary_artist_name"}
        )
        release_dates = release_dates.rename(columns={"artist_name": "_primary_artist_name"})
        ts_decade = track_summary.merge(
            track_summary_for_album_join[["track_id", "_primary_artist_name"]],
            on="track_id",
            how="left",
        ).merge(
            release_dates,
            on=["album_name", "_primary_artist_name"],
            how="left",
        )
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
