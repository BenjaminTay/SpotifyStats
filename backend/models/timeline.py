"""Timeline & wrapped response models."""

from typing import Optional
from pydantic import BaseModel


class AnnualTimelinePoint(BaseModel):
    year: int
    plays: int
    hours: float
    tracks: int
    artists: int


class MonthlyTimelinePoint(BaseModel):
    period: str  # "YYYY-MM"
    plays: int
    hours: float


class WrappedHero(BaseModel):
    total_minutes: float
    total_plays: int
    unique_tracks: int
    unique_artists: int
    total_days: int
    avg_minutes_per_day: float


class WrappedArtistEntry(BaseModel):
    artist_name: str
    plays: int
    hours: float


class WrappedTrackEntry(BaseModel):
    track_name: str
    artist_name: str
    plays: int
    hours: float


class WrappedAlbumEntry(BaseModel):
    album_name: str
    artist_name: str
    hours: float


class WrappedFirstLastTrack(BaseModel):
    track_name: str
    artist_name: str
    date: str


class WrappedMonthlyPulse(BaseModel):
    month: int
    hours: float


class YearlyWrapped(BaseModel):
    year: int
    empty: bool
    hero: Optional[WrappedHero] = None
    top_artists: list[WrappedArtistEntry] = []
    top_tracks: list[WrappedTrackEntry] = []
    top_album: Optional[WrappedAlbumEntry] = None
    platform_hours: dict[str, float] = {}
    peak_hour: int = 0
    first_track: Optional[WrappedFirstLastTrack] = None
    last_track: Optional[WrappedFirstLastTrack] = None
    season_tops: dict[str, str] = {}
    monthly_pulse: list[WrappedMonthlyPulse] = []
    personality: Optional[dict] = None
