"""Response models for Genius lyrics endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class TrackLyricsResponse(BaseModel):
    found: bool
    lyrics: str | None = None
    genius_url: str | None = None
    genius_song_id: int | None = None
    cached: bool | None = None


class TrackGeniusUrlResponse(BaseModel):
    found: bool
    genius_url: str | None = None
