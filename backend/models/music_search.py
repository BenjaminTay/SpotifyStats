"""Response models for local music entity search."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MusicSearchKind = Literal["track", "album", "artist"]


class MusicSearchResult(BaseModel):
    kind: MusicSearchKind
    label: str
    subtitle: str | None = None
    href: str
    play_events: int = 0
    total_ms: int = 0
    track_id: int | None = None
    album_name: str | None = None
    artist_name: str | None = None
    cover_url: str | None = None


class MusicSearchResponse(BaseModel):
    query: str
    limit_per_type: int = Field(ge=1, le=10)
    total: int
    tracks: list[MusicSearchResult] = Field(default_factory=list)
    albums: list[MusicSearchResult] = Field(default_factory=list)
    artists: list[MusicSearchResult] = Field(default_factory=list)
