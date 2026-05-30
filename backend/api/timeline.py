"""Timeline API endpoints."""

from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, Query

from backend.dependencies import PlayFilters, get_conn
from backend.services.play_service import (
    get_annual_timeline,
    get_monthly_timeline_drilldown,
    get_weekly_timeline,
)

router = APIRouter(prefix="/timeline", tags=["Timeline"])


@router.get("/annual")
def timeline_annual(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_annual_timeline(conn, filters.min_ms, filters.music_only, filters.merge_enabled)


@router.get("/monthly")
def timeline_monthly(
    filters: PlayFilters = Depends(),
    period: str | None = Query(None, description="YYYY-MM for drilldown top5"),
    conn: Connection = Depends(get_conn),
):
    return get_monthly_timeline_drilldown(
        conn, filters.min_ms, filters.music_only, filters.merge_enabled, period
    )


@router.get("/weekly")
def timeline_weekly(
    filters: PlayFilters = Depends(),
    week: str | None = Query(None, description="YYYY-Www for drilldown top5"),
    conn: Connection = Depends(get_conn),
):
    return get_weekly_timeline(
        conn, filters.min_ms, filters.music_only, filters.merge_enabled, week
    )
