"""Podcast API endpoint."""

from sqlite3 import Connection

from fastapi import APIRouter, Depends

from backend.dependencies import get_conn
from backend.models.account_center import (
    PodcastInteractionResponse,
    PodcastStatsResponse,
    SavedShowResponse,
)
from backend.services.podcast_service import (
    get_podcast_interactions,
    get_podcast_stats,
    get_saved_shows,
)

router = APIRouter(prefix="/podcast", tags=["Podcast"])


@router.get("", response_model=PodcastStatsResponse, response_model_exclude_unset=True)
def podcast_stats(conn: Connection = Depends(get_conn)):
    return get_podcast_stats(conn)


@router.get("/interactions", response_model=list[PodcastInteractionResponse])
def interactions(conn: Connection = Depends(get_conn)):
    return get_podcast_interactions(conn)


@router.get("/saved-shows", response_model=list[SavedShowResponse])
def saved_shows(conn: Connection = Depends(get_conn)):
    return get_saved_shows(conn)
