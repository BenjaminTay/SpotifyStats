"""Strict response contracts for the local-first music archive."""

from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field

ArchiveDataStatus = Literal["ready", "partial", "empty"]
ArchiveCapabilityStatus = Literal["available", "partial", "unavailable"]
ArchiveFeatureRole = Literal[
    "first_saved",
    "latest_saved",
    "oldest_release",
    "newest_release",
]
ArchiveChapterStatus = Literal["available", "partial", "unavailable"]
ArchiveMetricDisplayStatus = Literal["stable_rate", "count_only", "unavailable"]


class StrictArchiveModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArchiveCounts(StrictArchiveModel):
    saved_tracks: int = Field(ge=0)
    saved_albums: int = Field(ge=0)
    saved_artists: int = Field(ge=0)
    saved_shows: int = Field(ge=0)
    playlists: int = Field(ge=0)
    playlist_items: int = Field(ge=0)


class ArchiveCoverage(StrictArchiveModel):
    saved_tracks_with_date: int = Field(ge=0)
    saved_tracks_with_date_pct: float = Field(ge=0, le=100)
    saved_tracks_linked_to_history: int = Field(ge=0)
    saved_tracks_linked_to_history_pct: float = Field(ge=0, le=100)
    saved_tracks_with_known_duration: int = Field(ge=0)
    saved_tracks_with_known_duration_pct: float = Field(ge=0, le=100)
    known_duration_ms: int = Field(ge=0)


class ArchivePeriod(StrictArchiveModel):
    first_saved_at: str | None = None
    latest_saved_at: str | None = None
    first_play_date: str | None = None
    latest_play_date: str | None = None


class ArchiveDateProvenance(StrictArchiveModel):
    oauth: int = Field(ge=0)
    manual: int = Field(ge=0)
    legacy: int = Field(ge=0)
    missing: int = Field(ge=0)


class ArchiveCapabilities(StrictArchiveModel):
    collection_browse: ArchiveCapabilityStatus
    collection_timeline: ArchiveCapabilityStatus
    playback_cross_analysis: ArchiveCapabilityStatus


class ArchiveFeaturedItem(StrictArchiveModel):
    role: ArchiveFeatureRole
    track_name: str
    artist_name: str
    album_name: str | None = None
    added_date: str | None = None
    release_date: str | None = None
    cover_url: str | None = None
    deep_link: str | None = None


class ArchiveOverviewResponse(StrictArchiveModel):
    schema_version: Literal["account_archive_v1"] = "account_archive_v1"
    content_version: Literal["account_archive_v1_0"] = "account_archive_v1_0"
    data_revision: str
    status: ArchiveDataStatus
    counts: ArchiveCounts
    coverage: ArchiveCoverage
    period: ArchivePeriod
    date_provenance: ArchiveDateProvenance
    capabilities: ArchiveCapabilities
    featured_items: list[ArchiveFeaturedItem] = Field(default_factory=list, max_length=4)


class ArchiveFilterContext(StrictArchiveModel):
    context_version: Literal["account_archive_filter_v1"] = "account_archive_filter_v1"
    min_ms: int = Field(ge=0)
    music_only: Literal[True] = True
    merge_enabled: bool
    dynamic_threshold: bool
    max_merge_gap_minutes: int | None = Field(default=None, ge=1, le=240)
    merge_level: int = Field(ge=1, le=3)
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    first_play_at: str | None = None
    latest_play_at: str | None = None
    latest_play_date: str | None = None
    source_revision: str
    track_group_revision: str
    filter_fingerprint: str


class ArchiveGrowthPoint(StrictArchiveModel):
    period: str
    year: int = Field(ge=1900)
    quarter: int | None = Field(default=None, ge=1, le=4)
    saved_tracks: int = Field(ge=0)
    cumulative_saved_tracks: int = Field(ge=0)


class ArchiveJourneyCoverage(StrictArchiveModel):
    saved_tracks: int = Field(ge=0)
    saved_tracks_with_date: int = Field(ge=0)
    invalid_added_dates: int = Field(ge=0)
    saved_tracks_with_known_duration: int = Field(ge=0)
    duration_coverage_pct: float = Field(ge=0, le=100)


class ArchiveDurationFacts(StrictArchiveModel):
    known_duration_ms: int = Field(ge=0)
    release_year_start: int | None = None
    release_year_end: int | None = None


class ArchiveJourneyResponse(StrictArchiveModel):
    schema_version: Literal["account_archive_journey_v1"] = "account_archive_journey_v1"
    content_version: Literal["account_archive_journey_v1_0"] = "account_archive_journey_v1_0"
    data_revision: str
    status: ArchiveChapterStatus
    filter_context: ArchiveFilterContext
    coverage: ArchiveJourneyCoverage
    duration: ArchiveDurationFacts
    annual_growth: list[ArchiveGrowthPoint] = Field(default_factory=list)
    quarterly_growth: list[ArchiveGrowthPoint] = Field(default_factory=list)
    milestones: list[ArchiveFeaturedItem] = Field(default_factory=list, max_length=2)


class ArchiveEntityPreview(StrictArchiveModel):
    track_name: str
    artist_name: str
    album_name: str | None = None
    cover_url: str | None = None
    deep_link: str | None = None
    added_date: str | None = None
    first_play_at: str | None = None
    last_play_at: str | None = None
    effective_plays: int = Field(default=0, ge=0)


class ArchiveCohortCoverage(StrictArchiveModel):
    saved_tracks: int = Field(ge=0)
    matched_saved_tracks: int = Field(ge=0)
    unmatched_saved_tracks: int = Field(ge=0)
    canonical_saved_entities: int = Field(ge=0)
    dated_canonical_entities: int = Field(ge=0)
    invalid_added_dates: int = Field(ge=0)
    effective_play_events: int = Field(ge=0)


class ArchiveEncounterBin(StrictArchiveModel):
    key: Literal["same_day", "days_1_7", "days_8_30", "days_31_90", "days_90_plus"]
    entities: int = Field(ge=0)
    share_pct: float = Field(ge=0, le=100)


class ArchiveEncounterToSave(StrictArchiveModel):
    eligible_entities: int = Field(ge=0)
    no_observed_pre_save_play: int = Field(ge=0)
    bins: list[ArchiveEncounterBin] = Field(default_factory=list, min_length=5, max_length=5)
    examples: list[ArchiveEntityPreview] = Field(default_factory=list, max_length=5)


class ArchiveSymmetricWindow(StrictArchiveModel):
    window_days: Literal[30] = 30
    eligible_entities: int = Field(ge=0)
    before_events: int = Field(ge=0)
    after_events: int = Field(ge=0)
    more_before: int = Field(ge=0)
    equal: int = Field(ge=0)
    more_after: int = Field(ge=0)


class ArchiveReturnWindow(StrictArchiveModel):
    horizon_days: Literal[7, 30, 90, 365]
    eligible_entities: int = Field(ge=0)
    returned_entities: int = Field(ge=0)
    return_rate_pct: float | None = Field(default=None, ge=0, le=100)
    display_status: ArchiveMetricDisplayStatus


class ArchiveAlignedWeek(StrictArchiveModel):
    week_index: int = Field(ge=-4, le=12)
    eligible_entities: int = Field(ge=0)
    entities_with_play: int = Field(ge=0)
    effective_play_events: int = Field(ge=0)
    events_per_eligible: float = Field(ge=0)


class ArchiveRelationshipCounts(StrictArchiveModel):
    recent_active_saved: int = Field(ge=0)
    sleeping_saved: int = Field(ge=0)
    recently_saved_without_recent_play: int = Field(ge=0)
    saved_without_date: int = Field(ge=0)
    frequent_unsaved: int = Field(ge=0)
    unmatched_saved_tracks: int = Field(ge=0)


class ArchiveRelationshipMatrix(StrictArchiveModel):
    recent_window_days: Literal[90] = 90
    frequent_unsaved_min_plays: Literal[5] = 5
    counts: ArchiveRelationshipCounts
    recent_active_examples: list[ArchiveEntityPreview] = Field(default_factory=list, max_length=5)
    sleeping_examples: list[ArchiveEntityPreview] = Field(default_factory=list, max_length=5)
    frequent_unsaved_examples: list[ArchiveEntityPreview] = Field(
        default_factory=list, max_length=5
    )


class ArchiveCohortsResponse(StrictArchiveModel):
    schema_version: Literal["account_archive_cohorts_v1"] = "account_archive_cohorts_v1"
    content_version: Literal["account_archive_cohorts_v1_0"] = "account_archive_cohorts_v1_0"
    data_revision: str
    status: ArchiveChapterStatus
    filter_context: ArchiveFilterContext
    coverage: ArchiveCohortCoverage
    encounter_to_save: ArchiveEncounterToSave
    symmetric_30_day_window: ArchiveSymmetricWindow
    return_windows: list[ArchiveReturnWindow] = Field(
        default_factory=list, min_length=4, max_length=4
    )
    aligned_weeks: list[ArchiveAlignedWeek] = Field(default_factory=list)
    relationship_matrix: ArchiveRelationshipMatrix


class ArchiveReturnsCoverage(StrictArchiveModel):
    saved_tracks: int = Field(ge=0)
    matched_saved_tracks: int = Field(ge=0)
    unmatched_saved_tracks: int = Field(ge=0)
    canonical_saved_entities: int = Field(ge=0)
    dated_canonical_entities: int = Field(ge=0)
    invalid_added_dates: int = Field(ge=0)
    entities_with_effective_history: int = Field(ge=0)
    return_eligible_entities: int = Field(ge=0)
    effective_play_events: int = Field(ge=0)


class ArchiveReturnsSummary(StrictArchiveModel):
    gap_threshold_days: Literal[90] = 90
    return_episodes: int = Field(ge=0)
    returned_entities: int = Field(ge=0)
    multiple_return_entities: int = Field(ge=0)
    recent_30_day_return_entities: int = Field(ge=0)
    recent_90_day_return_entities: int = Field(ge=0)
    current_sleeping_entities: int = Field(ge=0)


class ArchiveReturnStory(StrictArchiveModel):
    track_name: str
    artist_name: str
    album_name: str | None = None
    cover_url: str | None = None
    deep_link: str | None = None
    added_date: str
    previous_play_at: str
    returned_at: str
    dormant_days: int = Field(ge=90)
    return_count: int = Field(ge=1)


class ArchiveSleepingStory(StrictArchiveModel):
    track_name: str
    artist_name: str
    album_name: str | None = None
    cover_url: str | None = None
    deep_link: str | None = None
    added_date: str
    last_play_at: str | None = None
    dormant_days: int = Field(ge=90)
    effective_plays: int = Field(ge=0)


class ArchiveReturnsResponse(StrictArchiveModel):
    schema_version: Literal["account_archive_returns_v1"] = "account_archive_returns_v1"
    content_version: Literal["account_archive_returns_v1_0"] = "account_archive_returns_v1_0"
    data_revision: str
    status: ArchiveChapterStatus
    filter_context: ArchiveFilterContext
    coverage: ArchiveReturnsCoverage
    summary: ArchiveReturnsSummary
    latest_returns: list[ArchiveReturnStory] = Field(default_factory=list, max_length=5)
    longest_returns: list[ArchiveReturnStory] = Field(default_factory=list, max_length=5)
    sleeping_recommendations: list[ArchiveSleepingStory] = Field(default_factory=list, max_length=5)


class ArchiveDiscoveryPeriod(StrictArchiveModel):
    first_search_at: str | None = None
    latest_search_at: str | None = None
    active_days: int = Field(ge=0)


class ArchiveDiscoveryCoverage(StrictArchiveModel):
    normalization_version: Literal["nfkc_casefold_ws_v1"] = "nfkc_casefold_ws_v1"
    burst_gap_minutes: Literal[5] = 5
    raw_search_rows: int = Field(ge=0)
    deduplicated_search_rows: int = Field(ge=0)
    invalid_timestamp_rows: int = Field(ge=0)
    unique_normalized_queries: int = Field(ge=0)
    search_bursts: int = Field(ge=0)
    interaction_records: int = Field(ge=0)
    interaction_bursts: int = Field(ge=0)


class ArchiveInteractionTypeCounts(StrictArchiveModel):
    track: int = Field(ge=0)
    artist: int = Field(ge=0)
    album: int = Field(ge=0)
    playlist: int = Field(ge=0)
    show: int = Field(ge=0)
    episode: int = Field(ge=0)
    other: int = Field(ge=0)


class ArchiveDiscoveryFunnel(StrictArchiveModel):
    display_status: Literal["count_only", "unavailable"]
    playback_window_minutes: Literal[60] = 60
    save_window_days: Literal[30] = 30
    track_interaction_bursts: int = Field(ge=0)
    mapped_track_interaction_bursts: int = Field(ge=0)
    played_within_1h_bursts: int = Field(ge=0)
    currently_saved_within_30d_bursts: int = Field(ge=0)


class ArchiveDiscoveryWeekdayPoint(StrictArchiveModel):
    weekday: int = Field(ge=0, le=6)
    bursts: int = Field(ge=0)


class ArchiveDiscoveryHourPoint(StrictArchiveModel):
    hour: int = Field(ge=0, le=23)
    bursts: int = Field(ge=0)


class ArchiveDiscoveryTrackPreview(StrictArchiveModel):
    track_name: str
    artist_name: str
    album_name: str | None = None
    cover_url: str | None = None
    deep_link: str | None = None
    interaction_at: str
    played_at: str
    added_date: str


class ArchiveDiscoveryResponse(StrictArchiveModel):
    schema_version: Literal["account_archive_discovery_v1"] = "account_archive_discovery_v1"
    content_version: Literal["account_archive_discovery_v1_0"] = "account_archive_discovery_v1_0"
    data_revision: str
    status: ArchiveChapterStatus
    filter_context: ArchiveFilterContext
    period: ArchiveDiscoveryPeriod
    coverage: ArchiveDiscoveryCoverage
    interaction_types: ArchiveInteractionTypeCounts
    funnel: ArchiveDiscoveryFunnel
    weekday_distribution: list[ArchiveDiscoveryWeekdayPoint] = Field(
        default_factory=list, min_length=7, max_length=7
    )
    hour_distribution: list[ArchiveDiscoveryHourPoint] = Field(
        default_factory=list, min_length=24, max_length=24
    )
    observed_saved_examples: list[ArchiveDiscoveryTrackPreview] = Field(
        default_factory=list, max_length=5
    )


ArchiveLibraryEntityType = Literal["tracks", "albums", "artists", "playlists"]
ArchiveLibrarySort = Literal["recent", "oldest", "name", "artist", "tracks"]


class ArchiveLibraryTrackItem(StrictArchiveModel):
    entity_type: Literal["track"] = "track"
    item_key: str
    track_name: str
    artist_name: str
    album_name: str | None = None
    added_date: str | None = None
    cover_url: str | None = None
    deep_link: str | None = None


class ArchiveLibraryAlbumItem(StrictArchiveModel):
    entity_type: Literal["album"] = "album"
    item_key: str
    album_name: str
    artist_name: str
    cover_url: str | None = None
    deep_link: str | None = None


class ArchiveLibraryArtistItem(StrictArchiveModel):
    entity_type: Literal["artist"] = "artist"
    item_key: str
    artist_name: str
    cover_url: str | None = None
    deep_link: str | None = None


class ArchiveLibraryPlaylistTrackPreview(StrictArchiveModel):
    track_name: str
    artist_name: str


class ArchiveLibraryPlaylistItem(StrictArchiveModel):
    entity_type: Literal["playlist"] = "playlist"
    item_key: str
    playlist_id: int = Field(ge=1)
    playlist_name: str
    last_modified_date: str | None = None
    track_count: int = Field(ge=0)
    follower_count: int = Field(ge=0)
    preview_tracks: list[ArchiveLibraryPlaylistTrackPreview] = Field(
        default_factory=list, max_length=3
    )


ArchiveLibraryItem = Union[
    ArchiveLibraryTrackItem,
    ArchiveLibraryAlbumItem,
    ArchiveLibraryArtistItem,
    ArchiveLibraryPlaylistItem,
]


class ArchiveLibraryPageResponse(StrictArchiveModel):
    schema_version: Literal["account_archive_library_v1"] = "account_archive_library_v1"
    content_version: Literal["account_archive_library_v1_0"] = "account_archive_library_v1_0"
    data_revision: str
    entity_type: ArchiveLibraryEntityType
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=50)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    sort: ArchiveLibrarySort
    search_applied: bool
    items: list[ArchiveLibraryItem] = Field(default_factory=list)


class ArchiveMediaObservationWindow(StrictArchiveModel):
    first_play_at: str | None = None
    latest_play_at: str | None = None


class ArchivePodcastShowPreview(StrictArchiveModel):
    show_name: str
    effective_events: int = Field(ge=0)
    effective_ms: int = Field(ge=0)


class ArchivePodcastSummary(StrictArchiveModel):
    source_rows: int = Field(ge=0)
    effective_events: int = Field(ge=0)
    effective_ms: int = Field(ge=0)
    unique_shows: int = Field(ge=0)
    active_months: int = Field(ge=0)
    returning_shows: int = Field(ge=0)
    first_effective_at: str | None = None
    latest_effective_at: str | None = None
    top_shows: list[ArchivePodcastShowPreview] = Field(default_factory=list, max_length=3)


class ArchiveVideoSummary(StrictArchiveModel):
    source_rows: int = Field(ge=0)
    effective_events: int = Field(ge=0)
    effective_ms: int = Field(ge=0)
    unique_tracks: int = Field(ge=0)
    active_days: int = Field(ge=0)
    first_effective_at: str | None = None
    latest_effective_at: str | None = None


class ArchiveAudioVideoComparison(StrictArchiveModel):
    audio_effective_events: int = Field(ge=0)
    audio_effective_ms: int = Field(ge=0)
    video_effective_events: int = Field(ge=0)
    video_effective_ms: int = Field(ge=0)


class ArchiveOtherMediaResponse(StrictArchiveModel):
    schema_version: Literal["account_archive_other_media_v1"] = "account_archive_other_media_v1"
    content_version: Literal["account_archive_other_media_v1_0"] = (
        "account_archive_other_media_v1_0"
    )
    data_revision: str
    status: ArchiveChapterStatus
    filter_context: ArchiveFilterContext
    observation_window: ArchiveMediaObservationWindow
    podcast: ArchivePodcastSummary
    video: ArchiveVideoSummary
    audio_video_comparison: ArchiveAudioVideoComparison
