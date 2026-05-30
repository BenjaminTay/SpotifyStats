"""Billboard detail and versus endpoints.

GET /billboard/track/{track_id}      — track chart history with change column
GET /billboard/artist/{name}         — artist chart detail with tracks/albums
GET /billboard/album/{name}          — album chart detail with tracks
GET /billboard/entity-lists          — entity lists for versus search pickers
GET /billboard/versus/track          — compare two tracks
GET /billboard/versus/album          — compare two albums
GET /billboard/versus/artist         — compare two artists
"""

from fastapi import APIRouter, Depends, Query

from backend.dependencies import BillboardFilters
from backend.services.billboard_service import (
    get_album_chart_detail,
    get_artist_chart_detail,
    get_billboard_entity_lists,
    get_track_history,
    get_versus_album,
    get_versus_artist,
    get_versus_track,
)

router = APIRouter()


@router.get("/track/{track_id}")
def track_history(
    track_id: int,
    filters: BillboardFilters = Depends(),
):
    """Get detailed track chart history with change column and gapped chart data."""
    return get_track_history(
        track_id=track_id,
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


@router.get("/artist/{artist_name:path}")
def artist_chart_detail(
    artist_name: str,
    filters: BillboardFilters = Depends(),
):
    """Get detailed artist chart data: weekly history, track/album performances, trend overlay."""
    return get_artist_chart_detail(
        artist_name=artist_name,
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


@router.get("/album/{album_name:path}")
def album_chart_detail(
    album_name: str,
    artist_name: str = Query(..., description="Artist name for disambiguation"),
    filters: BillboardFilters = Depends(),
):
    """Get detailed album chart data: weekly history, track performances, trend overlay."""
    return get_album_chart_detail(
        album_name=album_name,
        artist_name=artist_name,
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


@router.get("/entity-lists")
def entity_lists(
    filters: BillboardFilters = Depends(),
):
    """Return track/album/artist lists for versus search pickers."""
    return get_billboard_entity_lists(
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


# ── Versus ───────────────────────────────────────────────────────────────────


@router.get("/versus/track")
def versus_track(
    track_id_a: int = Query(..., description="Track A ID"),
    track_id_b: int = Query(..., description="Track B ID"),
    filters: BillboardFilters = Depends(),
):
    """Compare two tracks side-by-side."""
    return get_versus_track(
        tid_a=track_id_a,
        tid_b=track_id_b,
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


@router.get("/versus/album")
def versus_album(
    album_a: str = Query(..., description="Album A name"),
    artist_a: str = Query(..., description="Album A artist"),
    album_b: str = Query(..., description="Album B name"),
    artist_b: str = Query(..., description="Album B artist"),
    filters: BillboardFilters = Depends(),
):
    """Compare two albums side-by-side."""
    return get_versus_album(
        aname_a=album_a,
        aart_a=artist_a,
        aname_b=album_b,
        aart_b=artist_b,
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


@router.get("/versus/artist")
def versus_artist(
    artist_a: str = Query(..., description="Artist A name"),
    artist_b: str = Query(..., description="Artist B name"),
    filters: BillboardFilters = Depends(),
):
    """Compare two artists side-by-side."""
    return get_versus_artist(
        sel_a=artist_a,
        sel_b=artist_b,
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
