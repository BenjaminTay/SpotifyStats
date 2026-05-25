"""Billboard consolidated data endpoint.

GET /api/billboard/data — returns all computed DataFrames for all 12 tabs
in a single JSON response (gzipped by FastAPI).
"""

from fastapi import APIRouter, Depends

from backend.dependencies import BillboardFilters
from backend.services.billboard_service import compute_billboard_data

router = APIRouter()


@router.get("/data")
def get_billboard_data(filters: BillboardFilters = Depends()):
    """Compute all Billboard chart data in a single request.

    Returns weekly rankings, track/artist/album summaries, records,
    and power scores. The frontend caches this response and 12 tabs
    read from it without additional requests.
    """
    return compute_billboard_data(
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
