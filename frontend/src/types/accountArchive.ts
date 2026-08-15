export type ArchiveStatus = 'ready' | 'partial' | 'empty'
export type ArchiveChapterStatus = 'available' | 'partial' | 'unavailable'
export type ArchiveCapabilityStatus = 'available' | 'partial' | 'unavailable'
export type ArchiveDisplayStatus = 'stable_rate' | 'count_only' | 'unavailable'
export type ArchiveSectionKey =
  | 'cover'
  | 'journey'
  | 'cohorts'
  | 'relationships'
  | 'returns'
  | 'discovery'
  | 'library'
  | 'other-media'

export interface ArchiveFeaturedItem {
  role: 'first_saved' | 'latest_saved' | 'oldest_release' | 'newest_release'
  track_name: string
  artist_name: string
  album_name: string | null
  added_date: string | null
  release_date: string | null
  cover_url: string | null
  deep_link: string | null
}

export interface ArchiveOverview {
  schema_version: 'account_archive_v1'
  content_version: 'account_archive_v1_0'
  data_revision: string
  status: ArchiveStatus
  counts: {
    saved_tracks: number
    saved_albums: number
    saved_artists: number
    saved_shows: number
    playlists: number
    playlist_items: number
  }
  coverage: {
    saved_tracks_with_date: number
    saved_tracks_with_date_pct: number
    saved_tracks_linked_to_history: number
    saved_tracks_linked_to_history_pct: number
    saved_tracks_with_known_duration: number
    saved_tracks_with_known_duration_pct: number
    known_duration_ms: number
  }
  period: {
    first_saved_at: string | null
    latest_saved_at: string | null
    first_play_date: string | null
    latest_play_date: string | null
  }
  date_provenance: { oauth: number; manual: number; legacy: number; missing: number }
  capabilities: {
    collection_browse: ArchiveCapabilityStatus
    collection_timeline: ArchiveCapabilityStatus
    playback_cross_analysis: ArchiveCapabilityStatus
  }
  featured_items: ArchiveFeaturedItem[]
}

export interface ArchiveFilterContext {
  context_version: 'account_archive_filter_v2'
  min_ms: number
  music_only: true
  merge_enabled: boolean
  dynamic_threshold: boolean
  max_merge_gap_minutes: number
  merge_level: number
  timezone: 'Asia/Shanghai'
  first_play_at: string | null
  latest_play_at: string | null
  latest_play_date: string | null
  source_revision: string
  track_group_revision: string
  filter_fingerprint: string
}

export interface ArchiveEntityPreview {
  track_name: string
  artist_name: string
  album_name: string | null
  cover_url: string | null
  deep_link: string | null
  added_date: string | null
  first_play_at: string | null
  last_play_at: string | null
  effective_plays: number
  days_to_save: number | null
}

export interface ArchiveCollectionMilestone {
  ordinal: number
  track_name: string
  artist_name: string
  album_name: string | null
  added_date: string
  cover_url: string | null
  deep_link: string | null
}

export interface ArchiveJourney {
  schema_version: 'account_archive_journey_v2'
  content_version: 'account_archive_journey_v2_0'
  data_revision: string
  status: ArchiveChapterStatus
  filter_context: ArchiveFilterContext
  coverage: {
    saved_tracks: number
    saved_tracks_with_date: number
    invalid_added_dates: number
    saved_tracks_with_known_duration: number
    duration_coverage_pct: number
  }
  duration: {
    known_duration_ms: number
    release_year_start: number | null
    release_year_end: number | null
  }
  annual_growth: ArchiveGrowthPoint[]
  quarterly_growth: ArchiveGrowthPoint[]
  milestones: ArchiveCollectionMilestone[]
}

export interface ArchiveGrowthPoint {
  period: string
  year: number
  quarter: number | null
  saved_tracks: number
  cumulative_saved_tracks: number
}

export interface ArchiveCohorts {
  schema_version: 'account_archive_cohorts_v2'
  content_version: 'account_archive_cohorts_v2_0'
  data_revision: string
  status: ArchiveChapterStatus
  filter_context: ArchiveFilterContext
  coverage: {
    saved_tracks: number
    matched_saved_tracks: number
    unmatched_saved_tracks: number
    canonical_saved_entities: number
    dated_canonical_entities: number
    invalid_added_dates: number
    effective_play_events: number
  }
  encounter_to_save: {
    eligible_entities: number
    no_observed_pre_save_play: number
    bins: Array<{
      key: 'same_day' | 'days_1_7' | 'days_8_30' | 'days_31_90' | 'days_90_plus'
      entities: number
      share_pct: number
    }>
    examples: ArchiveEntityPreview[]
  }
  symmetric_30_day_window: {
    window_days: 30
    eligible_entities: number
    before_events: number
    after_events: number
    more_before: number
    equal: number
    more_after: number
  }
  return_windows: Array<{
    horizon_days: 7 | 30 | 90 | 365
    eligible_entities: number
    returned_entities: number
    return_rate_pct: number | null
    display_status: ArchiveDisplayStatus
  }>
  vitality_metrics: Array<{
    key: 'within_7d' | 'days_8_30' | 'after_180d' | 'after_365d'
    start_day: number
    end_day: number | null
    eligible_entities: number
    returned_entities: number
    return_rate_pct: number | null
    display_status: ArchiveDisplayStatus
  }>
  aligned_weeks: Array<{
    week_index: number
    eligible_entities: number
    entities_with_play: number
    effective_play_events: number
    events_per_eligible: number
  }>
  relationship_matrix: {
    recent_window_days: 90
    frequent_unsaved_min_plays: 5
    counts: {
      recent_active_saved: number
      sleeping_saved: number
      recently_saved_without_recent_play: number
      saved_without_date: number
      frequent_unsaved: number
      unmatched_saved_tracks: number
    }
    recent_active_examples: ArchiveEntityPreview[]
    sleeping_examples: ArchiveEntityPreview[]
    frequent_unsaved_examples: ArchiveEntityPreview[]
  }
}

export interface ArchiveReturnStory {
  track_name: string
  artist_name: string
  album_name: string | null
  cover_url: string | null
  deep_link: string | null
  added_date: string
  previous_play_at: string
  returned_at: string
  dormant_days: number
  return_count: number
}

export interface ArchiveSleepingStory {
  track_name: string
  artist_name: string
  album_name: string | null
  cover_url: string | null
  deep_link: string | null
  added_date: string
  last_play_at: string | null
  dormant_days: number
  effective_plays: number
}

export interface ArchiveReturns {
  schema_version: 'account_archive_returns_v1'
  content_version: 'account_archive_returns_v1_0'
  data_revision: string
  status: ArchiveChapterStatus
  filter_context: ArchiveFilterContext
  coverage: {
    saved_tracks: number
    matched_saved_tracks: number
    unmatched_saved_tracks: number
    canonical_saved_entities: number
    dated_canonical_entities: number
    invalid_added_dates: number
    entities_with_effective_history: number
    return_eligible_entities: number
    effective_play_events: number
  }
  summary: {
    gap_threshold_days: 90
    return_episodes: number
    returned_entities: number
    multiple_return_entities: number
    recent_30_day_return_entities: number
    recent_90_day_return_entities: number
    current_sleeping_entities: number
  }
  latest_returns: ArchiveReturnStory[]
  longest_returns: ArchiveReturnStory[]
  sleeping_recommendations: ArchiveSleepingStory[]
}

export interface ArchiveDiscovery {
  schema_version: 'account_archive_discovery_v1'
  content_version: 'account_archive_discovery_v1_0'
  data_revision: string
  status: ArchiveChapterStatus
  filter_context: ArchiveFilterContext
  period: { first_search_at: string | null; latest_search_at: string | null; active_days: number }
  coverage: {
    normalization_version: 'nfkc_casefold_ws_v1'
    burst_gap_minutes: 5
    raw_search_rows: number
    deduplicated_search_rows: number
    invalid_timestamp_rows: number
    unique_normalized_queries: number
    search_bursts: number
    interaction_records: number
    interaction_bursts: number
  }
  interaction_types: {
    track: number
    artist: number
    album: number
    playlist: number
    show: number
    episode: number
    other: number
  }
  funnel: {
    display_status: 'count_only' | 'unavailable'
    playback_window_minutes: 60
    save_window_days: 30
    track_interaction_bursts: number
    mapped_track_interaction_bursts: number
    played_within_1h_bursts: number
    currently_saved_within_30d_bursts: number
  }
  weekday_distribution: Array<{ weekday: number; bursts: number }>
  hour_distribution: Array<{ hour: number; bursts: number }>
  observed_saved_examples: Array<
    ArchiveEntityPreview & { interaction_at: string; played_at: string; added_date: string }
  >
}

export type ArchiveLibraryEntityType = 'tracks' | 'albums' | 'artists' | 'playlists'
export type ArchiveLibrarySort = 'recent' | 'oldest' | 'name' | 'artist' | 'tracks'

interface ArchiveLibraryBaseItem {
  item_key: string
}

export interface ArchiveLibraryTrackItem extends ArchiveLibraryBaseItem {
  entity_type: 'track'
  track_name: string
  artist_name: string
  album_name: string | null
  added_date: string | null
  cover_url: string | null
  deep_link: string | null
}

export interface ArchiveLibraryAlbumItem extends ArchiveLibraryBaseItem {
  entity_type: 'album'
  album_name: string
  artist_name: string
  cover_url: string | null
  deep_link: string | null
}

export interface ArchiveLibraryArtistItem extends ArchiveLibraryBaseItem {
  entity_type: 'artist'
  artist_name: string
  cover_url: string | null
  deep_link: string | null
}

export interface ArchiveLibraryPlaylistItem extends ArchiveLibraryBaseItem {
  entity_type: 'playlist'
  playlist_id: number
  playlist_name: string
  last_modified_date: string | null
  track_count: number
  follower_count: number
  preview_tracks: Array<{ track_name: string; artist_name: string }>
}

export type ArchiveLibraryItem =
  | ArchiveLibraryTrackItem
  | ArchiveLibraryAlbumItem
  | ArchiveLibraryArtistItem
  | ArchiveLibraryPlaylistItem

export interface ArchiveLibraryPage {
  schema_version: 'account_archive_library_v1'
  content_version: 'account_archive_library_v1_0'
  data_revision: string
  entity_type: ArchiveLibraryEntityType
  page: number
  limit: number
  total: number
  total_pages: number
  sort: ArchiveLibrarySort
  search_applied: boolean
  items: ArchiveLibraryItem[]
}

export interface ArchiveOtherMedia {
  schema_version: 'account_archive_other_media_v2'
  content_version: 'account_archive_other_media_v2_0'
  data_revision: string
  status: ArchiveChapterStatus
  filter_context: ArchiveFilterContext
  observation_window: { first_play_at: string | null; latest_play_at: string | null }
  podcast: {
    source_rows: number
    effective_events: number
    effective_ms: number
    unique_shows: number
    active_months: number
    returning_shows: number
    first_effective_at: string | null
    latest_effective_at: string | null
    top_shows: Array<{
      show_name: string
      publisher: string | null
      cover_url: string | null
      effective_events: number
      effective_ms: number
    }>
  }
  video: {
    source_rows: number
    effective_events: number
    effective_ms: number
    unique_tracks: number
    active_days: number
    first_effective_at: string | null
    latest_effective_at: string | null
    top_tracks: Array<{
      track_name: string
      artist_name: string
      album_name: string | null
      cover_url: string | null
      deep_link: string | null
      effective_events: number
      effective_ms: number
    }>
  }
  audio_video_comparison: {
    audio_effective_events: number
    audio_effective_ms: number
    video_effective_events: number
    video_effective_ms: number
  }
}
