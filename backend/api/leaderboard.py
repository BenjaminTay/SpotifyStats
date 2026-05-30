"""Leaderboard API endpoint."""

from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, Query

from backend.dependencies import PlayFilters, get_conn
from backend.services.play_service import get_leaderboard

router = APIRouter(prefix="/leaderboard", tags=["Leaderboard"])


@router.get("")
def leaderboard(
    entity: str = Query("track", pattern="^(track|artist|album)$"),
    time_range: str = Query("all", pattern="^(all|this_year|this_month|custom)$"),
    year: int | None = Query(None),
    month: str | None = Query(None, description="YYYY-MM format"),
    metric: str = Query("plays", pattern="^(plays|hours)$"),
    top_n: int = Query(30, ge=5, le=100),
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_leaderboard(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        entity=entity,
        time_range=time_range,
        year=year,
        month=month,
        metric=metric,
        top_n=top_n,
    )
