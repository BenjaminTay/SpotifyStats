"""Typed contract for the personal music front page."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HomeEntityRef(BaseModel):
    entity_type: Literal["track", "album", "artist"]
    entity_id: int | str | None = None
    name: str
    artist_name: str | None = None
    cover_url: str | None = None
    deep_link: str


class HomeCoverage(BaseModel):
    first_source_date: str | None = None
    source_latest_date: str | None = None
    first_effective_play_date: str | None = None
    latest_effective_play_date: str | None = None
    # Compatibility aliases for early V1 clients; both refer to effective plays.
    first_play_date: str | None = None
    latest_play_date: str | None = None
    freshness: Literal["recent", "aging", "old", "unknown"] = "unknown"
    has_account_data: bool = False


class HomeArchive(BaseModel):
    total_plays: int = Field(ge=0)
    total_hours: float = Field(ge=0)
    unique_tracks: int = Field(ge=0)
    unique_artists: int = Field(ge=0)
    unique_albums: int = Field(ge=0)
    active_days: int = Field(ge=0)


class HomeHeadline(BaseModel):
    kind: Literal["comeback", "discovery", "surge", "habit_shift", "leader", "archive"]
    title: str
    statement: str
    entity: HomeEntityRef | None = None


class HomePeriod(BaseModel):
    start_date: str
    end_date: str
    label: str


class HomeRecentSummary(BaseModel):
    plays: int = Field(ge=0)
    hours: float = Field(ge=0)
    active_days: int = Field(ge=0)
    plays_delta_pct: float | None = None
    hours_delta_pct: float | None = None
    late_night_pct: float = Field(ge=0, le=100)
    weekend_pct: float = Field(ge=0, le=100)


class HomeTrendPoint(BaseModel):
    date: str
    plays: int = Field(ge=0)
    hours: float = Field(ge=0)


class HomeEntityMetric(BaseModel):
    entity: HomeEntityRef
    plays: int = Field(ge=0)
    hours: float = Field(ge=0)


class HomeRecentLeaders(BaseModel):
    track: HomeEntityMetric | None = None
    album: HomeEntityMetric | None = None
    artist: HomeEntityMetric | None = None


class HomeRecent(BaseModel):
    period: HomePeriod | None = None
    comparison_period: HomePeriod | None = None
    comparison_available: bool = False
    summary: HomeRecentSummary
    trend: list[HomeTrendPoint] = Field(default_factory=list)
    leaders: HomeRecentLeaders = Field(default_factory=HomeRecentLeaders)


class HomeChartChampion(BaseModel):
    entity: HomeEntityRef
    rank: Literal[1] = 1
    plays: int = Field(ge=0)
    hours: float = Field(ge=0)
    movement: Literal["new", "re", "up", "down", "same"]
    previous_rank: int | None = Field(default=None, ge=1)
    rank_change: int | None = None


class HomeBillboard(BaseModel):
    state: Literal["ready", "unavailable"]
    week: str | None = None
    track: HomeChartChampion | None = None
    album: HomeChartChampion | None = None
    artist: HomeChartChampion | None = None


class HomeYearlyReview(BaseModel):
    state: Literal["ready", "not_generated", "unavailable"]
    year: int | None = None
    headline: str | None = None
    statement: str | None = None
    entity: HomeEntityRef | None = None


class HomeRediscovery(BaseModel):
    entity: HomeEntityRef
    last_played: str
    total_plays: int = Field(ge=1)
    days_since_last_play: int = Field(ge=0)


class HomeOverviewResponse(BaseModel):
    schema_version: Literal["home_overview_v2"] = "home_overview_v2"
    generated_at: str
    cache_state: Literal["fresh", "warming", "stale"] = "fresh"
    filter_fingerprint: str
    state: Literal["ready", "limited", "empty"]
    coverage: HomeCoverage
    archive: HomeArchive
    headline: HomeHeadline
    recent: HomeRecent | None = None
    billboard: HomeBillboard
    yearly_review: HomeYearlyReview
    rediscovery: HomeRediscovery | None = None
