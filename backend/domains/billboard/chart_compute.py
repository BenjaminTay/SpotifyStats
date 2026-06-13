"""Core Billboard computation pipeline — orchestration, caching, and staged API."""

from functools import lru_cache

from backend.core.db import enrich_track_artist_names
from backend.core.json_helpers import df_to_json as _df_to_json
from backend.domains.billboard.chart_power_score import (
    compute_album_power_scores,
    compute_artist_power_scores,
    compute_power_scores,
)
from backend.domains.billboard.chart_ranking import (
    compute_album_weekly_rankings as compute_album_weekly_rankings,  # noqa: F401
)
from backend.domains.billboard.chart_ranking import (
    compute_artist_weekly_rankings as compute_artist_weekly_rankings,  # noqa: F401
)
from backend.domains.billboard.chart_ranking import (
    compute_weekly_rankings as compute_weekly_rankings,  # noqa: F401
)
from backend.domains.billboard.chart_staged_api import (
    compute_power_scores_staged as compute_power_scores_staged,  # noqa: F401
)
from backend.domains.billboard.chart_staged_api import (
    compute_records_staged as compute_records_staged,  # noqa: F401
)
from backend.domains.billboard.chart_staged_api import (
    compute_summaries_staged as compute_summaries_staged,  # noqa: F401
)
from backend.domains.billboard.chart_staged_api import (
    compute_weekly_data as compute_weekly_data,  # noqa: F401
)
from backend.domains.billboard.chart_staged_cache import (
    _compute_power_scores_cached,
    _compute_records_cached,
    _compute_summaries_cached,
    _compute_weekly_data_cached,
    _load_and_rank,
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
    merge_level=2,
    dynamic_threshold=False,
    max_merge_gap_minutes=None,
    include_compilations=False,
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
    dict with keys: meta, weekly, weekly_album, weekly_artist,
    track_summary, artist_summary, artist_track_counts,
    album_track_counts, track_per_album, records, power_scores,
    album_power_scores, artist_power_scores
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
            merge_level,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            include_compilations=include_compilations,
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
    merge_level=2,
    dynamic_threshold=False,
    max_merge_gap_minutes=None,
    include_compilations=False,
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
        merge_level,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        include_compilations=include_compilations,
    )


compute_billboard_data.cache_clear = _compute_billboard_data_cached.cache_clear  # type: ignore[attr-defined]
compute_billboard_data.cache_info = _compute_billboard_data_cached.cache_info  # type: ignore[attr-defined]

# ── Cache registration ─────────────────────────────────────────────────
from backend.core.cache_manager import register_lru  # noqa: E402

register_lru("billboard", "full_data", _compute_billboard_data_cached)
register_lru("billboard", "weekly", _compute_weekly_data_cached)
register_lru("billboard", "power_scores", _compute_power_scores_cached)
register_lru("billboard", "summaries", _compute_summaries_cached)
register_lru("billboard", "records", _compute_records_cached)
