"""Staged Billboard cached computations — _load_and_rank, weekly/power/summaries/records."""

from functools import lru_cache

import pandas as pd

from backend.core.db import enrich_track_artist_names
from backend.core.json_helpers import df_to_json as _df_to_json
from backend.domains.billboard.chart_power_score import (
    compute_album_power_scores,
    compute_artist_power_scores,
    compute_power_scores,
)
from backend.domains.billboard.chart_ranking import (
    _add_running_metrics,
    compute_album_weekly_rankings,
    compute_artist_weekly_rankings,
    compute_weekly_rankings,
)
from backend.domains.billboard.chart_summaries import (
    compute_album_track_counts,
    compute_artist_summary,
    compute_artist_track_counts,
    compute_track_summary,
)
from backend.domains.billboard.data_loader import (
    DOW_NAMES,
    DOW_SHORT,
    _try_load_from_agg,
    load_billboard_raw,
    load_billboard_raw_for_artists,
    load_track_album_map,
)
from backend.domains.billboard.version_merge import _normalize_album_column


def _load_and_rank(
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
    df_raw = load_billboard_raw(
        min_ms,
        music_only,
        bb_week_start_dow,
        bb_week_start_hour,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
    )

    df_raw = df_raw.copy()
    df_raw["_year"] = df_raw["billboard_week"].apply(lambda x: x.year)
    if year_start is not None:
        df_raw = df_raw[df_raw["_year"] >= year_start]
    if year_end is not None:
        df_raw = df_raw[df_raw["_year"] <= year_end]
    df_filtered = df_raw.copy()

    all_weeks_asc = sorted(df_filtered["billboard_week"].unique().tolist())
    all_weeks_desc = sorted(all_weeks_asc, reverse=True)

    _agg_tracks, _agg_albums, _agg_artists = _try_load_from_agg(
        min_ms,
        music_only,
        bb_week_start_dow,
        bb_week_start_hour,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
    )

    if _agg_tracks is not None:
        y0, y1 = year_start or 1900, year_end or 2100
        _agg_tracks = _agg_tracks[
            pd.to_datetime(_agg_tracks["billboard_week"]).dt.year.between(y0, y1)
        ]
        _agg_albums = _agg_albums[
            pd.to_datetime(_agg_albums["billboard_week"]).dt.year.between(y0, y1)
        ]
        _agg_artists = _agg_artists[
            pd.to_datetime(_agg_artists["billboard_week"]).dt.year.between(y0, y1)
        ]

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

    return weekly, weekly_album, weekly_artist, all_weeks_asc, all_weeks_desc, df_filtered


@lru_cache(maxsize=4)
def _compute_weekly_data_cached(
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
    weekly, weekly_album, weekly_artist, all_weeks_asc, all_weeks_desc, df_filtered = (
        _load_and_rank(
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
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            include_compilations=include_compilations,
        )
    )

    from backend.domains.billboard.records import _add_cover_urls  # noqa: E402

    weekly, weekly_album, weekly_artist = _add_cover_urls(weekly, weekly_album, weekly_artist)
    weekly = enrich_track_artist_names(weekly)

    date_cols_week = ["billboard_week"]
    return {
        "meta": {
            "total_weeks": len(all_weeks_asc),
            "total_filtered_records": int(len(df_filtered)),
            "all_weeks_asc": [w.isoformat() for w in all_weeks_asc],
            "all_weeks_desc": [w.isoformat() for w in all_weeks_desc],
            "dow_name": DOW_NAMES[bb_week_start_dow],
            "dow_short": DOW_SHORT[bb_week_start_dow],
            "top_n": bb_top_n,
            "album_top_n": bb_album_top_n,
            "artist_top_n": bb_artist_top_n,
            "week_start_dow": bb_week_start_dow,
            "week_start_hour": bb_week_start_hour,
        },
        "weekly": _df_to_json(weekly, date_cols_week),
        "weekly_album": _df_to_json(weekly_album, date_cols_week),
        "weekly_artist": _df_to_json(weekly_artist, date_cols_week),
    }


@lru_cache(maxsize=4)
def _compute_power_scores_cached(
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
):
    weekly, weekly_album, weekly_artist, *_ = _load_and_rank(
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
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
    )

    weekly = enrich_track_artist_names(weekly)

    power_scores = compute_power_scores(weekly, bb_top_n)
    album_power_scores = compute_album_power_scores(weekly_album, bb_album_top_n)
    artist_power_scores = compute_artist_power_scores(weekly_artist, bb_artist_top_n)

    return {
        "power_scores": _df_to_json(power_scores),
        "album_power_scores": _df_to_json(album_power_scores),
        "artist_power_scores": _df_to_json(artist_power_scores),
    }


@lru_cache(maxsize=4)
def _compute_summaries_cached(
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
):
    weekly, weekly_album, weekly_artist, *_all_weeks, df_filtered = _load_and_rank(
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
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
    )

    album_map = load_track_album_map()
    date_cols_week = ["billboard_week", "first_week", "last_week", "first_peak_week"]

    track_summary = compute_track_summary(weekly, df_filtered)
    artist_summary = compute_artist_summary(weekly)
    artist_track_counts = compute_artist_track_counts(
        artist_summary, track_summary, weekly_album, weekly_artist
    )
    album_track_counts, _track_per_album = compute_album_track_counts(
        track_summary, album_map, weekly_album
    )

    track_summary = enrich_track_artist_names(track_summary)

    return {
        "track_summary": _df_to_json(track_summary, date_cols_week),
        "artist_summary": _df_to_json(artist_summary, date_cols_week),
        "album_track_counts": _df_to_json(album_track_counts),
        "artist_track_counts": _df_to_json(artist_track_counts),
    }


@lru_cache(maxsize=4)
def _compute_records_cached(
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
):
    weekly, weekly_album, weekly_artist, *_all_weeks, df_filtered = _load_and_rank(
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
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
    )

    track_summary = compute_track_summary(weekly, df_filtered)
    power_scores = compute_power_scores(weekly, bb_top_n)
    album_power_scores = compute_album_power_scores(weekly_album, bb_album_top_n)
    artist_power_scores = compute_artist_power_scores(weekly_artist, bb_artist_top_n)

    weekly = enrich_track_artist_names(weekly)
    track_summary = enrich_track_artist_names(track_summary)

    from backend.domains.billboard.records import _serialize_records, compute_records  # noqa: E402

    records = compute_records(
        weekly,
        track_summary,
        bb_top_n,
        weekly_album=weekly_album,
        weekly_artist=weekly_artist,
        track_power_scores=power_scores,
        album_power_scores=album_power_scores,
        artist_power_scores=artist_power_scores,
    )

    return {"records": _serialize_records(records)}
