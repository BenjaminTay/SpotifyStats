"""Playback behavior API endpoint."""

from fastapi import APIRouter, Depends
from sqlite3 import Connection

from backend.dependencies import get_conn, PlayFilters
from backend.models.behavior import BehaviorResponse
from backend.services.play_service import get_behavior_data

router = APIRouter(prefix="/behavior", tags=["Behavior"])


@router.get("", response_model=BehaviorResponse)
def behavior_analysis(
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    return get_behavior_data(conn, filters.min_ms, filters.music_only, filters.merge_enabled)
