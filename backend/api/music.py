"""Global music entity API endpoints."""

from sqlite3 import Connection
from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.dependencies import PlayFilters, get_conn
from backend.services.entity_stats_service import get_album_stats, get_artist_stats, get_track_stats

router = APIRouter(prefix="/music", tags=["Music"])


@router.get("/tracks/{track_id}/stats")
def track_stats(
    track_id: int,
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    return get_track_stats(
        conn, track_id, filters.min_ms, filters.music_only, filters.merge_enabled,
        period, start_date, end_date,
    )


@router.get("/albums/{album_name}/stats")
def album_stats(
    album_name: str,
    artist: Optional[str] = Query(default=None),
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    return get_album_stats(
        conn, album_name, artist, filters.min_ms, filters.music_only, filters.merge_enabled,
        period, start_date, end_date,
    )


@router.get("/artists/{artist_name}/stats")
def artist_stats(
    artist_name: str,
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    return get_artist_stats(
        conn, artist_name, filters.min_ms, filters.music_only, filters.merge_enabled,
        period, start_date, end_date,
    )


@router.get("/tracks/{track_id}/plays")
def track_plays(
    track_id: int,
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    return get_track_stats(
        conn, track_id, filters.min_ms, filters.music_only, filters.merge_enabled,
        period, start_date, end_date,
    ).get("recent_plays", [])


@router.get("/albums/{album_name}/plays")
def album_plays(
    album_name: str,
    artist: Optional[str] = Query(default=None),
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    return get_album_stats(
        conn, album_name, artist, filters.min_ms, filters.music_only, filters.merge_enabled,
        period, start_date, end_date,
    ).get("recent_plays", [])


@router.get("/artists/{artist_name}/plays")
def artist_plays(
    artist_name: str,
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    return get_artist_stats(
        conn, artist_name, filters.min_ms, filters.music_only, filters.merge_enabled,
        period, start_date, end_date,
    ).get("recent_plays", [])
