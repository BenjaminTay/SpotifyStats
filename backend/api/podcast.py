"""Podcast API endpoint."""

from fastapi import APIRouter, Depends
from sqlite3 import Connection

from backend.dependencies import get_conn
from backend.services.podcast_service import (
    get_podcast_stats, get_podcast_interactions, get_saved_shows,
)

router = APIRouter(prefix="/podcast", tags=["Podcast"])


@router.get("")
def podcast_stats(conn: Connection = Depends(get_conn)):
    return get_podcast_stats(conn)


@router.get("/interactions")
def interactions(conn: Connection = Depends(get_conn)):
    return get_podcast_interactions(conn)


@router.get("/saved-shows")
def saved_shows(conn: Connection = Depends(get_conn)):
    return get_saved_shows(conn)
