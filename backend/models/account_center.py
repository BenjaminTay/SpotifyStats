# ruff: noqa: UP045
"""Pydantic response models for account-center adjacent endpoints."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class SearchDailyVolume(BaseModel):
    date: str
    count: int


class SearchQueryCount(BaseModel):
    query: str
    count: int


class SearchIntentCount(BaseModel):
    intent: str
    count: int


class SearchHeatmap(BaseModel):
    z: list[list[int]]
    x: list[int]
    y: list[str]


class SearchHistoryResponse(BaseModel):
    available: bool
    empty: bool = False
    total_searches: int = 0
    daily_volume: list[SearchDailyVolume] = Field(default_factory=list)
    top_queries: list[SearchQueryCount] = Field(default_factory=list)
    intent_dist: list[SearchIntentCount] = Field(default_factory=list)
    heatmap: Optional[SearchHeatmap] = None


class ArtistTierEntry(BaseModel):
    rank: int
    artist_name: str
    play_count: int
    hours: float
    tier: str
    cover_url: Optional[str] = None


class ArtistTiersResponse(BaseModel):
    available: bool
    empty: bool = False
    total_artists: int = 0
    tier_hours: dict[str, float] = Field(default_factory=dict)
    tier_counts: dict[str, int] = Field(default_factory=dict)
    artists: list[ArtistTierEntry] = Field(default_factory=list)


class MarqueeConversionEntry(BaseModel):
    artist_name: str
    segment: str
    impressions: int
    actual_plays: int
    actual_hours: float
    conversion_rate: float
    cover_url: Optional[str] = None


class MarqueeConversionResponse(BaseModel):
    available: bool
    empty: bool = False
    conversions: list[MarqueeConversionEntry] = Field(default_factory=list)


class PodcastTopShow(BaseModel):
    show_name: str
    hours: float


class PodcastMonthlyTrend(BaseModel):
    period: str
    hours: float


class PodcastStatsResponse(BaseModel):
    available: bool
    empty: bool = False
    total_plays: int = 0
    total_hours: float = 0
    unique_shows: int = 0
    saved_shows: int = 0
    top_shows: list[PodcastTopShow] = Field(default_factory=list)
    monthly_trend: list[PodcastMonthlyTrend] = Field(default_factory=list)


class PodcastInteractionResponse(BaseModel):
    type: str
    uri: str
    content: str
    created_at: str


class SavedShowResponse(BaseModel):
    uri: str
    name: str
    publisher: str


class VideoYearlyStats(BaseModel):
    year: int
    audio: int
    video: int


class TopVideoTrack(BaseModel):
    track_name: str
    artist_name: str
    video_plays: int
    audio_plays: int
    cover_url: Optional[str] = None


class VideoStatsResponse(BaseModel):
    available: bool
    empty: bool = False
    total_video_plays: int = 0
    total_audio_plays: int = 0
    avg_duration_sec: float = 0
    platform_dist: dict[str, int] = Field(default_factory=dict)
    yearly: list[VideoYearlyStats] = Field(default_factory=list)
    top_video_tracks: list[TopVideoTrack] = Field(default_factory=list)


class ProfileFollow(BaseModel):
    type: str
    name: str


class ProfilePrompt(BaseModel):
    message: str
    created: str


class ProfileStats(BaseModel):
    first_play_date: Optional[str] = None
    total_audio_plays: int


class BannedItem(BaseModel):
    name: str
    type: str


class UserProfileResponse(BaseModel):
    profile: dict[str, Any]
    follows: list[ProfileFollow]
    prompts: list[ProfilePrompt]
    stats: ProfileStats
    banned_items: list[BannedItem]


class UserInferencesResponse(BaseModel):
    available: bool
    total: int
    categories: dict[str, list[str]]


class SoundCapsuleHighlight(BaseModel):
    date: str
    type: str
    entity_name: str
    detail: Optional[str] = None


class SoundCapsuleDaily(BaseModel):
    date: str
    stream_count: int
    seconds_played: int
    top_data: Optional[str] = None


class SoundCapsuleResponse(BaseModel):
    available: bool
    highlights: list[SoundCapsuleHighlight] = Field(default_factory=list)
    daily: list[SoundCapsuleDaily] = Field(default_factory=list)


class WrappedHubAvailableYearsResponse(BaseModel):
    years: list[int]


class WrappedHubResponse(BaseModel):
    available: bool
    empty: bool = False
    top_artists: list[dict[str, Any]] = Field(default_factory=list)
    top_tracks: list[dict[str, Any]] = Field(default_factory=list)
    top_albums: list[dict[str, Any]] = Field(default_factory=list)
    top_genres: list[dict[str, Any]] = Field(default_factory=list)
    top_podcasts: list[dict[str, Any]] = Field(default_factory=list)
    artist_race: list[dict[str, Any]] = Field(default_factory=list)
    clubs: list[dict[str, Any]] = Field(default_factory=list)
    party_metrics: list[dict[str, Any]] = Field(default_factory=list)
    listening_age: dict[str, Any] = Field(default_factory=dict)
    archive_reports: list[dict[str, Any]] = Field(default_factory=list)
