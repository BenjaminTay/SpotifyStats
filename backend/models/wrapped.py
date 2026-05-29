"""Yearly review full response models."""

from typing import Optional
from pydantic import BaseModel


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
    play_share: float


class MonthlyGenreItem(BaseModel):
    month: int
    genres: dict[str, float]


class LanguageDist(BaseModel):
    chinese: float = 0.0
    english: float = 0.0
    korean: float = 0.0
    japanese: float = 0.0
    instrumental: float = 0.0
    other: float = 0.0


class GenrePanorama(BaseModel):
    top_genres: list[GenreItem] = []
    monthly_genres: list[MonthlyGenreItem] = []
    language_dist: Optional[LanguageDist] = None


class LateNightTrack(BaseModel):
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
    late_night: Optional[LateNightInfo] = None


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
    name: str
    artist_name: str
    plays: int
    release_year: int
    cover_url: str


class LongestLove(BaseModel):
    name: str
    artist_name: str
    span_days: int
    cover_url: str


class DiscoveryReturns(BaseModel):
    new_artists: list[NewArtist] = []
    returning_tracks: list[ReturningTrack] = []
    longest_love: Optional[LongestLove] = None


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
    listening_age: Optional[ListeningAge] = None
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
    most_active_day: Optional[MostActiveDay] = None
    earliest_listen: Optional[ListenMoment] = None
    latest_listen: Optional[ListenMoment] = None
    longest_streak: Optional[LongestStreak] = None


class MonthlyDrillTrack(BaseModel):
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
    top_artist: Optional[MonthlyDrillArtist] = None


class LastYearComparison(BaseModel):
    total_hours_change: Optional[float] = None
    plays_change: Optional[float] = None
    tracks_change: Optional[float] = None
    artists_change: Optional[float] = None
    active_days_change: Optional[float] = None


class TopVsAlltimeMark(BaseModel):
    name: str
    is_new: bool = False
    is_classic: bool = False


class YearComparison(BaseModel):
    last_year: Optional[LastYearComparison] = None
    top_vs_alltime: dict[str, list[TopVsAlltimeMark]] = {}


class WrappedFullResponse(BaseModel):
    year: int
    empty: bool
    hero: Optional[WrappedFullHero] = None
    personality: Optional[PersonalityResult] = None
    top_lists: Optional[TopLists] = None
    genre_panorama: Optional[GenrePanorama] = None
    time_story: Optional[TimeStory] = None
    music_map: Optional[MusicMap] = None
    discovery_returns: Optional[DiscoveryReturns] = None
    listening_depth: Optional[ListeningDepth] = None
    special_moments: Optional[SpecialMoments] = None
    monthly_drilldown: list[MonthlyDrillItem] = []
    comparison: Optional[YearComparison] = None
