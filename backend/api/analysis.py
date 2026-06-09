"""Playback analysis API endpoints."""

from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, Query

from backend.dependencies import PlayFilters, get_conn
from backend.models.analysis import (
    AnalysisChartsResponse,
    AnalysisOverviewResponse,
    AnalysisPlayDateEntry,
    AnalysisPlaysResponse,
    AnalysisStatsResponse,
)
from backend.services.analysis_service import get_analysis_overview
from backend.services.analysis_stats_service import (
    get_analysis_charts,
    get_analysis_stats,
    get_global_play_dates,
    get_global_plays,
)

router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.get("/overview", response_model=AnalysisOverviewResponse)
def analysis_overview(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_analysis_overview(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
    )


@router.get("/stats", response_model=AnalysisStatsResponse)
def analysis_stats(
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    return get_analysis_stats(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        period,
        start_date,
        end_date,
    )


@router.get("/charts", response_model=AnalysisChartsResponse)
def analysis_charts(
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    entity: str = Query(default="track"),
    metric: str = Query(default="plays"),
    limit: int = Query(default=100, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    conn: Connection = Depends(get_conn),
):
    return get_analysis_charts(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        period,
        start_date,
        end_date,
        entity,
        metric,
        limit,
        offset,
    )


@router.get("/plays", response_model=AnalysisPlaysResponse)
def analysis_plays(
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
    return get_global_plays(
        conn,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        period=period,
        start_date=start_date,
        end_date=end_date,
        search=search,
        date=date,
        limit=limit,
        offset=offset,
    )


@router.get("/play-dates", response_model=list[AnalysisPlayDateEntry])
def analysis_play_dates(
    filters: PlayFilters = Depends(),
    period: str = Query(default="lifetime"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    conn: Connection = Depends(get_conn),
):
    return get_global_play_dates(
        conn,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )
