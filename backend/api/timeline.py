"""Timeline API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlite3 import Connection
from typing import Optional

from backend.dependencies import get_conn, PlayFilters
from backend.services.play_service import (
    get_annual_timeline, get_monthly_timeline_drilldown,
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
    period: Optional[str] = Query(None, description="YYYY-MM for drilldown top5"),
    conn: Connection = Depends(get_conn),
):
    return get_monthly_timeline_drilldown(conn, filters.min_ms, filters.music_only, filters.merge_enabled, period)
