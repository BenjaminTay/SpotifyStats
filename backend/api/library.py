"""Library / account data API endpoints."""

from sqlite3 import Connection

from fastapi import APIRouter, Depends

from backend.dependencies import get_conn
from backend.services.library_service import (
    get_library_overview,
    get_playlist_overlap_matrix,
    get_playlist_tracks,
    get_playlists,
    get_saved_tracks_paginated,
)

router = APIRouter(prefix="/library", tags=["Library"])


@router.get("")
def library_overview(conn: Connection = Depends(get_conn)):
    return get_library_overview(conn)


@router.get("/playlists")
def playlists(conn: Connection = Depends(get_conn)):
    return get_playlists(conn)


@router.get("/playlists/{playlist_id}/tracks")
def playlist_tracks(playlist_id: int, conn: Connection = Depends(get_conn)):
    return get_playlist_tracks(conn, playlist_id)


@router.get("/saved-tracks")
def saved_tracks(
    page: int = 1, limit: int = 50, search: str = "", conn: Connection = Depends(get_conn)
):
    return get_saved_tracks_paginated(conn, page=page, limit=limit, search=search)


@router.get("/playlist-overlap")
def playlist_overlap(conn: Connection = Depends(get_conn)):
    return get_playlist_overlap_matrix(conn)
