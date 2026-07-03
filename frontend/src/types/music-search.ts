export type MusicSearchKind = 'track' | 'album' | 'artist'

export interface MusicSearchResult {
  kind: MusicSearchKind
  label: string
  subtitle: string | null
  href: string
  play_events: number
  total_ms: number
  track_id: number | null
  album_name: string | null
  artist_name: string | null
  cover_url: string | null
}

export interface MusicSearchResponse {
  query: string
  limit_per_type: number
  total: number
  tracks: MusicSearchResult[]
  albums: MusicSearchResult[]
  artists: MusicSearchResult[]
}
