"""Public staged Billboard chart API wrappers."""

from backend.domains.billboard.chart_staged_cache import (
    _compute_power_scores_cached,
    _compute_records_cached,
    _compute_summaries_cached,
    _compute_weekly_data_cached,
    _compute_year_end_cached,
)
from backend.domains.billboard.year_end import (
    YEAR_END_ALBUM_TOP_N,
    YEAR_END_ARTIST_TOP_N,
    YEAR_END_TRACK_TOP_N,
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
    max_merge_gap_minutes=None,
    include_compilations=False,
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
        merge_level,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        include_compilations=include_compilations,
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
    merge_level=2,
    dynamic_threshold=False,
    max_merge_gap_minutes=None,
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
        merge_level,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
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
    max_merge_gap_minutes=None,
):
    """Compute summaries only."""
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
    max_merge_gap_minutes=None,
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
        merge_level,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
    )


def compute_year_end_staged(
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
    """Compute Billboard Year-End charts for tracks, albums, and artists."""
    return _compute_year_end_cached(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year,
        merge_level,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        include_compilations=include_compilations,
    )


compute_weekly_data.cache_clear = _compute_weekly_data_cached.cache_clear  # type: ignore[attr-defined]
compute_power_scores_staged.cache_clear = _compute_power_scores_cached.cache_clear  # type: ignore[attr-defined]
compute_summaries_staged.cache_clear = _compute_summaries_cached.cache_clear  # type: ignore[attr-defined]
compute_records_staged.cache_clear = _compute_records_cached.cache_clear  # type: ignore[attr-defined]
compute_year_end_staged.cache_clear = _compute_year_end_cached.cache_clear  # type: ignore[attr-defined]
