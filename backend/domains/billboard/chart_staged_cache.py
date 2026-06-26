"""Staged Billboard cached computations — _load_and_rank, weekly/power/summaries/records."""

from __future__ import annotations

from functools import lru_cache

from backend.core.cache_manager import register_lru
from backend.core.db import enrich_track_artist_names
from backend.core.json_helpers import df_to_json as _df_to_json
from backend.domains.billboard.chart_load_rank import (
    _copy_load_and_rank_result,
    _filtered_record_count,
    _load_and_rank_cached,
)
from backend.domains.billboard.chart_power_score import (
    compute_album_power_scores,
    compute_artist_power_scores,
    compute_power_scores,
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
    load_track_album_map,
)
from backend.domains.billboard.year_end import (
    YEAR_END_ALBUM_TOP_N,
    YEAR_END_ARTIST_TOP_N,
    YEAR_END_TRACK_TOP_N,
    build_year_end_response,
)


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
    return _copy_load_and_rank_result(
        _load_and_rank_cached(
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
    )


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
    weekly, weekly_album, weekly_artist, all_weeks_asc, all_weeks_desc, df_filtered, _abtm = (
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
            "total_filtered_records": _filtered_record_count(df_filtered),
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
    weekly, weekly_album, weekly_artist, *_extra = _load_and_rank(
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
    album_total_map = _extra[-1] if len(_extra) >= 1 else {}

    weekly = enrich_track_artist_names(weekly)

    power_scores = compute_power_scores(weekly, bb_top_n)
    album_power_scores = compute_album_power_scores(weekly_album, bb_album_top_n)
    artist_power_scores = compute_artist_power_scores(weekly_artist, bb_artist_top_n)

    # Inject unfiltered total_plays into album power scores
    if isinstance(album_total_map, dict) and album_total_map:
        album_power_scores["total_plays"] = album_power_scores.apply(
            lambda row: album_total_map.get((row["album_name"], row["artist_name"]), 0),
            axis=1,
        )

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
    weekly, weekly_album, weekly_artist, *_all_weeks, df_filtered, _album_tm = _load_and_rank(
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
    weekly, weekly_album, weekly_artist, *_all_weeks, df_filtered, _album_tm = _load_and_rank(
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


@lru_cache(maxsize=4)
def _compute_year_end_cached(
    min_ms=30000,
    music_only=True,
    bb_top_n=YEAR_END_TRACK_TOP_N,
    bb_album_top_n=YEAR_END_ALBUM_TOP_N,
    bb_artist_top_n=YEAR_END_ARTIST_TOP_N,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year=None,
    merge_level=2,
    dynamic_threshold=False,
    max_merge_gap_minutes=None,
    include_compilations=False,
):
    weekly, weekly_album, weekly_artist, *_extra = _load_and_rank(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        None,
        None,
        merge_level,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        include_compilations=include_compilations,
    )

    from backend.domains.billboard.records import _add_cover_urls  # noqa: E402

    weekly, weekly_album, weekly_artist = _add_cover_urls(weekly, weekly_album, weekly_artist)
    weekly = enrich_track_artist_names(weekly)

    return build_year_end_response(
        weekly=weekly,
        weekly_album=weekly_album,
        weekly_artist=weekly_artist,
        year=year,
        top_n=bb_top_n,
        album_top_n=bb_album_top_n,
        artist_top_n=bb_artist_top_n,
        week_start_dow=bb_week_start_dow,
        week_start_hour=bb_week_start_hour,
    )


register_lru("billboard", "year_end", _compute_year_end_cached)
