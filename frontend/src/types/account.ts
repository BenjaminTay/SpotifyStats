/* Account Center types */

// --- Collection Tab ---

export interface CollectionPersonality {
  type: string
  icon: string
  description: string
  metrics: {
    avg_plays_before_save: number
    retention_pct: number
    impulsive_pct: number
  }
}

export interface SaveTimelinePoint {
  year: number
  count: number
}

export interface BiggestSaveDay {
  date: string
  count: number
}

export interface CollectionOverview {
  saved_tracks: number
  saved_albums: number
  saved_artists: number
  playlists: number
  save_timeline: SaveTimelinePoint[]
  biggest_save_day: BiggestSaveDay | null
  first_save_date: string | null
  last_save_date: string | null
}

export interface FirstSaveStory {
  track_name: string
  artist_name: string
  save_date: string
  total_plays: number
  days_since: number
  avg_interval_days: number
}

export interface LifecycleStage {
  label: string
  weeks: string
  avg_per_week: number
}

export interface LifecycleFate {
  evergreen_pct: number
  occasional_pct: number
  forgotten_pct: number
}

export interface SaveLifecycle {
  honeymoon: LifecycleStage
  cooling: LifecycleStage
  settling: LifecycleStage
  fate: LifecycleFate
}

export interface ChemistryExample {
  track_name: string
  artist_name: string
  total_plays: number
  before_save: number
  first_week: number
  days_since_play: number | null
}

export interface ChemistryType {
  count: number
  label: string
  description: string
  icon: string
  examples: ChemistryExample[]
}

export interface SavePlayChemistry {
  love_at_first_listen: ChemistryType
  slow_burn: ChemistryType
  flash_in_the_pan: ChemistryType
  late_bloomer: ChemistryType
  steady_favorite: ChemistryType
  shelf_sitter: ChemistryType
  total_with_dates: number
}

export interface FlipSideTrack {
  track_name: string
  artist_name: string
  play_count: number
}

export interface CoSavedPair {
  artist_a: string
  artist_b: string
  count: number
}

export interface TopSavedArtist {
  artist_name: string
  saved_count: number
  total_plays: number
}

export interface MismatchArtists {
  over_saved: TopSavedArtist[]
  under_saved: TopSavedArtist[]
}

export interface ArchiveFacts {
  total_duration_hrs: number
  year_span: string | null
  oldest_track: { track_name: string; artist_name: string; year: number } | null
}

export interface CollectionInsights {
  available: boolean
  empty?: boolean
  personality: CollectionPersonality
  overview: CollectionOverview
  first_save_story: FirstSaveStory | null
  lifecycle: SaveLifecycle
  chemistry: SavePlayChemistry
  flip_side: FlipSideTrack[]
  keyword_migration: Record<string, string[]>
  co_saved_artists: CoSavedPair[]
  top_saved_artists: TopSavedArtist[]
  mismatch: MismatchArtists
  archive_facts: ArchiveFacts
}

// --- Habits Tab ---

export interface SearchData {
  available: boolean
  empty?: boolean
  total_searches: number
  daily_volume: { date: string; count: number }[]
  top_queries: { query: string; count: number }[]
  intent_dist: { intent: string; count: number }[]
  heatmap: {
    z: number[][]
    x: number[]
    y: string[]
  }
}

export interface ArtistTier {
  rank: number
  artist_name: string
  play_count: number
  hours: number
  tier: string
}

export interface ArtistTiersData {
  available: boolean
  empty?: boolean
  total_artists: number
  tier_hours: Record<string, number>
  tier_counts: Record<string, number>
  artists: ArtistTier[]
}

export interface MarqueeConversion {
  artist_name: string
  segment: string
  impressions: number
  actual_plays: number
  actual_hours: number
}

export interface MarqueeData {
  available: boolean
  empty?: boolean
  conversions: MarqueeConversion[]
}

export interface PodcastShow {
  show_name: string
  hours: number
}

export interface PodcastMonthlyPoint {
  period: string
  hours: number
}

export interface PodcastData {
  available: boolean
  empty?: boolean
  total_plays: number
  total_hours: number
  unique_shows: number
  saved_shows: number
  top_shows: PodcastShow[]
  monthly_trend: PodcastMonthlyPoint[]
}

export interface VideoTrack {
  track_name: string
  artist_name: string
  video_plays: number
  audio_plays: number
}

export interface VideoYearlyPoint {
  year: number
  audio: number
  video: number
}

export interface VideoData {
  available: boolean
  empty?: boolean
  total_video_plays: number
  total_audio_plays: number
  avg_duration_sec: number
  platform_dist: Record<string, number>
  yearly: VideoYearlyPoint[]
  top_video_tracks: VideoTrack[]
}

// --- Identity Tab ---

export interface UserProfile {
  identity_displayName?: string
  identity_firstName?: string
  identity_lastName?: string
  identity_imageUrl?: string
  attr_username?: string
  attr_country?: string
  attr_birthdate?: string
  [key: string]: string | undefined
}

export interface UserFollow {
  type: string
  name: string
}

export interface UserPrompt {
  message: string
  created: string
}

export interface BannedItem {
  name: string
  type: string
}

export interface ProfileStats {
  first_play_date: string | null
  total_audio_plays: number
}

export interface ProfileData {
  profile: UserProfile
  follows: UserFollow[]
  prompts: UserPrompt[]
  stats: ProfileStats
  banned_items: BannedItem[]
}

// --- Wrapped Hub (reused in Identity Tab) ---

export interface WrappedClub {
  club_name: string
  percent_in_club: number
  role: string
  artist_name: string
}

export interface WrappedPartyMetric {
  metric: string
  value: number
}

export interface WrappedListeningAge {
  age: number
  window_start_year: number
  decade_phase: string
}

export interface WrappedArchiveReport {
  column_qualifier: string
  title: string
  description: string
  reason: string
  minutes_listened: number
  filed_under_tags: string
}

export interface WrappedHubData {
  available: boolean
  empty?: boolean
  top_artists: { rank: number; name: string; ms_played: number; percentile: number; cover_url: string }[]
  top_tracks: { rank: number; name: string; play_count: number; ms_played: number; cover_url: string }[]
  top_albums: { rank: number; name: string; play_count: number; ms_played: number; cover_url: string }[]
  clubs: WrappedClub[]
  party_metrics: WrappedPartyMetric[]
  listening_age: WrappedListeningAge | null
  archive_reports: WrappedArchiveReport[]
}

// --- Aggregated Account Data ---

export interface AccountSummary {
  has_account_data: boolean
  profile: ProfileData
  library: {
    available: boolean
    saved_tracks?: number
    saved_albums?: number
    saved_artists?: number
    playlists?: number
    banned_items?: number
    artist_comparison?: { artist_name: string; saved_count: number; play_count: number }[]
    forgotten_tracks?: { track_id: string; never_played: boolean; track_name: string; artist_name: string }[]
  }
  collection_insights: CollectionInsights
  search: SearchData
  insights_tiers: ArtistTiersData
  insights_marquee: MarqueeData
  podcast: PodcastData
  video: VideoData
  inferences: InferencesData
  sound_capsule: SoundCapsuleData
}

// --- Inferences ---

export interface InferencesData {
  available: boolean
  total: number
  categories: Record<string, string[]>
}

// --- Sound Capsule ---

export interface SoundCapsuleHighlight {
  date: string
  type: string
  entity_name: string
  detail: string
}

export interface SoundCapsuleDaily {
  date: string
  stream_count: number
  seconds_played: number
  top_data: string
}

export interface SoundCapsuleData {
  available: boolean
  highlights?: SoundCapsuleHighlight[]
  daily?: SoundCapsuleDaily[]
}
