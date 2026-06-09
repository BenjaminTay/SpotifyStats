"""Core Billboard computation pipeline — orchestration, caching, and staged API."""

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


@lru_cache(maxsize=8)
def _compute_billboard_data_cached(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
):
    """Compute all Billboard data in one call.

    Returns a dict with all DataFrames converted to JSON-safe lists of dicts.
    This single function replaces the 15+ DataFrame computation pipeline
    previously done in Streamlit's billboard/__init__.py:run().

    Parameters
    ----------
    min_ms : int
        Minimum play duration in milliseconds.
    music_only : bool
        Exclude podcasts/audiobooks.
    bb_top_n : int
        Number of tracks per week in the singles chart.
    bb_album_top_n : int
        Number of albums per week in the albums chart.
    bb_artist_top_n : int
        Number of artists per week in the artists chart.
    bb_week_start_dow : int
        Day of week (0=Mon, 6=Sun) that starts a Billboard week.
    bb_week_start_hour : int
        Hour (0-23) that starts a Billboard week.
    year_start : int or None
        Filter to this year and later (inclusive).
    year_end : int or None
        Filter to this year and earlier (inclusive).

    Returns
    -------
    dict with keys:
        meta, weekly, weekly_album, weekly_artist,
        track_summary, artist_summary, artist_track_counts,
        album_track_counts, track_per_album,
        records, power_scores, album_power_scores, artist_power_scores
    """
    # ── Load, filter, rank (shared with staged functions) ─────────────
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
        )
    )

    album_map = load_track_album_map()

    # ── Summaries ──────────────────────────────────────────────────────
    track_summary = compute_track_summary(weekly, df_filtered)
    artist_summary = compute_artist_summary(weekly)
    artist_track_counts = compute_artist_track_counts(
        artist_summary, track_summary, weekly_album, weekly_artist
    )
    album_track_counts, track_per_album = compute_album_track_counts(
        track_summary, album_map, weekly_album
    )

    # ── Enrich track artist_name with featured artists ────────────────────
    weekly = enrich_track_artist_names(weekly)
    track_summary = enrich_track_artist_names(track_summary)

    # ── Power scores (compute before records to avoid double work) ──────
    power_scores = compute_power_scores(weekly, bb_top_n)
    album_power_scores = compute_album_power_scores(weekly_album, bb_album_top_n)
    artist_power_scores = compute_artist_power_scores(weekly_artist, bb_artist_top_n)

    # ── Records ────────────────────────────────────────────────────────
    from backend.domains.billboard.records import (  # noqa: E402
        _add_cover_urls,
        _serialize_records,
        compute_records,
    )

    records = compute_records(
        weekly,
        track_summary,
        bb_top_n,
        weekly_album,
        weekly_artist,
        track_power_scores=power_scores,
        album_power_scores=album_power_scores,
        artist_power_scores=artist_power_scores,
    )

    # ── Enrich with cover URLs ───────────────────────────────────────
    weekly, weekly_album, weekly_artist = _add_cover_urls(weekly, weekly_album, weekly_artist)

    # ── Convert to JSON-safe format ────────────────────────────────────
    date_cols_week = ["billboard_week", "first_week", "last_week", "first_peak_week"]

    result = {
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
        "weekly_album": _df_to_json(weekly_album, ["billboard_week"]),
        "weekly_artist": _df_to_json(weekly_artist, ["billboard_week"]),
        "track_summary": _df_to_json(track_summary, date_cols_week),
        "artist_summary": _df_to_json(artist_summary, date_cols_week),
        "artist_track_counts": _df_to_json(artist_track_counts),
        "album_track_counts": _df_to_json(album_track_counts),
        "track_per_album": _df_to_json(track_per_album, date_cols_week),
        "records": _serialize_records(records),
        "power_scores": _df_to_json(power_scores),
        "album_power_scores": _df_to_json(album_power_scores),
        "artist_power_scores": _df_to_json(artist_power_scores),
    }

    return result


def compute_billboard_data(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
):
    """Compute all Billboard data with normalized cache keys."""
    return _compute_billboard_data_cached(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )


compute_billboard_data.cache_clear = _compute_billboard_data_cached.cache_clear  # type: ignore[attr-defined]
compute_billboard_data.cache_info = _compute_billboard_data_cached.cache_info  # type: ignore[attr-defined]


# ═══════════════════════════════════════════════════════════════════════════
# Staged computation functions — independent @lru_cache per data slice
# ═══════════════════════════════════════════════════════════════════════════


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
):
    """Shared helper: load raw data, apply filters, compute weekly rankings.

    NOT cached (returns mutable DataFrames), but inner data loading functions
    (load_billboard_raw, _try_load_from_agg) are independently cached.

    Returns (weekly, weekly_album, weekly_artist, all_weeks_asc, all_weeks_desc, df_filtered).
    """
    df_raw = load_billboard_raw(min_ms, music_only, bb_week_start_dow, bb_week_start_hour)

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
        min_ms, music_only, bb_week_start_dow, bb_week_start_hour
    )

    if _agg_tracks is not None:
        _agg_tracks = _agg_tracks[
            pd.to_datetime(_agg_tracks["billboard_week"]).dt.year.between(
                year_start or 1900, year_end or 2100
            )
        ]
        _agg_albums = _agg_albums[
            pd.to_datetime(_agg_albums["billboard_week"]).dt.year.between(
                year_start or 1900, year_end or 2100
            )
        ]
        _agg_artists = _agg_artists[
            pd.to_datetime(_agg_artists["billboard_week"]).dt.year.between(
                year_start or 1900, year_end or 2100
            )
        ]

    weekly = compute_weekly_rankings(df_filtered, bb_top_n, pre_agg=_agg_tracks)
    weekly_album = compute_album_weekly_rankings(df_filtered, bb_album_top_n, pre_agg=_agg_albums)

    if _agg_artists is not None:
        weekly_artist = compute_artist_weekly_rankings(
            df_filtered, bb_artist_top_n, pre_agg=_agg_artists
        )
    else:
        df_artists = load_billboard_raw_for_artists(
            min_ms, music_only, bb_week_start_dow, bb_week_start_hour
        )
        df_artists = df_artists.copy()
        df_artists["_year"] = df_artists["billboard_week"].apply(lambda x: x.year)
        if year_start is not None:
            df_artists = df_artists[df_artists["_year"] >= year_start]
        if year_end is not None:
            df_artists = df_artists[df_artists["_year"] <= year_end]
        weekly_artist = compute_artist_weekly_rankings(df_artists, bb_artist_top_n)

    # Patch tracks_count from weekly when using pre-agg
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

    # Albums count per artist from album chart
    _artist_ac = (
        weekly_album.groupby(["billboard_week", "artist_name"])
        .agg(albums_count=("album_name", "nunique"))
        .reset_index()
    )
    weekly_artist = weekly_artist.merge(
        _artist_ac, on=["billboard_week", "artist_name"], how="left"
    )
    weekly_artist["albums_count"] = weekly_artist["albums_count"].fillna(0).astype(int)

    # Running metrics
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
):
    """Compute weekly rankings + meta. Returns JSON-safe dict."""
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
):
    """Compute power scores for tracks, albums, and artists. Returns JSON-safe dict."""
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
):
    """Compute track/artist/album summaries. Returns JSON-safe dict."""
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
):
    """Compute Billboard records. Returns JSON-safe dict."""
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


# Public wrappers with normalized cache keys


def compute_weekly_data(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
):
    """Compute weekly rankings + meta only (no summaries, no records)."""
    return _compute_weekly_data_cached(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )


def compute_power_scores_staged(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
):
    """Compute power scores only (track, album, artist)."""
    return _compute_power_scores_cached(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )


def compute_summaries_staged(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
):
    """Compute summaries only (track_summary, artist_summary, album/artist track counts)."""
    return _compute_summaries_cached(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )


def compute_records_staged(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
):
    """Compute records only."""
    return _compute_records_cached(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
    )


compute_weekly_data.cache_clear = _compute_weekly_data_cached.cache_clear  # type: ignore[attr-defined]
compute_power_scores_staged.cache_clear = _compute_power_scores_cached.cache_clear  # type: ignore[attr-defined]
compute_summaries_staged.cache_clear = _compute_summaries_cached.cache_clear  # type: ignore[attr-defined]
compute_records_staged.cache_clear = _compute_records_cached.cache_clear  # type: ignore[attr-defined]

# ── Cache registration ─────────────────────────────────────────────────
from backend.core.cache_manager import register_lru  # noqa: E402

register_lru("billboard", "full_data", _compute_billboard_data_cached)
register_lru("billboard", "weekly", _compute_weekly_data_cached)
register_lru("billboard", "power_scores", _compute_power_scores_cached)
register_lru("billboard", "summaries", _compute_summaries_cached)
register_lru("billboard", "records", _compute_records_cached)
