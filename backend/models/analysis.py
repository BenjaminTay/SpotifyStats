"""Analysis response models."""

from __future__ import annotations

from pydantic import BaseModel

from backend.models.wrapped import ConsumerTasteProfile

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
    taste_profile: ConsumerTasteProfile
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


# ── /analysis/records ──


class PlaybackRecordRow(BaseModel):
    """通用播放记录行模型，三实体记录与事件型记录共用。"""

    rank: int
    entity_type: str | None = None
    entity_id: str | None = None
    name: str
    artist_name: str | None = None
    artist_names: list[str] | None = None
    artist_cover_urls: list[str | None] | None = None
    artist_play_counts: list[int] | None = None
    value: float
    unit: str
    secondary_value: float | None = None
    secondary_unit: str | None = None
    date: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    total_plays: int | None = None
    total_hours: float | None = None
    unique_tracks: int | None = None
    top_track_name: str | None = None
    top_track_entity_id: str | None = None
    top_track_artist_name: str | None = None
    top_track_plays: int | None = None
    top_track_cover_url: str | None = None
    top_album_name: str | None = None
    top_album_artist_name: str | None = None
    top_album_plays: int | None = None
    top_album_cover_url: str | None = None
    top_artist_name: str | None = None
    top_artist_plays: int | None = None
    top_artist_cover_url: str | None = None
    share_pct: float | None = None
    cover_url: str | None = None
    caption: str | None = None
    qualified: bool | None = None


class EntityRecordFamily(BaseModel):
    """三实体记录族，同一记录主题在 track/album/artist 三个维度的结果。"""

    track: list[PlaybackRecordRow] = []
    album: list[PlaybackRecordRow] = []
    artist: list[PlaybackRecordRow] = []


class PlaybackObsessionRecords(BaseModel):
    daily_binge: EntityRecordFamily = EntityRecordFamily()
    daily_duration: EntityRecordFamily = EntityRecordFamily()
    consecutive_marathon: EntityRecordFamily = EntityRecordFamily()
    daily_total_record: list[PlaybackRecordRow] = []


class PlaybackLateNightTrajectory(BaseModel):
    monthly: list[PlaybackRecordRow] = []
    quarterly: list[PlaybackRecordRow] = []
    monthly_min_plays: int = 500
    quarterly_min_plays: int = 1500


class PlaybackTimePatternRecords(BaseModel):
    hourly_dominance: EntityRecordFamily = EntityRecordFamily()
    monthly_peak: EntityRecordFamily = EntityRecordFamily()
    yearly_peak: EntityRecordFamily = EntityRecordFamily()
    late_night_peak_day: list[PlaybackRecordRow] = []
    late_night_trajectory: PlaybackLateNightTrajectory = PlaybackLateNightTrajectory()
    weekday_preference: list[PlaybackRecordRow] = []
    new_year_eve: list[PlaybackRecordRow] = []


class PlaybackReignRecords(BaseModel):
    daily_champion: EntityRecordFamily = EntityRecordFamily()
    monthly_reign: EntityRecordFamily = EntityRecordFamily()
    yearly_reign: EntityRecordFamily = EntityRecordFamily()
    fastest_milestone: EntityRecordFamily = EntityRecordFamily()
    consecutive_champion_days: EntityRecordFamily = EntityRecordFamily()


class PlaybackLongevityRecords(BaseModel):
    longest_streak_days: EntityRecordFamily = EntityRecordFamily()
    longest_span: EntityRecordFamily = EntityRecordFamily()
    comeback_after_sleep: EntityRecordFamily = EntityRecordFamily()
    most_active_months: EntityRecordFamily = EntityRecordFamily()
    user_active_streak: list[PlaybackRecordRow] = []


class PlaybackDiscoveryRecords(BaseModel):
    discovery_day: EntityRecordFamily = EntityRecordFamily()
    longest_no_repeat: EntityRecordFamily = EntityRecordFamily()
    album_completionist: EntityRecordFamily = EntityRecordFamily()
    same_name_diff_artist: list[PlaybackRecordRow] = []
    feat_lover: EntityRecordFamily = EntityRecordFamily()


class PlaybackBehaviorRecords(BaseModel):
    skip_storm: EntityRecordFamily = EntityRecordFamily()
    shuffle_peak: list[PlaybackRecordRow] = []
    platform_reign: list[PlaybackRecordRow] = []
    platform_switch_day: list[PlaybackRecordRow] = []
    playback_milestones: list[PlaybackRecordRow] = []


class PlaybackRecordsData(BaseModel):
    obsession: PlaybackObsessionRecords = PlaybackObsessionRecords()
    time_patterns: PlaybackTimePatternRecords = PlaybackTimePatternRecords()
    reigns: PlaybackReignRecords = PlaybackReignRecords()
    longevity: PlaybackLongevityRecords = PlaybackLongevityRecords()
    discovery: PlaybackDiscoveryRecords = PlaybackDiscoveryRecords()
    behavior: PlaybackBehaviorRecords = PlaybackBehaviorRecords()


class PlaybackRecordsMeta(BaseModel):
    total_plays: int
    total_hours: float
    active_days: int
    merge_level: int
    min_sample_plays: int = 10
    generated_at: str


class PlaybackRecordsResponse(BaseModel):
    period: AnalysisResolvedPeriod
    meta: PlaybackRecordsMeta
    records: PlaybackRecordsData
