"""Dashboard API endpoints."""

from sqlite3 import Connection

from fastapi import APIRouter, Depends, Query

from backend.core.db import load_plays
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
    get_account_kpis,
    get_dashboard_summary,
    get_dow_dist,
    get_hourly_dist,
    get_monthly_trend,
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
    """Complete dashboard data — all KPIs, charts, and random track in one request.

    Loads plays once and reuses the DataFrame across all sub-functions to avoid
    redundant SQL queries (was 6 calls, now 1).
    """
    df = load_plays(
        conn,
        min_ms=filters.min_ms,
        music_only=filters.music_only,
        merge_enabled=filters.merge_enabled,
        dynamic_threshold=filters.dynamic_threshold,
        max_merge_gap_minutes=filters.max_merge_gap_minutes,
    )
    return {
        "summary": get_dashboard_summary(
            conn, filters.min_ms, filters.music_only, filters.merge_enabled, df=df
        ),
        "account_kpis": get_account_kpis(conn),
        "monthly_trend": get_monthly_trend(
            conn, filters.min_ms, filters.music_only, filters.merge_enabled, df=df
        ),
        "top_tracks": get_top_tracks(
            conn, filters.min_ms, filters.music_only, filters.merge_enabled, df=df
        ),
        "platform_dist": get_platform_dist(
            conn, filters.min_ms, filters.music_only, filters.merge_enabled, df=df
        ),
        "dow_dist": get_dow_dist(
            conn, filters.min_ms, filters.music_only, filters.merge_enabled, df=df
        ),
        "hourly_dist": get_hourly_dist(
            conn, filters.min_ms, filters.music_only, filters.merge_enabled, df=df
        ),
        "random_track": get_random_track(
            conn,
            filters.min_ms,
            filters.music_only,
            filters.merge_enabled,
            filters.dynamic_threshold,
            filters.max_merge_gap_minutes,
            df=df,
        ),
    }


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
