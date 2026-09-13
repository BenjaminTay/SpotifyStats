"""Dashboard API endpoints."""

from sqlite3 import Connection

from fastapi import APIRouter, Depends, Query

from backend.dependencies import PlayFilters, get_conn
from backend.models.dashboard import (
    DashboardFullResponse,
    DashboardSummary,
    DowDist,
    PlatformDist,
    RandomTrack,
    TopTrack,
)
from backend.services.play_service import (
    get_dashboard_full,
    get_dashboard_summary,
    get_dow_dist,
    get_platform_dist,
    get_random_track,
    get_top_tracks,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_dashboard_summary(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
    )


@router.get("/full", response_model=DashboardFullResponse)
def dashboard_full(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    """Complete dashboard data — all KPIs, charts, and random track."""
    return get_dashboard_full(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
    )


@router.get("/top-tracks", response_model=list[TopTrack])
def top_tracks_endpoint(
    filters: PlayFilters = Depends(),
    n: int = Query(10),
    conn: Connection = Depends(get_conn),
):
    return get_top_tracks(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        n,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
    )


@router.get("/platform-dist", response_model=list[PlatformDist])
def platform_dist_endpoint(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_platform_dist(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
    )


@router.get("/dow-dist", response_model=list[DowDist])
def dow_dist_endpoint(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_dow_dist(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
    )


@router.get("/random-track", response_model=RandomTrack)
def random_track_endpoint(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_random_track(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
    )
