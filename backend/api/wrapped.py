"""Wrapped API endpoint."""

from fastapi import APIRouter, Depends
from sqlite3 import Connection

from backend.dependencies import get_conn, PlayFilters
from backend.models.timeline import YearlyWrapped
from backend.services.play_service import get_wrapped_data

router = APIRouter(prefix="/wrapped", tags=["Wrapped"])


@router.get("/{year}", response_model=YearlyWrapped)
def yearly_wrapped(
    year: int,
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_wrapped_data(conn, filters.min_ms, filters.music_only, filters.merge_enabled, year)
