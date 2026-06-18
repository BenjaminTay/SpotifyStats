"""Shared summary computation functions for Billboard charts.

Pure functions: take DataFrames, return DataFrames. No I/O, no caching, no DB.
Caching happens at the caller level in chart_compute.py.
"""

import pandas as pd

from backend.core.db import fan_out_weekly_for_artists
from backend.domains.billboard.album_display import choose_representative_album
from backend.domains.billboard.version_merge import _normalize_album_column


def compute_track_summary(weekly: pd.DataFrame, df_filtered: pd.DataFrame) -> pd.DataFrame:
    """Compute per-track summary from weekly rankings and raw plays.

    Returns DataFrame with columns: track_id, track_name, artist_name, album_name,
    peak_position, weeks_on_chart, weeks_at_peak, first_week, last_week,
    total_chart_plays, total_plays, weeks_at_no1, first_peak_week, is_debut_no1.
    """
    group_cols = ["track_id", "track_name", "artist_name"]
    album_choice = choose_representative_album(weekly, group_cols)

    track_summary = (
        weekly.groupby(group_cols)
        .agg(
            peak_position=("rank", "min"),
            weeks_on_chart=("billboard_week", "nunique"),
            weeks_at_peak=("rank", lambda x: (x == x.min()).sum()),
            first_week=("billboard_week", "min"),
            last_week=("billboard_week", "max"),
            total_chart_plays=("play_count", "sum"),
        )
        .reset_index()
    )
    track_summary = track_summary.merge(album_choice, on=group_cols, how="left")

    if "play_count" in df_filtered.columns:
        track_total_plays = (
            df_filtered.groupby("track_id").agg(total_plays=("play_count", "sum")).reset_index()
        )
    else:
        track_total_plays = (
            df_filtered.groupby("track_id").agg(total_plays=("ms_played", "count")).reset_index()
        )
    track_summary = track_summary.merge(track_total_plays, on="track_id", how="left")

    weeks_at_no1 = (
        weekly[weekly["rank"] == 1]
        .groupby("track_id")
        .agg(weeks_at_no1=("billboard_week", "nunique"))
        .reset_index()
    )
    track_summary = track_summary.merge(weeks_at_no1, on="track_id", how="left")
    track_summary["weeks_at_no1"] = track_summary["weeks_at_no1"].fillna(0).astype(int)

    first_peak = weekly.merge(track_summary[group_cols + ["peak_position"]], on=group_cols)
    first_peak = first_peak[first_peak["rank"] == first_peak["peak_position"]]
    first_peak = first_peak.groupby(group_cols)["billboard_week"].min().reset_index()
    first_peak = first_peak.rename(columns={"billboard_week": "first_peak_week"})
    track_summary = track_summary.merge(first_peak, on=group_cols, how="left")

    track_summary["is_debut_no1"] = (track_summary["peak_position"] == 1) & (
        track_summary["first_week"] == track_summary["first_peak_week"]
    )

    ordered = [
        "track_id",
        "track_name",
        "artist_name",
        "album_name",
        "peak_position",
        "weeks_on_chart",
        "weeks_at_peak",
        "first_week",
        "last_week",
        "total_chart_plays",
        "total_plays",
        "weeks_at_no1",
        "first_peak_week",
        "is_debut_no1",
    ]
    track_summary = track_summary[[col for col in ordered if col in track_summary.columns]]

    return track_summary


def compute_artist_summary(weekly: pd.DataFrame) -> pd.DataFrame:
    """Compute per-artist-per-track summary from weekly rankings.

    Uses fan_out_weekly_for_artists to expand multi-artist tracks.
    Returns DataFrame with columns: artist_name, track_id, track_name, album_name,
    peak_position, weeks_on_chart, weeks_at_peak, first_week, last_week, total_chart_plays.
    """
    weekly_fanned = fan_out_weekly_for_artists(weekly)
    return (
        weekly_fanned.groupby(["artist_name", "track_id", "track_name", "album_name"])
        .agg(
            peak_position=("rank", "min"),
            weeks_on_chart=("billboard_week", "nunique"),
            weeks_at_peak=("rank", lambda x: (x == x.min()).sum()),
            first_week=("billboard_week", "min"),
            last_week=("billboard_week", "max"),
            total_chart_plays=("play_count", "sum"),
        )
        .reset_index()
    )


def compute_artist_track_counts(
    artist_summary: pd.DataFrame,
    track_summary: pd.DataFrame,
    weekly_album: pd.DataFrame,
    weekly_artist: pd.DataFrame,
) -> pd.DataFrame:
    """Compute per-artist aggregate counts and rankings.

    Returns DataFrame with columns: artist_name, total_tracks, best_peak,
    total_weeks, avg_weeks, top1, top5, top10, best_peak_track, weeks_at_no1,
    num_no1_albums, album_no1_weeks, artist_chart_no1_weeks.
    """
    artist_track_counts = (
        artist_summary.groupby("artist_name")
        .agg(
            total_tracks=("track_id", "nunique"),
            best_peak=("peak_position", "min"),
            total_weeks=("weeks_on_chart", "sum"),
            avg_weeks=("weeks_on_chart", "mean"),
            top1=("peak_position", lambda x: (x == 1).sum()),
            top5=("peak_position", lambda x: (x <= 5).sum()),
            top10=("peak_position", lambda x: (x <= 10).sum()),
        )
        .reset_index()
        .sort_values("total_tracks", ascending=False)
    )
    artist_track_counts["best_peak_track"] = artist_track_counts["artist_name"].apply(
        lambda a: (
            artist_summary[artist_summary["artist_name"] == a]
            .sort_values("peak_position")
            .iloc[0]["track_name"]
        )
    )

    artist_weeks_no1 = track_summary.groupby("artist_name")["weeks_at_no1"].sum().reset_index()
    artist_track_counts = artist_track_counts.merge(artist_weeks_no1, on="artist_name", how="left")

    album_no1_artist = (
        weekly_album[weekly_album["rank"] == 1]
        .groupby("artist_name")
        .agg(
            num_no1_albums=("album_name", "nunique"),
            album_no1_weeks=("billboard_week", "nunique"),
        )
        .reset_index()
    )
    artist_track_counts = artist_track_counts.merge(album_no1_artist, on="artist_name", how="left")
    artist_track_counts["num_no1_albums"] = (
        artist_track_counts["num_no1_albums"].fillna(0).astype(int)
    )
    artist_track_counts["album_no1_weeks"] = (
        artist_track_counts["album_no1_weeks"].fillna(0).astype(int)
    )

    artist_no1_weeks = (
        weekly_artist[weekly_artist["rank"] == 1]
        .groupby("artist_name")
        .agg(artist_chart_no1_weeks=("billboard_week", "nunique"))
        .reset_index()
    )
    artist_track_counts = artist_track_counts.merge(artist_no1_weeks, on="artist_name", how="left")
    artist_track_counts["artist_chart_no1_weeks"] = (
        artist_track_counts["artist_chart_no1_weeks"].fillna(0).astype(int)
    )

    return artist_track_counts


def compute_album_track_counts(
    track_summary: pd.DataFrame,
    album_map: pd.DataFrame,
    weekly_album: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute per-album aggregate counts via track-album expansion.

    Returns (album_track_counts, track_per_album).
    album_track_counts columns: album_name, artist_name, total_tracks, best_peak,
    total_weeks, avg_weeks, top1, top5, top10, best_peak_track, weeks_at_no1,
    album_chart_no1_weeks.
    """
    ts_for_album = track_summary.drop(columns=["album_name"])
    track_albums_expanded = ts_for_album.merge(album_map, on="track_id", how="left")
    track_albums_expanded["album_list"] = track_albums_expanded["album_list"].apply(
        lambda x: x if isinstance(x, list) else []
    )
    track_per_album = track_albums_expanded.explode("album_list")
    track_per_album = track_per_album.dropna(subset=["album_list"])
    track_per_album = track_per_album.rename(columns={"album_list": "album_name"})
    track_per_album = _normalize_album_column(
        track_per_album, dedup_cols=["track_id", "album_name", "artist_name"]
    )

    album_track_counts = (
        track_per_album.groupby(["album_name", "artist_name"])
        .agg(
            total_tracks=("track_id", "nunique"),
            best_peak=("peak_position", "min"),
            total_weeks=("weeks_on_chart", "sum"),
            avg_weeks=("weeks_on_chart", "mean"),
            top1=("peak_position", lambda x: (x == 1).sum()),
            top5=("peak_position", lambda x: (x <= 5).sum()),
            top10=("peak_position", lambda x: (x <= 10).sum()),
        )
        .reset_index()
        .sort_values("total_tracks", ascending=False)
    )
    album_track_counts["best_peak_track"] = album_track_counts.apply(
        lambda r: (
            track_per_album[
                (track_per_album["album_name"] == r["album_name"])
                & (track_per_album["artist_name"] == r["artist_name"])
            ]
            .sort_values("peak_position")
            .iloc[0]["track_name"]
        ),
        axis=1,
    )

    album_weeks_no1 = (
        track_per_album.groupby(["album_name", "artist_name"])["weeks_at_no1"].sum().reset_index()
    )
    album_track_counts = album_track_counts.merge(
        album_weeks_no1, on=["album_name", "artist_name"], how="left"
    )

    album_no1 = (
        weekly_album[weekly_album["rank"] == 1]
        .groupby(["album_name", "artist_name"])
        .agg(album_chart_no1_weeks=("billboard_week", "nunique"))
        .reset_index()
    )
    album_track_counts = album_track_counts.merge(
        album_no1, on=["album_name", "artist_name"], how="left"
    )
    album_track_counts["album_chart_no1_weeks"] = (
        album_track_counts["album_chart_no1_weeks"].fillna(0).astype(int)
    )

    return album_track_counts, track_per_album
