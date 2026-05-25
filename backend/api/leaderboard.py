"""Leaderboard API endpoint."""

from fastapi import APIRouter, Depends, Query
from sqlite3 import Connection
from typing import Optional

from backend.dependencies import get_conn, PlayFilters
from backend.services.play_service import get_leaderboard

router = APIRouter(prefix="/leaderboard", tags=["Leaderboard"])


@router.get("")
def leaderboard(
    entity: str = Query("track", pattern="^(track|artist|album)$"),
    time_range: str = Query("all", pattern="^(all|this_year|this_month|custom)$"),
    year: Optional[int] = Query(None),
    month: Optional[str] = Query(None, description="YYYY-MM format"),
    metric: str = Query("plays", pattern="^(plays|hours)$"),
    top_n: int = Query(30, ge=5, le=100),
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_leaderboard(
        conn, filters.min_ms, filters.music_only, filters.merge_enabled,
        entity=entity, time_range=time_range,
        year=year, month=month, metric=metric, top_n=top_n,
    )
