"""Shared Billboard load/rank cache used by full and staged chart APIs."""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from backend.core.cache import singleflight
from backend.domains.billboard.chart_ranking import (
    _add_running_metrics,
    compute_album_weekly_rankings,
    compute_artist_weekly_rankings,
    compute_weekly_rankings,
)
from backend.domains.billboard.data_loader import (
    _try_load_from_agg,
    load_billboard_raw,
    load_billboard_raw_for_artists,
)
from backend.domains.billboard.version_merge import _normalize_album_column


@singleflight
@lru_cache(maxsize=8)
def _load_and_rank_cached(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
    merge_level=2,
    dynamic_threshold=False,
    max_merge_gap_minutes=None,
    include_compilations=False,
):
    return _load_and_rank_uncached(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
        merge_level,
        dynamic_threshold,
        max_merge_gap_minutes,
        include_compilations,
    )


def _copy_load_and_rank_result(result):
    if len(result) == 7:
        (
            weekly,
            weekly_album,
            weekly_artist,
            all_weeks_asc,
            all_weeks_desc,
            df_filtered,
            album_total_map,
        ) = result
    else:
        weekly, weekly_album, weekly_artist, all_weeks_asc, all_weeks_desc, df_filtered = result
        album_total_map = {}
    return (
        weekly.copy(),
        weekly_album.copy(),
        weekly_artist.copy(),
        list(all_weeks_asc),
        list(all_weeks_desc),
        df_filtered.copy(),
        album_total_map,
    )


def _load_and_rank_uncached(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
    merge_level=2,
    dynamic_threshold=False,
    max_merge_gap_minutes=None,
    include_compilations=False,
):
    _agg_tracks, _agg_albums, _agg_artists = _try_load_from_agg(
        min_ms,
        music_only,
        bb_week_start_dow,
        bb_week_start_hour,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
    )

    if _agg_tracks is not None:
        _agg_tracks = _filter_billboard_years(_agg_tracks, year_start, year_end)
        _agg_albums = _filter_billboard_years(_agg_albums, year_start, year_end)
        _agg_artists = _filter_billboard_years(_agg_artists, year_start, year_end)
        df_filtered = _agg_tracks.copy()
    else:
        df_raw = load_billboard_raw(
            min_ms,
            music_only,
            bb_week_start_dow,
            bb_week_start_hour,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
        )
        df_filtered = _filter_billboard_years(df_raw.copy(), year_start, year_end)

    all_weeks_asc = sorted(df_filtered["billboard_week"].unique().tolist())
    all_weeks_desc = sorted(all_weeks_asc, reverse=True)
    weekly = compute_weekly_rankings(
        df_filtered, bb_top_n, pre_agg=_agg_tracks, merge_level=merge_level
    )
    weekly_album = compute_album_weekly_rankings(
        df_filtered,
        bb_album_top_n,
        pre_agg=_agg_albums,
        merge_level=merge_level,
        include_compilations=include_compilations,
    )

    if _agg_artists is not None:
        weekly_artist = compute_artist_weekly_rankings(
            df_filtered, bb_artist_top_n, pre_agg=_agg_artists
        )
    else:
        df_artists = load_billboard_raw_for_artists(
            min_ms,
            music_only,
            bb_week_start_dow,
            bb_week_start_hour,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
        )
        df_artists = df_artists.copy()
        df_artists["_year"] = df_artists["billboard_week"].apply(lambda x: x.year)
        if year_start is not None:
            df_artists = df_artists[df_artists["_year"] >= year_start]
        if year_end is not None:
            df_artists = df_artists[df_artists["_year"] <= year_end]
        weekly_artist = compute_artist_weekly_rankings(df_artists, bb_artist_top_n)

    if _agg_tracks is not None:
        weekly_album, weekly_artist = _attach_track_and_artist_counts_from_preagg(
            weekly, weekly_album, weekly_artist
        )

    _artist_ac = (
        weekly_album.groupby(["billboard_week", "artist_name"])
        .agg(albums_count=("album_name", "nunique"))
        .reset_index()
    )
    weekly_artist = weekly_artist.merge(
        _artist_ac, on=["billboard_week", "artist_name"], how="left"
    )
    weekly_artist["albums_count"] = weekly_artist["albums_count"].fillna(0).astype(int)

    weekly = _add_running_metrics(weekly, ["track_id"])
    weekly_album = _add_running_metrics(weekly_album, ["artist_name", "album_name"])
    weekly_artist = _add_running_metrics(weekly_artist, ["artist_name"])

    # Compute unfiltered total_plays for all album projects (no release-date filter)
    from backend.core.db import get_db
    from backend.domains.playback.album_projects import compute_album_project_plays

    conn = get_db()
    try:
        album_total_plays = compute_album_project_plays(
            df_filtered,
            conn,
            merge_level=merge_level,
            include_compilations=include_compilations,
            billboard_mode=False,
        )
        album_total_map = {}
        if not album_total_plays.empty:
            for _, row in album_total_plays.iterrows():
                key = (row["album_project_name"], row["artist_name"])
                album_total_map[key] = int(row["play_count"])
    finally:
        conn.close()

    return (
        weekly,
        weekly_album,
        weekly_artist,
        all_weeks_asc,
        all_weeks_desc,
        df_filtered,
        album_total_map,
    )


def _attach_track_and_artist_counts_from_preagg(weekly, weekly_album, weekly_artist):
    _album_tc = (
        weekly.groupby(["billboard_week", "album_name", "artist_name"])
        .agg(tracks_count=("track_id", "nunique"))
        .reset_index()
    )
    _album_tc = _normalize_album_column(
        _album_tc, dedup_cols=["billboard_week", "album_name", "artist_name"]
    )
    _album_tc = (
        _album_tc.groupby(["billboard_week", "album_name", "artist_name"])
        .agg(tracks_count=("tracks_count", "sum"))
        .reset_index()
    )
    weekly_album = weekly_album.drop(columns=["tracks_count"], errors="ignore").merge(
        _album_tc, on=["billboard_week", "album_name", "artist_name"], how="left"
    )
    weekly_album["tracks_count"] = weekly_album["tracks_count"].fillna(0).astype(int)

    _artist_tc = (
        weekly.groupby(["billboard_week", "artist_name"])
        .agg(tracks_count=("track_id", "nunique"))
        .reset_index()
    )
    weekly_artist = weekly_artist.drop(columns=["tracks_count"], errors="ignore").merge(
        _artist_tc, on=["billboard_week", "artist_name"], how="left"
    )
    weekly_artist["tracks_count"] = weekly_artist["tracks_count"].fillna(0).astype(int)
    return weekly_album, weekly_artist


def _filter_billboard_years(
    df: pd.DataFrame,
    year_start: int | None,
    year_end: int | None,
) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()
    years = pd.to_datetime(out["billboard_week"]).dt.year
    if year_start is not None:
        out = out[years >= year_start]
        years = years.loc[out.index]
    if year_end is not None:
        out = out[years <= year_end]
    return out


def _filtered_record_count(df: pd.DataFrame) -> int:
    if "play_count" in df.columns:
        return int(pd.to_numeric(df["play_count"], errors="coerce").fillna(0).sum())
    return int(len(df))
