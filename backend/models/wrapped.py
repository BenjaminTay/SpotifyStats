"""Yearly review full response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.models.artist_language_metadata import (
    ArtistLanguageBucket,
    ArtistLanguageMissingItem,
)


class WrappedAvailableYearsResponse(BaseModel):
    years: list[int]


class WrappedFullHero(BaseModel):
    total_minutes: float
    total_plays: int
    unique_tracks: int
    unique_artists: int
    active_days: int
    avg_minutes_per_day: float


class PersonalityDimension(BaseModel):
    label: str
    score: float
    desc: str


class PersonalityResult(BaseModel):
    primary: str
    primary_label: str
    primary_desc: str
    dimensions: dict[str, PersonalityDimension]


class TopArtistEntry(BaseModel):
    rank: int
    name: str
    plays: int
    hours: float
    cover_url: str


class TopTrackEntry(BaseModel):
    rank: int
    track_id: int
    name: str
    artist_name: str
    plays: int
    hours: float
    cover_url: str


class TopAlbumEntry(BaseModel):
    rank: int
    name: str
    artist_name: str
    plays: int
    hours: float
    cover_url: str


class TopLists(BaseModel):
    artists: list[TopArtistEntry]
    tracks: list[TopTrackEntry]
    albums: list[TopAlbumEntry]


class GenreItem(BaseModel):
    name: str
    label: str | None = None
    play_share: float
    hours: float = 0.0
    confidence_tier: str = "medium"
    top_artists: list[dict[str, Any]] = Field(default_factory=list)
    risk_flags: list[dict[str, Any]] = Field(default_factory=list)


class MonthlyGenreItem(BaseModel):
    month: int
    genres: dict[str, float]


class GenreAxisDistribution(BaseModel):
    axis: str
    label: str
    hours: float
    share_pct: float
    coverage_pct: float
    unknown_hours: float
    unknown_pct: float
    canonical_count: int
    interpretation: str
    buckets: list[dict[str, Any]] = Field(default_factory=list)


class ConsumerGenreBucket(BaseModel):
    key: str
    label: str
    hours: float
    share_pct: float
    artist_count: int


class ConsumerGenreDistribution(BaseModel):
    axis: str
    label: str
    total_hours: float
    known_hours: float
    unknown_hours: float
    allows_multiple: bool = True
    buckets: list[ConsumerGenreBucket] = Field(default_factory=list)


class LanguageDistribution(BaseModel):
    eligible_hours: float = 0.0
    excluded_unattributed_hours: float = 0.0
    classified_hours: float = 0.0
    unknown_hours: float = 0.0
    classified_pct: float = 0.0
    unknown_pct: float = 0.0
    buckets: list[ArtistLanguageBucket] = Field(default_factory=list)
    source_hours: dict[str, float] = Field(default_factory=dict)
    top_missing: list[ArtistLanguageMissingItem] = Field(default_factory=list)
    caveat: str = "艺人级估算，按主艺人归属。"


class ConsumerTasteProfile(BaseModel):
    display_taxonomy_version: str
    primary_styles: ConsumerGenreDistribution
    regional_pop: ConsumerGenreDistribution
    language_dist: LanguageDistribution


class GenrePanorama(BaseModel):
    display_taxonomy_version: str | None = None
    primary_styles: ConsumerGenreDistribution | None = None
    regional_pop: ConsumerGenreDistribution | None = None
    top_genres: list[GenreItem] = []
    monthly_genres: list[MonthlyGenreItem] = []
    axes: list[GenreAxisDistribution] = []
    language_dist: LanguageDistribution | None = None
    coverage: dict[str, Any] | None = None
    caveat: str | None = None


class LateNightTrack(BaseModel):
    track_id: int
    name: str
    artist_name: str
    plays: int
    cover_url: str


class LateNightInfo(BaseModel):
    ratio: float
    top_tracks: list[LateNightTrack] = []


class HourlyDistItem(BaseModel):
    hour: int
    plays: int


class MonthlyPulseItem(BaseModel):
    month: int
    hours: float


class TimeStory(BaseModel):
    daily_grid: list[list[int]] = []
    monthly_pulse: list[MonthlyPulseItem] = []
    hourly_dist: list[HourlyDistItem] = []
    late_night: LateNightInfo | None = None


class RegionDist(BaseModel):
    region: str
    flag: str
    play_share: float


class MusicMap(BaseModel):
    regions: list[RegionDist] = []
    top_overseas_artists: list[dict] = []


class NewArtist(BaseModel):
    name: str
    plays: int
    first_date: str
    cover_url: str


class ReturningTrack(BaseModel):
    track_id: int
    name: str
    artist_name: str
    plays: int
    release_year: int
    cover_url: str


class LongestLove(BaseModel):
    track_id: int
    name: str
    artist_name: str
    span_days: int
    cover_url: str


class DiscoveryReturns(BaseModel):
    new_artists: list[NewArtist] = []
    returning_tracks: list[ReturningTrack] = []
    longest_love: LongestLove | None = None


class ListeningAge(BaseModel):
    age: int
    avg_release_year: int
    description: str


class AlbumCompletion(BaseModel):
    name: str
    artist_name: str
    completion_pct: float
    cover_url: str


class ListeningDepth(BaseModel):
    listening_age: ListeningAge | None = None
    album_completion: list[AlbumCompletion] = []
    deep_listen_ratio: float = 0.0


class MostActiveDay(BaseModel):
    date: str
    plays: int
    top_track: dict


class ListenMoment(BaseModel):
    hour: int
    track: dict


class LongestStreak(BaseModel):
    days: int
    start: str
    end: str


class SpecialMoments(BaseModel):
    most_active_day: MostActiveDay | None = None
    earliest_listen: ListenMoment | None = None
    latest_listen: ListenMoment | None = None
    longest_streak: LongestStreak | None = None


class MonthlyDrillTrack(BaseModel):
    track_id: int
    name: str
    artist_name: str
    plays: int
    cover_url: str


class MonthlyDrillArtist(BaseModel):
    name: str
    cover_url: str


class MonthlyDrillItem(BaseModel):
    month: int
    total_hours: float
    top_tracks: list[MonthlyDrillTrack] = []
    top_artist: MonthlyDrillArtist | None = None


class LastYearComparison(BaseModel):
    total_hours_change: float | None = None
    plays_change: float | None = None
    tracks_change: float | None = None
    artists_change: float | None = None
    active_days_change: float | None = None


class TopVsAlltimeMark(BaseModel):
    name: str
    is_new: bool = False
    is_classic: bool = False


class YearComparison(BaseModel):
    last_year: LastYearComparison | None = None
    top_vs_alltime: dict[str, list[TopVsAlltimeMark]] = {}


class WrappedFullResponse(BaseModel):
    year: int
    empty: bool
    hero: WrappedFullHero | None = None
    personality: PersonalityResult | None = None
    top_lists: TopLists | None = None
    genre_panorama: GenrePanorama | None = None
    time_story: TimeStory | None = None
    music_map: MusicMap | None = None
    discovery_returns: DiscoveryReturns | None = None
    listening_depth: ListeningDepth | None = None
    special_moments: SpecialMoments | None = None
    monthly_drilldown: list[MonthlyDrillItem] = []
    comparison: YearComparison | None = None
