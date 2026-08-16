"""Public staged Billboard Year-End API wrapper."""

from backend.domains.billboard.chart_year_end_cache import _compute_year_end_cached
from backend.domains.billboard.year_end import (
    YEAR_END_ALBUM_TOP_N,
    YEAR_END_ARTIST_TOP_N,
    YEAR_END_TRACK_TOP_N,
)


def compute_year_end_staged(
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
        merge_enabled=merge_enabled,
        year_end_top_n=year_end_top_n,
        year_end_album_top_n=year_end_album_top_n,
        year_end_artist_top_n=year_end_artist_top_n,
    )


compute_year_end_staged.cache_clear = _compute_year_end_cached.cache_clear  # type: ignore[attr-defined]
