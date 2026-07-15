"""Response models for local music entity search."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MusicSearchKind = Literal["track", "album", "artist"]


class MusicSearchChartSummary(BaseModel):
    peak_position: int | None = None
    peak_weeks: int | None = None
    weeks_on_chart: int | None = None
    weeks_at_no1: int | None = None
    power_score: int | None = None
    power_rank: int | None = None
    first_week: str | None = None
    latest_week: str | None = None
    first_peak_week: str | None = None


class MusicSearchResult(BaseModel):
    kind: MusicSearchKind
    label: str
    subtitle: str | None = None
    href: str
    play_events: int = 0
    total_ms: int = 0
    track_id: int | None = None
    artist_id: int | None = None
    album_name: str | None = None
    artist_name: str | None = None
    cover_url: str | None = None
    chart: MusicSearchChartSummary | None = None


class MusicSearchResponse(BaseModel):
    query: str
    limit_per_type: int = Field(ge=1, le=10)
    total: int
    tracks: list[MusicSearchResult] = Field(default_factory=list)
    albums: list[MusicSearchResult] = Field(default_factory=list)
    artists: list[MusicSearchResult] = Field(default_factory=list)
