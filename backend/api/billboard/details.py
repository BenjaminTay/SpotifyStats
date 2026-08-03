"""Billboard detail and versus endpoints.

GET /billboard/track/{track_id}      — track chart history with change column
GET /billboard/artist/{name}         — artist chart detail with tracks/albums
GET /billboard/album/{name}          — album chart detail with tracks
GET /billboard/entity-lists          — entity lists for versus search pickers
GET /billboard/versus/track          — compare two tracks (legacy)
GET /billboard/versus/album          — compare two albums (legacy)
GET /billboard/versus/artist         — compare two artists (legacy)
POST /billboard/versus/track         — compare multiple tracks (2–5)
POST /billboard/versus/album         — compare multiple albums (2–5)
POST /billboard/versus/artist        — compare multiple artists (2–5)
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.dependencies import BillboardFilters, MergeConfig
from backend.services.billboard_service import (
    get_album_chart_detail,
    get_artist_chart_detail,
    get_billboard_entity_lists,
    get_track_history,
    get_versus_album,
    get_versus_album_multi,
    get_versus_artist,
    get_versus_artist_multi,
    get_versus_track,
    get_versus_track_multi,
)

router = APIRouter()


class TrackHistoryResponse(BaseModel):
    model_config = {"extra": "allow"}
    found: bool
    chart_status: Literal["charted", "not_charted"] | None = None
    effective_play_count: int | None = None
    track_id: int | None = None
    track_name: str | None = None
    artist_name: str | None = None
    artist_names: list[str] | None = None
    cover_url: str | None = None
    meta: dict | None = None
    summary: dict | None = None
    history: list[dict] | None = None
    chart_data: dict | None = None


class ArtistChartDetailResponse(BaseModel):
    model_config = {"extra": "allow"}
    found: bool
    chart_status: Literal["charted", "not_charted"] | None = None
    track_chart_status: Literal["charted", "not_charted"] | None = None
    album_chart_status: Literal["charted", "not_charted"] | None = None
    effective_play_count: int | None = None
    artist_name: str | None = None
    cover_url: str | None = None
    meta: dict | None = None
    info: dict | None = None
    chart_summary: dict | None = None
    artist_weekly_history: list[dict] | None = None
    artist_no1_by_week: list[dict] | None = None
    week_no1_albums: list[dict] | None = None
    best_singles_overlay: list[dict] | None = None
    best_albums_overlay: list[dict] | None = None
    tracks: list[dict] | None = None
    albums: list[dict] | None = None


class AlbumChartDetailResponse(BaseModel):
    model_config = {"extra": "allow"}
    found: bool
    chart_status: Literal["charted", "not_charted"] | None = None
    track_chart_status: Literal["charted", "not_charted"] | None = None
    effective_play_count: int | None = None
    album_name: str | None = None
    artist_name: str | None = None
    cover_url: str | None = None
    meta: dict | None = None
    info: dict | None = None
    chart_summary: dict | None = None
    album_project: dict | None = None
    album_weekly_history: list[dict] | None = None
    album_no1_by_week: list[dict] | None = None
    best_singles_overlay: list[dict] | None = None
    tracks: list[dict] | None = None


class EntityListsResponse(BaseModel):
    tracks: list[dict]
    albums: list[dict]
    artists: list[dict]


class VersusEntity(BaseModel):
    model_config = {"extra": "allow"}
    name: str | None = None
    cover_url: str | None = None
    popularity: int | None = None
    genres: list[str] | None = None
    genre_source: str | None = None
    genre_confidence: float | None = None
    rank_history: list[dict] | None = None
    metrics: dict | None = None


class VersusResponse(BaseModel):
    model_config = {"extra": "allow"}
    found: bool
    reason: str | None = None
    entity_a: VersusEntity | None = None
    entity_b: VersusEntity | None = None
    head_to_head: list[dict] | None = None


# ── Multi-entity versus models ──


class MultiVersusEntity(BaseModel):
    model_config = {"extra": "allow"}
    name: str | None = None
    cover_url: str | None = None
    popularity: int | None = None
    genres: list[str] | None = None
    genre_source: str | None = None
    genre_confidence: float | None = None
    rank_history: list[dict] | None = None
    metrics: dict | None = None


class MultiVersusResponse(BaseModel):
    model_config = {"extra": "allow"}
    found: bool
    reason: str | None = None
    entities: list[MultiVersusEntity] | None = None


# ── Multi-entity request bodies ──


class TrackMultiRequest(BaseModel):
    track_ids: list[int]


class AlbumMultiRequest(BaseModel):
    albums: list[dict]


class ArtistMultiRequest(BaseModel):
    artist_names: list[str]


@router.get(
    "/track/{track_id}",
    response_model=TrackHistoryResponse,
    responses={404: {"description": "Track has no resolvable chart or effective-play facts"}},
)
def track_history(
    track_id: int,
    filters: BillboardFilters = Depends(),
    merge: MergeConfig = Depends(),
    include_compilations: bool = Query(False),
):
    """Get detailed track chart history with change column and gapped chart data."""
    result = get_track_history(
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
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
        merge_enabled=filters.merge_enabled,
        merge_level=merge.merge_level,
        include_compilations=include_compilations,
    )
    if not result.get("found"):
        raise HTTPException(status_code=404, detail="Track not found")
    return result


@router.get(
    "/artist/{artist_name:path}",
    response_model=ArtistChartDetailResponse,
    responses={404: {"description": "Artist has no resolvable chart or effective-play facts"}},
)
def artist_chart_detail(
    artist_name: str,
    filters: BillboardFilters = Depends(),
    merge: MergeConfig = Depends(),
    include_compilations: bool = Query(False),
):
    """Get detailed artist chart data: weekly history, track/album performances, trend overlay."""
    result = get_artist_chart_detail(
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
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
        merge_enabled=filters.merge_enabled,
        merge_level=merge.merge_level,
        include_compilations=include_compilations,
    )
    if not result.get("found"):
        raise HTTPException(status_code=404, detail="Artist not found")
    return result


@router.get(
    "/album/{album_name:path}",
    response_model=AlbumChartDetailResponse,
    responses={404: {"description": "Album has no resolvable chart or effective-play facts"}},
)
def album_chart_detail(
    album_name: str,
    artist_name: str = Query(default="", description="Artist name for disambiguation"),
    filters: BillboardFilters = Depends(),
    merge: MergeConfig = Depends(),
    include_compilations: bool = Query(False),
):
    """Get detailed album chart data: weekly history, track performances, trend overlay."""
    result = get_album_chart_detail(
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
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
        merge_enabled=filters.merge_enabled,
        merge_level=merge.merge_level,
        include_compilations=include_compilations,
    )
    if not result.get("found"):
        raise HTTPException(status_code=404, detail="Album not found")
    return result


@router.get("/entity-lists", response_model=EntityListsResponse)
def entity_lists(
    search: str | None = Query(
        default=None, description="Filter entities by name (case-insensitive)"
    ),
    filters: BillboardFilters = Depends(),
    merge: MergeConfig = Depends(),
    include_compilations: bool = Query(False),
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
        search=search,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
        merge_level=merge.merge_level,
        include_compilations=include_compilations,
    )


# ── Versus ───────────────────────────────────────────────────────────────────


@router.get("/versus/track", response_model=VersusResponse)
def versus_track(
    track_id_a: int = Query(..., description="Track A ID"),
    track_id_b: int = Query(..., description="Track B ID"),
    filters: BillboardFilters = Depends(),
    merge: MergeConfig = Depends(),
    include_compilations: bool = Query(False),
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
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
        merge_level=merge.merge_level,
        include_compilations=include_compilations,
    )


@router.get("/versus/album", response_model=VersusResponse)
def versus_album(
    album_a: str = Query(..., description="Album A name"),
    artist_a: str = Query(..., description="Album A artist"),
    album_b: str = Query(..., description="Album B name"),
    artist_b: str = Query(..., description="Album B artist"),
    filters: BillboardFilters = Depends(),
    merge: MergeConfig = Depends(),
    include_compilations: bool = Query(False),
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
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
        merge_level=merge.merge_level,
        include_compilations=include_compilations,
    )


@router.get("/versus/artist", response_model=VersusResponse)
def versus_artist(
    artist_a: str = Query(..., description="Artist A name"),
    artist_b: str = Query(..., description="Artist B name"),
    filters: BillboardFilters = Depends(),
    merge: MergeConfig = Depends(),
    include_compilations: bool = Query(False),
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
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
        merge_level=merge.merge_level,
        include_compilations=include_compilations,
    )


# ── Multi-entity versus (POST) ──


@router.post("/versus/track", response_model=MultiVersusResponse)
def versus_track_multi(
    body: TrackMultiRequest,
    filters: BillboardFilters = Depends(),
    merge: MergeConfig = Depends(),
    include_compilations: bool = Query(False),
):
    """Compare multiple tracks side-by-side (2–5)."""
    return get_versus_track_multi(
        track_ids=body.track_ids,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        bb_top_n=filters.bb_top_n,
        bb_album_top_n=filters.bb_album_top_n,
        bb_artist_top_n=filters.bb_artist_top_n,
        bb_week_start_dow=filters.bb_week_start_dow,
        bb_week_start_hour=filters.bb_week_start_hour,
        year_start=filters.year_start,
        year_end=filters.year_end,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
        merge_level=merge.merge_level,
        include_compilations=include_compilations,
    )


@router.post("/versus/album", response_model=MultiVersusResponse)
def versus_album_multi(
    body: AlbumMultiRequest,
    filters: BillboardFilters = Depends(),
    merge: MergeConfig = Depends(),
    include_compilations: bool = Query(False),
):
    """Compare multiple albums side-by-side (2–5)."""
    return get_versus_album_multi(
        albums=body.albums,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        bb_top_n=filters.bb_top_n,
        bb_album_top_n=filters.bb_album_top_n,
        bb_artist_top_n=filters.bb_artist_top_n,
        bb_week_start_dow=filters.bb_week_start_dow,
        bb_week_start_hour=filters.bb_week_start_hour,
        year_start=filters.year_start,
        year_end=filters.year_end,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
        merge_level=merge.merge_level,
        include_compilations=include_compilations,
    )


@router.post("/versus/artist", response_model=MultiVersusResponse)
def versus_artist_multi(
    body: ArtistMultiRequest,
    filters: BillboardFilters = Depends(),
    merge: MergeConfig = Depends(),
    include_compilations: bool = Query(False),
):
    """Compare multiple artists side-by-side (2–5)."""
    return get_versus_artist_multi(
        artist_names=body.artist_names,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        bb_top_n=filters.bb_top_n,
        bb_album_top_n=filters.bb_album_top_n,
        bb_artist_top_n=filters.bb_artist_top_n,
        bb_week_start_dow=filters.bb_week_start_dow,
        bb_week_start_hour=filters.bb_week_start_hour,
        year_start=filters.year_start,
        year_end=filters.year_end,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
        merge_level=merge.merge_level,
        include_compilations=include_compilations,
    )
