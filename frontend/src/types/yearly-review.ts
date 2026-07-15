import type { ArtistLanguageMissingItem, LanguageBucket } from './artist-language-metadata'

export interface WrappedFullHero {
  total_minutes: number
  total_plays: number
  unique_tracks: number
  unique_artists: number
  active_days: number
  avg_minutes_per_day: number
}

export interface PersonalityDimension {
  label: string
  score: number
  desc: string
}

export interface PersonalityResult {
  primary: string
  primary_label: string
  primary_desc: string
  dimensions: Record<string, PersonalityDimension>
}

export interface TopArtistEntry {
  rank: number
  name: string
  plays: number
  hours: number
  cover_url: string
}

export interface TopTrackEntry {
  rank: number
  track_id: number
  name: string
  artist_name: string
  artist_names?: string[]
  plays: number
  hours: number
  cover_url: string
}

export interface TopAlbumEntry {
  rank: number
  name: string
  artist_name: string
  plays: number
  hours: number
  cover_url: string
}

export interface TopLists {
  artists: TopArtistEntry[]
  tracks: TopTrackEntry[]
  albums: TopAlbumEntry[]
}

export interface GenreItem {
  name: string
  label?: string | null
  play_share: number
  hours?: number
  confidence_tier?: 'high' | 'medium' | 'low' | string
  top_artists?: Array<{ artist_name: string; hours: number; share_pct: number }>
  risk_flags?: Array<{ code: string; severity: string; message: string }>
}

export interface MonthlyGenreItem {
  month: number
  genres: Record<string, number>
}

export interface LanguageDistribution {
  eligible_hours: number
  excluded_unattributed_hours: number
  classified_hours: number
  unknown_hours: number
  classified_pct: number
  unknown_pct: number
  buckets: LanguageBucket[]
  source_hours: Record<string, number>
  top_missing: ArtistLanguageMissingItem[]
  caveat: string
}

export interface GenreAxisDistribution {
  axis: 'style' | 'scene' | 'context' | 'role' | string
  label: string
  hours: number
  share_pct: number
  coverage_pct: number
  unknown_hours: number
  unknown_pct: number
  canonical_count: number
  interpretation: string
  buckets: Array<{
    name: string
    label: string | null
    hours: number
    share_pct: number
    overall_share_pct: number
    confidence_tier: string
    top_artists: Array<{ artist_name: string; hours: number; share_pct: number }>
    risk_flags: Array<{ code: string; severity: string; message: string }>
  }>
}

export interface GenrePanorama {
  top_genres: GenreItem[]
  monthly_genres: MonthlyGenreItem[]
  axes?: GenreAxisDistribution[]
  language_dist: LanguageDistribution | null
  coverage?: {
    known_hours: number
    unknown_hours: number
    known_pct: number
    unknown_pct: number
    excluded_unattributed_hours?: number
  } | null
  caveat?: string | null
}

export interface LateNightTrack {
  track_id: number
  name: string
  artist_name: string
  artist_names?: string[]
  plays: number
  cover_url: string
}

export interface LateNightInfo {
  ratio: number
  top_tracks: LateNightTrack[]
}

export interface HourlyDistItem {
  hour: number
  plays: number
}

export interface MonthlyPulseItem {
  month: number
  hours: number
}

export interface TimeStory {
  daily_grid: number[][]
  monthly_pulse: MonthlyPulseItem[]
  hourly_dist: HourlyDistItem[]
  late_night: LateNightInfo | null
}

export interface RegionDist {
  region: string
  flag: string
  play_share: number
}

export interface MusicMap {
  regions: RegionDist[]
  top_overseas_artists: { name: string; region: string; cover_url: string }[]
}

export interface NewArtist {
  name: string
  plays: number
  first_date: string
  cover_url: string
}

export interface ReturningTrack {
  track_id: number
  name: string
  artist_name: string
  artist_names?: string[]
  plays: number
  release_year: number
  cover_url: string
}

export interface LongestLove {
  track_id: number
  name: string
  artist_name: string
  artist_names?: string[]
  span_days: number
  cover_url: string
}

export interface DiscoveryReturns {
  new_artists: NewArtist[]
  returning_tracks: ReturningTrack[]
  longest_love: LongestLove | null
}

export interface ListeningAge {
  age: number
  avg_release_year: number
  description: string
}

export interface AlbumCompletion {
  name: string
  artist_name: string
  completion_pct: number
  cover_url: string
}

export interface ListeningDepth {
  listening_age: ListeningAge | null
  album_completion: AlbumCompletion[]
  deep_listen_ratio: number
}

export interface MostActiveDay {
  date: string
  plays: number
  top_track: { name: string; cover_url: string }
}

export interface ListenMoment {
  hour: number
  track: { name: string; artist_name: string; cover_url: string }
}

export interface LongestStreak {
  days: number
  start: string
  end: string
}

export interface SpecialMoments {
  most_active_day: MostActiveDay | null
  earliest_listen: ListenMoment | null
  latest_listen: ListenMoment | null
  longest_streak: LongestStreak | null
}

export interface MonthlyDrillItem {
  month: number
  total_hours: number
  top_tracks: { track_id: number; name: string; artist_name: string; artist_names?: string[]; plays: number; cover_url: string }[]
  top_artist: { name: string; cover_url: string } | null
}

export interface LastYearComparison {
  total_hours_change: number | null
  plays_change: number | null
  tracks_change: number | null
  artists_change: number | null
  active_days_change: number | null
}

export interface TopVsAlltimeMark {
  name: string
  is_new: boolean
  is_classic: boolean
}

export interface YearComparison {
  last_year: LastYearComparison | null
  top_vs_alltime: Record<string, TopVsAlltimeMark[]>
}

export interface WrappedFullResponse {
  year: number
  empty: boolean
  hero: WrappedFullHero | null
  personality: PersonalityResult | null
  top_lists: TopLists | null
  genre_panorama: GenrePanorama | null
  time_story: TimeStory | null
  music_map: MusicMap | null
  discovery_returns: DiscoveryReturns | null
  listening_depth: ListeningDepth | null
  special_moments: SpecialMoments | null
  monthly_drilldown: MonthlyDrillItem[]
  comparison: YearComparison | null
}
