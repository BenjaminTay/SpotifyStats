"""Lyrics endpoints — Genius integration."""

from fastapi import APIRouter
from backend.services.genius_service import get_track_lyrics, get_track_genius_url

router = APIRouter()


@router.get("/{track_id}")
def track_lyrics(track_id: int):
    """Get full lyrics for a track, fetched from Genius and cached in DB."""
    return get_track_lyrics(track_id)


@router.get("/{track_id}/url")
def track_genius_url(track_id: int):
    """Get just the Genius page URL for a track."""
    return get_track_genius_url(track_id)
