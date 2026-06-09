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
    peak_period: str
    peak_plays: int
    low_period: str
    low_plays: int
    latest_period: str
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
    id: str
    title: str
    subtitle: str
    highlight: str | None
    icon: str | None
    trend: str | None


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


class AnalysisSummary(BaseModel):
    plays: int
    hours: float
    days: int
    tracks: int
    artists: int
    albums: int
    avg_daily_plays: float
    avg_daily_hours: float
    first_date: str | None
    last_date: str | None


class AnalysisDailyMetric(BaseModel):
    date: str
    plays: int


class AnalysisHourlyPoint(BaseModel):
    hour: int
    count: int


class AnalysisDailyTrendPoint(BaseModel):
    date: str
    plays: int
    cum_plays: int


class AnalysisWeekdayPoint(BaseModel):
    dow: int
    count: int


class AnalysisMonthPoint(BaseModel):
    month: int
    count: int


class AnalysisYearPoint(BaseModel):
    year: int
    count: int


class AnalysisStatsBehaviorSummary(BaseModel):
    total_plays: int
    skip_rate: float | None
    avg_ms: float
    platforms: dict[str, int]


class AnalysisStatsResponse(BaseModel):
    period: AnalysisResolvedPeriod
    summary: AnalysisSummary
    daily_metrics: list[dict]
    hourly_distribution: list[AnalysisHourlyPoint]
    daily_trend: list[AnalysisDailyTrendPoint]
    cumulative_trend: list[dict]
    weekday_distribution: list[AnalysisWeekdayPoint]
    month_distribution: list[dict]
    year_distribution: list[dict]
    behavior_summary: dict
    recent_plays: list[dict]


# ── /analysis/charts ──


class AnalysisChartRow(BaseModel):
    rank: int
    track_id: int | None
    track_name: str | None
    artist_name: str | None
    album_name: str | None
    plays: int
    hours: float
    share_pct: str
    first_played: str | None
    last_played: str | None
    avg_daily_plays: float
    avg_daily_hours: float
    cover_url: str | None
    unique_tracks: int | None
    artist_names: list[str] | None


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
    track_id: int | None
    track_name: str
    artist_name: str
    album_name: str | None
    ms_played: int
    hours: float
    platform: str
    cover_url: str | None
    artist_names: list[str] | None


class AnalysisPlaysResponse(BaseModel):
    total: int
    limit: int
    offset: int
    rows: list[AnalysisPlayRow]


# ── /analysis/play-dates ──


class AnalysisPlayDateEntry(BaseModel):
    date: str
    count: int
