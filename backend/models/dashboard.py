"""Dashboard response models."""

from typing import Optional
from pydantic import BaseModel


class DashboardSummary(BaseModel):
    """Overview KPIs."""

    total_plays: int
    total_hours: float
    total_tracks: int
    total_artists: int
    total_albums: int
    total_days: int
    avg_daily_hours: float


class AccountKpi(BaseModel):
    """Account data KPIs (if account data is imported)."""

    saved_tracks: int
    playlists: int
    search_queries: int
    video_plays: int


class MonthlyTrendPoint(BaseModel):
    """Single period in the monthly trend chart."""

    period: str  # "YYYY-MM"
    plays: int
    hours: float


class TopTrack(BaseModel):
    """Top 10 track row."""

    track_name: str
    artist_name: str
    plays: int


class PlatformDist(BaseModel):
    """Platform distribution row."""

    platform: str
    count: int


class DowDist(BaseModel):
    """Day-of-week distribution row."""

    day: str  # "周一" through "周日"
    count: int


class RandomTrack(BaseModel):
    """Random nostalgic track recommendation."""

    track_name: str
    artist_name: str
    album_name: Optional[str]
    last_played: str
    total_plays: int


class DashboardFullResponse(BaseModel):
    """Complete dashboard data — all in one response to minimize round trips."""

    summary: DashboardSummary
    account_kpis: Optional[AccountKpi]
    monthly_trend: list[MonthlyTrendPoint]
    top_tracks: list[TopTrack]
    platform_dist: list[PlatformDist]
    dow_dist: list[DowDist]
    random_track: Optional[RandomTrack]
