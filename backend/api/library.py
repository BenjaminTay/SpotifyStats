"""Library / account data API endpoints."""

from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.dependencies import get_conn
from backend.domains.metadata.artist_identity import canonicalize_artist_payload
from backend.services.library_service import (
    get_library_overview,
    get_playlist_overlap_matrix,
    get_playlist_tracks,
    get_playlists,
    get_saved_tracks_paginated,
)

router = APIRouter(prefix="/library", tags=["Library"])


class LibraryOverviewResponse(BaseModel):
    model_config = {"extra": "allow"}
    available: bool | None = None
    saved_tracks: int | None = None
    saved_albums: int | None = None
    saved_artists: int | None = None
    playlists: int | None = None
    banned_items: int | None = None
    coverage_pct: float | None = None
    forgotten_count: int | None = None
    forgotten_tracks: list[dict] | None = None
    artist_comparison: list[dict] | None = None


class PlaylistEntry(BaseModel):
    model_config = {"extra": "allow"}
    id: int
    name: str
    last_modified: str | None = None
    track_count: int | None = None


class PlaylistTrackEntry(BaseModel):
    model_config = {"extra": "allow"}
    track_uri: str
    track_name: str
    artist_name: str
    album_name: str | None = None
    added_date: str | None = None
    cover_url: str | None = None


class SavedTracksResponse(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int
    tracks: list[dict]


class PlaylistOverlapResponse(BaseModel):
    playlist_ids: list[int]
    playlist_names: list[str]
    matrix: list[list[int]]


@router.get("", response_model=LibraryOverviewResponse)
def library_overview(conn: Connection = Depends(get_conn)):
    return canonicalize_artist_payload(get_library_overview(conn), conn)


@router.get("/playlists", response_model=list[PlaylistEntry])
def playlists(conn: Connection = Depends(get_conn)):
    return get_playlists(conn)


@router.get("/playlists/{playlist_id}/tracks", response_model=list[PlaylistTrackEntry])
def playlist_tracks(playlist_id: int, conn: Connection = Depends(get_conn)):
    return canonicalize_artist_payload(get_playlist_tracks(conn, playlist_id), conn)


@router.get("/saved-tracks", response_model=SavedTracksResponse)
def saved_tracks(
    page: int = 1, limit: int = 50, search: str = "", conn: Connection = Depends(get_conn)
):
    return canonicalize_artist_payload(
        get_saved_tracks_paginated(conn, page=page, limit=limit, search=search), conn
    )


@router.get("/playlist-overlap", response_model=PlaylistOverlapResponse)
def playlist_overlap(conn: Connection = Depends(get_conn)):
    return get_playlist_overlap_matrix(conn)
