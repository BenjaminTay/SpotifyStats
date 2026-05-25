"""Listening hours API endpoint."""

from fastapi import APIRouter, Depends
from sqlite3 import Connection

from backend.dependencies import get_conn, PlayFilters
from backend.services.play_service import (
    get_listening_heatmap, get_yearly_heatmaps, get_late_night_ratio,
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
