"""Dashboard API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlite3 import Connection

from backend.dependencies import get_conn, PlayFilters
from backend.services.play_service import (
    get_dashboard_summary,
    get_account_kpis,
    get_monthly_trend,
    get_top_tracks,
    get_platform_dist,
    get_dow_dist,
    get_random_track,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary")
def dashboard_summary(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_dashboard_summary(conn, filters.min_ms, filters.music_only, filters.merge_enabled)


@router.get("/full")
def dashboard_full(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    """Complete dashboard data — all KPIs, charts, and random track in one request."""
    return {
        "summary": get_dashboard_summary(conn, filters.min_ms, filters.music_only, filters.merge_enabled),
        "account_kpis": get_account_kpis(conn),
        "monthly_trend": get_monthly_trend(conn, filters.min_ms, filters.music_only, filters.merge_enabled),
        "top_tracks": get_top_tracks(conn, filters.min_ms, filters.music_only, filters.merge_enabled),
        "platform_dist": get_platform_dist(conn, filters.min_ms, filters.music_only, filters.merge_enabled),
        "dow_dist": get_dow_dist(conn, filters.min_ms, filters.music_only, filters.merge_enabled),
        "random_track": get_random_track(conn, filters.min_ms, filters.music_only),
    }


@router.get("/top-tracks")
def top_tracks_endpoint(
    filters: PlayFilters = Depends(),
    n: int = Query(10),
    conn: Connection = Depends(get_conn),
):
    return get_top_tracks(conn, filters.min_ms, filters.music_only, filters.merge_enabled, n)


@router.get("/platform-dist")
def platform_dist_endpoint(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_platform_dist(conn, filters.min_ms, filters.music_only, filters.merge_enabled)


@router.get("/dow-dist")
def dow_dist_endpoint(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_dow_dist(conn, filters.min_ms, filters.music_only, filters.merge_enabled)


@router.get("/random-track")
def random_track_endpoint(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_random_track(conn, filters.min_ms, filters.music_only)
