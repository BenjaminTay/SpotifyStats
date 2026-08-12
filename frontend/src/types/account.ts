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
  cover_url?: string | null
}

export interface LifecycleExample {
  track_name: string
  artist_name: string
  cover_url?: string | null
}

export interface LifecycleStage {
  label: string
  weeks: string
  avg_per_week: number
  examples?: LifecycleExample[]
}

export interface LifecycleFate {
  evergreen_pct: number
  occasional_pct: number
  forgotten_pct: number
}

export interface LifecycleTrendPoint {
  week: number
  avg_plays: number
  track_count: number
}

export interface TopTrackTrendPoint {
  week: number
  plays: number
}

export interface TopTrackTrend {
  track_name: string
  artist_name: string
  cover_url?: string | null
  data: TopTrackTrendPoint[]
}

export interface SaveLifecycle {
  honeymoon: LifecycleStage
  cooling: LifecycleStage
  settling: LifecycleStage
  fate: LifecycleFate
  honeymoon_examples?: LifecycleExample[]
  cooling_examples?: LifecycleExample[]
  settling_examples?: LifecycleExample[]
}

export interface ChemistryExample {
  track_name: string
  artist_name: string
  total_plays: number
  before_save: number
  first_week: number
  days_since_play: number | null
  cover_url?: string | null
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
  cover_url?: string | null
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
  cover_url?: string | null
}

export interface TopSavedAlbum {
  album_name: string
  artist_name: string
  saved_count: number
  total_plays: number
  cover_url?: string | null
}

export interface ArchiveFacts {
  total_duration_hrs: number
  year_span: string | null
  oldest_track: { track_name: string; artist_name: string; year: number } | null
}

export interface KeywordItem {
  word: string
  weight: number
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
  keyword_migration: Record<string, KeywordItem[]>
  genre_migration: Record<string, string[]>
  co_saved_artists: CoSavedPair[]
  top_saved_artists: TopSavedArtist[]
  top_saved_albums: TopSavedAlbum[]
  archive_facts: ArchiveFacts
  lifecycle_trend?: LifecycleTrendPoint[]
  lifecycle_top_tracks?: TopTrackTrend[]
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
  cover_url?: string | null
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
  conversion_rate: number
  cover_url?: string | null
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
  cover_url?: string | null
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
