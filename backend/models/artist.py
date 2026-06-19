"""Response models for artist selector and deep-dive endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ArtistListItem(BaseModel):
    artist_id: int
    artist_name: str
    play_count: int
    cover_url: str | None = None


class ArtistDeepDiveInfo(BaseModel):
    total_plays: int
    total_hours: float
    unique_tracks: int
    unique_albums: int


class ArtistDeepDiveHeatmap(BaseModel):
    z: list[list[int]]
    x: list[int]
    y: list[str]


class ArtistDeepDiveTrack(BaseModel):
    track_id: int
    track_name: str
    plays: int
    hours: float
    cover_url: str | None = None


class ArtistDeepDiveMonth(BaseModel):
    period: str
    plays: int
    hours: float


class ArtistAlbumBreakdown(BaseModel):
    album_name: str
    plays: int
    hours: float
    cover_url: str | None = None


class ArtistDeepDiveResponse(BaseModel):
    found: bool
    artist_name: str | None = None
    cover_url: str | None = None
    info: ArtistDeepDiveInfo | None = None
    heatmap: ArtistDeepDiveHeatmap | None = None
    top_tracks: list[ArtistDeepDiveTrack] = Field(default_factory=list)
    monthly_trend: list[ArtistDeepDiveMonth] = Field(default_factory=list)
    album_breakdown: list[ArtistAlbumBreakdown] = Field(default_factory=list)
