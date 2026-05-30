"""Artist deep dive API endpoint."""

from sqlite3 import Connection

from fastapi import APIRouter, Depends, Query

from backend.dependencies import PlayFilters, get_conn
from backend.services.play_service import get_artist_deep_dive, get_artist_list

router = APIRouter(prefix="/artist", tags=["Artist"])


@router.get("/list")
def artist_list(
    min_ms: int = Query(30000, ge=0),
    music_only: bool = Query(True),
    conn: Connection = Depends(get_conn),
):
    return get_artist_list(conn, min_ms, music_only)


@router.get("/{name}/deep-dive")
def artist_deep_dive(
    name: str,
    filters: PlayFilters = Depends(),
    conn: Connection = Depends(get_conn),
):
    """In-depth analysis for a single artist: heatmap, top tracks, album breakdown, monthly trend."""
    return get_artist_deep_dive(
        conn, filters.min_ms, filters.music_only, filters.merge_enabled, name
    )
