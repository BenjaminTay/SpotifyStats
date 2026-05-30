"""Billboard data endpoints — full data + staged slices.

GET /api/billboard/data        — all data (backward compatible, ~5MB)
GET /api/billboard/weekly      — meta + weekly/weekly_album/weekly_artist (~1.5MB)
GET /api/billboard/records     — records only (~800KB)
GET /api/billboard/power-scores — power_scores + album/artist variants (~200KB)
GET /api/billboard/summaries   — track_summary + artist_summary + counts (~300KB)
GET /api/billboard/all-time    — power-scores + summaries + weekly (~2MB)
"""

from fastapi import APIRouter, Depends

from backend.dependencies import BillboardFilters
from backend.services.billboard_service import (
    compute_billboard_data,
    compute_power_scores_staged,
    compute_records_staged,
    compute_summaries_staged,
    compute_weekly_data,
)

router = APIRouter()


def _billboard_params(filters: BillboardFilters):
    """Extract Billboard computation params from filters."""
    return dict(
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        bb_top_n=filters.bb_top_n,
        bb_album_top_n=filters.bb_album_top_n,
        bb_artist_top_n=filters.bb_artist_top_n,
        bb_week_start_dow=filters.bb_week_start_dow,
        bb_week_start_hour=filters.bb_week_start_hour,
        year_start=filters.year_start,
        year_end=filters.year_end,
    )


@router.get("/data")
def get_billboard_data(filters: BillboardFilters = Depends()):
    """Compute all Billboard chart data in a single request.

    Returns weekly rankings, track/artist/album summaries, records,
    and power scores. Kept for backward compatibility.
    """
    return compute_billboard_data(**_billboard_params(filters))


@router.get("/weekly")
def get_billboard_weekly(filters: BillboardFilters = Depends()):
    """Weekly rankings + meta only — used by BillboardPage.

    Returns meta, weekly (tracks), weekly_album, weekly_artist.
    """
    return compute_weekly_data(**_billboard_params(filters))


@router.get("/records")
def get_billboard_records(filters: BillboardFilters = Depends()):
    """Billboard records only — used by RecordsPage.

    Returns all 37 records across 6 sections.
    """
    return compute_records_staged(**_billboard_params(filters))


@router.get("/power-scores")
def get_billboard_power_scores(filters: BillboardFilters = Depends()):
    """Power scores for tracks, albums, and artists.

    Returns power_scores, album_power_scores, artist_power_scores
    each with power_rank, weeks_top5, weeks_top10.
    """
    return compute_power_scores_staged(**_billboard_params(filters))


@router.get("/summaries")
def get_billboard_summaries(filters: BillboardFilters = Depends()):
    """Track/artist/album summaries and counts.

    Returns track_summary, artist_summary, album_track_counts,
    artist_track_counts.
    """
    return compute_summaries_staged(**_billboard_params(filters))


@router.get("/all-time")
def get_billboard_all_time(filters: BillboardFilters = Depends()):
    """Combined data for all-time charts pages.

    Returns power-scores + summaries + weekly data.
    Used by NumberOnesPage and AllTimeChartsPage.
    """
    params = _billboard_params(filters)
    weekly = compute_weekly_data(**params)
    power = compute_power_scores_staged(**params)
    summaries = compute_summaries_staged(**params)
    return {**weekly, **power, **summaries}
