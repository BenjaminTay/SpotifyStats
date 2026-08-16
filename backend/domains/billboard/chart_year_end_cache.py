"""Cached Billboard Year-End computation."""

from functools import lru_cache

from backend.core.cache_manager import register_lru
from backend.core.db import enrich_track_artist_names
from backend.domains.billboard.chart_staged_cache import _load_and_rank
from backend.domains.billboard.year_end import (
    YEAR_END_ALBUM_TOP_N,
    YEAR_END_ARTIST_TOP_N,
    YEAR_END_TRACK_TOP_N,
    build_year_end_response,
)

_YEAR_END_UNBOUNDED_TOP_N = 1_000_000


@lru_cache(maxsize=4)
def _compute_year_end_cached(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year=None,
    merge_level=2,
    dynamic_threshold=False,
    max_merge_gap_minutes=5,
    include_compilations=False,
    merge_enabled=True,
    year_end_top_n=YEAR_END_TRACK_TOP_N,
    year_end_album_top_n=YEAR_END_ALBUM_TOP_N,
    year_end_artist_top_n=YEAR_END_ARTIST_TOP_N,
):
    (
        all_weekly,
        all_weekly_album,
        all_weekly_artist,
        _all_weeks_asc,
        _all_weeks_desc,
        df_filtered,
        _album_total_map,
    ) = _load_and_rank(
        min_ms,
        music_only,
        _YEAR_END_UNBOUNDED_TOP_N,
        _YEAR_END_UNBOUNDED_TOP_N,
        _YEAR_END_UNBOUNDED_TOP_N,
        bb_week_start_dow,
        bb_week_start_hour,
        None,
        None,
        merge_level,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        include_compilations=include_compilations,
        merge_enabled=merge_enabled,
    )
    weekly = all_weekly[all_weekly["rank"] <= bb_top_n].copy()
    weekly_album = all_weekly_album[all_weekly_album["rank"] <= bb_album_top_n].copy()
    weekly_artist = all_weekly_artist[all_weekly_artist["rank"] <= bb_artist_top_n].copy()

    from backend.domains.billboard.records import _add_cover_urls

    weekly, weekly_album, weekly_artist = _add_cover_urls(weekly, weekly_album, weekly_artist)
    weekly = enrich_track_artist_names(weekly)

    return build_year_end_response(
        weekly=weekly,
        weekly_album=weekly_album,
        weekly_artist=weekly_artist,
        year=year,
        top_n=year_end_top_n,
        album_top_n=year_end_album_top_n,
        artist_top_n=year_end_artist_top_n,
        week_start_dow=bb_week_start_dow,
        week_start_hour=bb_week_start_hour,
        weekly_top_n=bb_top_n,
        weekly_album_top_n=bb_album_top_n,
        weekly_artist_top_n=bb_artist_top_n,
        all_weekly=all_weekly,
        all_weekly_album=all_weekly_album,
        all_weekly_artist=all_weekly_artist,
        coverage_source=df_filtered,
    )


register_lru("billboard", "year_end", _compute_year_end_cached)
