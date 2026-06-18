"""Playback behavior API endpoint."""

from sqlite3 import Connection

from fastapi import APIRouter, Depends, Query

from backend.dependencies import get_conn
from backend.models.behavior import BehaviorResponse
from backend.services.play_service import get_behavior_data

router = APIRouter(prefix="/behavior", tags=["Behavior"])


@router.get("", response_model=BehaviorResponse)
def behavior_analysis(
    music_only: bool = Query(default=True, description="仅音乐"),
    conn: Connection = Depends(get_conn),
):
    return get_behavior_data(conn, music_only=music_only)
