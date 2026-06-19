"""Lyrics endpoints — Genius integration."""

from fastapi import APIRouter

from backend.models.lyrics import TrackGeniusUrlResponse, TrackLyricsResponse
from backend.services.genius_service import get_track_genius_url, get_track_lyrics

router = APIRouter()


@router.get("/{track_id}", response_model=TrackLyricsResponse, response_model_exclude_unset=True)
def track_lyrics(track_id: int):
    """Get full lyrics for a track, fetched from Genius and cached in DB."""
    return get_track_lyrics(track_id)


@router.get(
    "/{track_id}/url", response_model=TrackGeniusUrlResponse, response_model_exclude_unset=True
)
def track_genius_url(track_id: int):
    """Get just the Genius page URL for a track."""
    return get_track_genius_url(track_id)
