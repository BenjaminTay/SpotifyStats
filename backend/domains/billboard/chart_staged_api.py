from backend.domains.billboard.chart_load_rank import call_with_billboard_revision_cache
from backend.domains.billboard.chart_staged_cache import (
    _compute_power_scores_cached,
    _compute_records_cached,
    _compute_summaries_cached,
    _compute_weekly_data_cached,
)


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
    merge_level=2,
    dynamic_threshold=False,
    max_merge_gap_minutes=5,
    include_compilations=False,
):
    args = (
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
    return call_with_billboard_revision_cache(_compute_weekly_data_cached, args)


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
    merge_level=2,
    dynamic_threshold=False,
    max_merge_gap_minutes=5,
    include_compilations=False,
):
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
        merge_level,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        include_compilations=include_compilations,
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
    merge_level=2,
    dynamic_threshold=False,
    max_merge_gap_minutes=5,
    include_compilations=False,
):
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
        merge_level,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        include_compilations=include_compilations,
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
    merge_level=2,
    dynamic_threshold=False,
    max_merge_gap_minutes=5,
):
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
        merge_level,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
    )


compute_weekly_data.cache_clear = _compute_weekly_data_cached.cache_clear  # type: ignore[attr-defined]
compute_power_scores_staged.cache_clear = _compute_power_scores_cached.cache_clear  # type: ignore[attr-defined]
compute_summaries_staged.cache_clear = _compute_summaries_cached.cache_clear  # type: ignore[attr-defined]
compute_records_staged.cache_clear = _compute_records_cached.cache_clear  # type: ignore[attr-defined]
