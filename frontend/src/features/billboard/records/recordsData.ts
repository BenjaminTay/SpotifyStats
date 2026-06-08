import type { BillboardDataResponse } from '@/types/billboard'

export interface CoverMaps {
  track: Map<number, string | null>
  artist: Map<string, string | null>
  album: Map<string, string | null>
}

export function buildCoverMaps(data: BillboardDataResponse): CoverMaps {
  const track = new Map<number, string | null>()
  const artist = new Map<string, string | null>()
  const album = new Map<string, string | null>()
  for (const e of data.weekly) { if (!track.has(e.track_id) && e.cover_url) track.set(e.track_id, e.cover_url) }
  for (const e of data.weekly_artist) { if (!artist.has(e.artist_name) && e.cover_url) artist.set(e.artist_name, e.cover_url) }
  for (const e of data.weekly) { if (!artist.has(e.artist_name) && e.cover_url) artist.set(e.artist_name, e.cover_url) }
  for (const e of data.weekly_album) { if (!album.has(e.album_name) && e.cover_url) album.set(e.album_name, e.cover_url) }
  return { track, artist, album }
}
