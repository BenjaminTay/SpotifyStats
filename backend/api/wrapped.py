"""Wrapped API endpoint."""

from sqlite3 import Connection

from fastapi import APIRouter, Depends

from backend.dependencies import PlayFilters, get_conn
from backend.models.timeline import YearlyWrapped
from backend.models.wrapped import WrappedFullResponse
from backend.services.play_service import get_wrapped_data
from backend.services.wrapped_service import get_wrapped_full

router = APIRouter(prefix="/wrapped", tags=["Wrapped"])


@router.get("/available-years")
def available_years(conn: Connection = Depends(get_conn)):
    """Return years with play data for the yearly review."""
    years = conn.execute("SELECT DISTINCT ts_year FROM plays ORDER BY ts_year").fetchall()
    return {"years": [int(y[0]) for y in years]}


@router.get("/{year}", response_model=YearlyWrapped)
def yearly_wrapped(
    year: int,
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_wrapped_data(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        year,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
    )


@router.get("/{year}/full", response_model=WrappedFullResponse)
def yearly_wrapped_full(
    year: int,
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_wrapped_full(
        conn,
        filters.min_ms,
        filters.music_only,
        filters.merge_enabled,
        year,
        filters.dynamic_threshold,
        filters.max_merge_gap_minutes,
    )
