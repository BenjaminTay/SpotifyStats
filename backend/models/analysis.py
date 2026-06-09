"""Analysis response models."""

from __future__ import annotations

from pydantic import BaseModel

# ── Sub-structures for /analysis/overview ──


class AnalysisOverviewSummary(BaseModel):
    total_plays: int
    total_hours: float
    total_tracks: int
    total_artists: int
    total_albums: int
    total_days: int
    avg_daily_hours: float


class AnalysisTrendSummary(BaseModel):
    peak_period: str | None
    peak_plays: int
    low_period: str | None
    low_plays: int
    latest_period: str | None
    latest_plays: int
    previous_period: str | None
    previous_plays: int
    month_delta_pct: float | None


class AnalysisListeningSummary(BaseModel):
    peak_hour: int | None
    peak_hour_count: int
    late_night_rate: float
    weekend_rate: float
    day_type_preference: str


class AnalysisTopTrack(BaseModel):
    track_id: int
    track_name: str
    artist_name: str
    plays: int
    hours: float
    cover_url: str | None


class AnalysisTopArtist(BaseModel):
    artist_name: str
    plays: int
    hours: float
    tracks: int
    cover_url: str | None


class AnalysisTopAlbum(BaseModel):
    album_name: str
    artist_name: str
    plays: int
    hours: float
    cover_url: str | None


class AnalysisModuleCard(BaseModel):
    key: str
    title: str
    metric: str
    detail: str
    to: str
    cover_url: str | None = None


class AnalysisOverviewResponse(BaseModel):
    summary: AnalysisOverviewSummary
    monthly_trend: list[dict]
    trend_summary: AnalysisTrendSummary
    listening_summary: AnalysisListeningSummary
    top_tracks: list[AnalysisTopTrack]
    top_artists: list[AnalysisTopArtist]
    top_albums: list[AnalysisTopAlbum]
    behavior_summary: dict
    module_cards: list[AnalysisModuleCard]


# ── Sub-structures for /analysis/stats ──


class AnalysisResolvedPeriod(BaseModel):
    period: str
    label: str
    start_date: str | None
    end_date: str | None


class AnalysisStatsSummary(BaseModel):
    total_plays: int
    total_hours: float
    unique_tracks: int
    unique_albums: int
    unique_artists: int
    active_days: int


class AnalysisDailyMetrics(BaseModel):
    avg_daily_plays: float
    avg_daily_hours: float
    avg_active_day_plays: float
    avg_active_day_hours: float


class AnalysisHourlyPoint(BaseModel):
    hour: int
    plays: int
    hours: float


class AnalysisDailyTrendPoint(BaseModel):
    date: str
    plays: int
    hours: float


class AnalysisCumulativeTrendPoint(BaseModel):
    date: str
    cumulative_plays: int
    cumulative_hours: float


class AnalysisWeekdayPoint(BaseModel):
    day: str
    plays: int
    hours: float


class AnalysisMonthPoint(BaseModel):
    month: int
    plays: int
    hours: float


class AnalysisYearPoint(BaseModel):
    year: int
    plays: int
    hours: float


class AnalysisStatsBehaviorSummary(BaseModel):
    forward_rate: float
    shuffle_rate: float
    primary_platform: str
    primary_platform_rate: float
    top_start_reason: str
    top_end_reason: str


class AnalysisStatsResponse(BaseModel):
    period: AnalysisResolvedPeriod
    summary: AnalysisStatsSummary
    daily_metrics: AnalysisDailyMetrics
    hourly_distribution: list[AnalysisHourlyPoint]
    daily_trend: list[AnalysisDailyTrendPoint]
    cumulative_trend: list[AnalysisCumulativeTrendPoint]
    weekday_distribution: list[AnalysisWeekdayPoint]
    month_distribution: list[AnalysisMonthPoint]
    year_distribution: list[AnalysisYearPoint]
    behavior_summary: AnalysisStatsBehaviorSummary
    recent_plays: list[dict]


# ── /analysis/charts ──


class AnalysisChartRow(BaseModel):
    rank: int
    track_id: int | None = None
    track_name: str | None = None
    artist_name: str | None = None
    album_name: str | None = None
    plays: int
    hours: float
    share_pct: float
    first_played: str | None = None
    last_played: str | None = None
    avg_daily_plays: float
    avg_daily_hours: float
    cover_url: str | None = None
    unique_tracks: int | None = None
    unique_albums: int | None = None
    artist_names: list[str] | None = None


class AnalysisChartsResponse(BaseModel):
    period: AnalysisResolvedPeriod
    entity: str
    metric: str
    total: int
    limit: int
    offset: int
    rows: list[AnalysisChartRow]


# ── /analysis/plays ──


class AnalysisPlayRow(BaseModel):
    play_id: int
    ts: str
    date: str
    track_id: int | None = None
    track_name: str
    artist_name: str
    album_name: str | None = None
    ms_played: int
    hours: float
    platform: str
    cover_url: str | None = None
    artist_names: list[str] | None = None


class AnalysisPlaysResponse(BaseModel):
    total: int
    limit: int
    offset: int
    rows: list[AnalysisPlayRow]


# ── /analysis/play-dates ──


class AnalysisPlayDateEntry(BaseModel):
    date: str
    count: int
