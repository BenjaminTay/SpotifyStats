"""Listening hours API endpoint."""

from sqlite3 import Connection

from fastapi import APIRouter, Depends

from backend.dependencies import PlayFilters, get_conn
from backend.models.behavior import (
    HeatmapResponse,
    LateNightEntry,
    PlatformHourlyListeningResponse,
    WeekdayWeekendResponse,
    YearlyHeatmapEntry,
)
from backend.services.play_service import (
    get_late_night_ratio,
    get_listening_heatmap,
    get_platform_hourly_listening,
    get_weekday_weekend_comparison,
    get_yearly_heatmaps,
)

router = APIRouter(prefix="/listening-hours", tags=["Listening Hours"])


@router.get("/heatmap", response_model=HeatmapResponse)
def listening_heatmap(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_listening_heatmap(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
    )


@router.get("/yearly", response_model=list[YearlyHeatmapEntry])
def yearly_heatmaps(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_yearly_heatmaps(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
    )


@router.get("/late-night", response_model=list[LateNightEntry])
def late_night(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_late_night_ratio(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
    )


@router.get("/weekday-weekend", response_model=WeekdayWeekendResponse)
def weekday_weekend(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_weekday_weekend_comparison(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
    )


@router.get("/platform-hourly", response_model=PlatformHourlyListeningResponse)
def platform_hourly(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_platform_hourly_listening(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
    )
