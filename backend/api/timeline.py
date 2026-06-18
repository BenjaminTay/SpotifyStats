"""Timeline API endpoints."""

from __future__ import annotations

from sqlite3 import Connection
from typing import Union

from fastapi import APIRouter, Depends, Query

from backend.dependencies import PlayFilters, get_conn
from backend.models.timeline import (
    AnnualTimelinePoint,
    MonthlyTimelinePoint,
    TimelineMonthlyDrilldownResponse,
)
from backend.services.play_service import (
    get_annual_timeline,
    get_monthly_timeline_drilldown,
    get_weekly_timeline,
)

router = APIRouter(prefix="/timeline", tags=["Timeline"])


@router.get("/annual", response_model=list[AnnualTimelinePoint])
def timeline_annual(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_annual_timeline(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
    )


@router.get(
    "/monthly", response_model=Union[list[MonthlyTimelinePoint], TimelineMonthlyDrilldownResponse]
)
def timeline_monthly(
    filters: PlayFilters = Depends(),
    period: str | None = Query(None, description="YYYY-MM for drilldown top5"),
    conn: Connection = Depends(get_conn),
):
    result = get_monthly_timeline_drilldown(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        period,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
    )
    return result


@router.get("/weekly")
def timeline_weekly(
    filters: PlayFilters = Depends(),
    week: str | None = Query(None, description="YYYY-Www for drilldown top5"),
    conn: Connection = Depends(get_conn),
):
    return get_weekly_timeline(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        week,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
    )
