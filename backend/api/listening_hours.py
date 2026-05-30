"""Listening hours API endpoint."""

from sqlite3 import Connection

from fastapi import APIRouter, Depends

from backend.dependencies import PlayFilters, get_conn
from backend.services.play_service import (
    get_late_night_ratio,
    get_listening_heatmap,
    get_platform_hourly_listening,
    get_weekday_weekend_comparison,
    get_yearly_heatmaps,
)

router = APIRouter(prefix="/listening-hours", tags=["Listening Hours"])


@router.get("/heatmap")
def listening_heatmap(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_listening_heatmap(conn, filters.min_ms, filters.music_only, filters.merge_enabled)


@router.get("/yearly")
def yearly_heatmaps(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_yearly_heatmaps(conn, filters.min_ms, filters.music_only, filters.merge_enabled)


@router.get("/late-night")
def late_night(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_late_night_ratio(conn, filters.min_ms, filters.music_only, filters.merge_enabled)


@router.get("/weekday-weekend")
def weekday_weekend(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_weekday_weekend_comparison(
        conn, filters.min_ms, filters.music_only, filters.merge_enabled
    )


@router.get("/platform-hourly")
def platform_hourly(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_platform_hourly_listening(
        conn, filters.min_ms, filters.music_only, filters.merge_enabled
    )
