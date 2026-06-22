"""Global music entity API endpoints."""

from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.dependencies import PlayFilters, get_conn
from backend.services.entity_stats_service import (
    get_album_stats,
    get_artist_stats,
    get_entity_play_dates,
    get_entity_plays,
    get_track_stats,
)

router = APIRouter(prefix="/music", tags=["Music"])


class EntityStatsResponse(BaseModel):
    model_config = {"extra": "allow"}
    found: bool | None = None
    period: dict | None = None
    entity: dict | None = None
    first_played: str | None = None
    last_played: str | None = None
    ranks: dict | None = None
    recent_plays: list[dict] | None = None
    summary: dict | None = None
    daily_metrics: dict | None = None
    hourly_distribution: list | None = None
    daily_trend: list | None = None
    cumulative_trend: list | None = None
    weekday_distribution: list | None = None
    month_distribution: list | None = None
    year_distribution: list | None = None
    top250_counts: dict | None = None
    track_breakdown: list[dict] | None = None
    top_tracks: list[dict] | None = None
    top_albums: list[dict] | None = None
    recent_50_count: int | None = None


class EntityPlaysResponse(BaseModel):
    total: int
    limit: int
    offset: int
    rows: list[dict]


class PlayDateEntry(BaseModel):
    date: str
    count: int


@router.get("/tracks/{track_id}/stats", response_model=EntityStatsResponse)
def track_stats(
    track_id: int,
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    return get_track_stats(
        conn,
        track_id,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        period,
        start_date,
        end_date,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
    )


@router.get("/albums/{album_name}/stats", response_model=EntityStatsResponse)
def album_stats(
    album_name: str,
    artist: str | None = Query(default=None),
    filters: PlayFilters = Depends(),
    merge_level: int = Query(
        default=2,
        ge=1,
        le=3,
        description="Album project merge level (1=none, 2=recording, 3=composition)",
    ),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    return get_album_stats(
        conn,
        album_name,
        artist,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        period,
        start_date,
        end_date,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
        merge_level=merge_level,
    )


@router.get("/artists/{artist_name}/stats", response_model=EntityStatsResponse)
def artist_stats(
    artist_name: str,
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    return get_artist_stats(
        conn,
        artist_name,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        period,
        start_date,
        end_date,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
    )


@router.get("/tracks/{track_id}/plays", response_model=EntityPlaysResponse)
def track_plays(
    track_id: int,
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    search: str | None = Query(default=None),
    date: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_conn),
):
    return get_entity_plays(
        conn,
        entity="track",
        track_id=track_id,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        merge_enabled=filters.merge_enabled,
        period=period,
        start_date=start_date,
        end_date=end_date,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
        search=search,
        date=date,
        limit=limit,
        offset=offset,
    )


@router.get("/albums/{album_name}/plays", response_model=EntityPlaysResponse)
def album_plays(
    album_name: str,
    artist: str | None = Query(default=None),
    filters: PlayFilters = Depends(),
    merge_level: int = Query(default=2, ge=1, le=3),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    search: str | None = Query(default=None),
    date: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_conn),
):
    return get_entity_plays(
        conn,
        entity="album",
        album_name=album_name,
        artist_name=artist,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        merge_enabled=filters.merge_enabled,
        merge_level=merge_level,
        period=period,
        start_date=start_date,
        end_date=end_date,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
        search=search,
        date=date,
        limit=limit,
        offset=offset,
    )


@router.get("/artists/{artist_name}/plays", response_model=EntityPlaysResponse)
def artist_plays(
    artist_name: str,
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    search: str | None = Query(default=None),
    date: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_conn),
):
    return get_entity_plays(
        conn,
        entity="artist",
        artist_name=artist_name,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        merge_enabled=filters.merge_enabled,
        period=period,
        start_date=start_date,
        end_date=end_date,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
        search=search,
        date=date,
        limit=limit,
        offset=offset,
    )


@router.get("/tracks/{track_id}/play-dates", response_model=list[PlayDateEntry])
def track_play_dates(
    track_id: int,
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    return get_entity_play_dates(
        conn,
        entity="track",
        track_id=track_id,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        merge_enabled=filters.merge_enabled,
        period=period,
        start_date=start_date,
        end_date=end_date,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
    )


@router.get("/albums/{album_name}/play-dates", response_model=list[PlayDateEntry])
def album_play_dates(
    album_name: str,
    artist: str | None = Query(default=None),
    filters: PlayFilters = Depends(),
    merge_level: int = Query(default=2, ge=1, le=3),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    return get_entity_play_dates(
        conn,
        entity="album",
        album_name=album_name,
        artist_name=artist,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        merge_enabled=filters.merge_enabled,
        merge_level=merge_level,
        period=period,
        start_date=start_date,
        end_date=end_date,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
    )


@router.get("/artists/{artist_name}/play-dates", response_model=list[PlayDateEntry])
def artist_play_dates(
    artist_name: str,
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    return get_entity_play_dates(
        conn,
        entity="artist",
        artist_name=artist_name,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        merge_enabled=filters.merge_enabled,
        period=period,
        start_date=start_date,
        end_date=end_date,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
    )
