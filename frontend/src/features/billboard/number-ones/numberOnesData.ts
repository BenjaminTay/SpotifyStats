import type {
  BillboardAllTimeResponse,
  WeeklyAlbumEntry,
  WeeklyArtistEntry,
  WeeklyTrackEntry,
} from '@/types/billboard'

export type SubTabKey = 'tracks' | 'albums' | 'artists'

export const SUB_TABS: { key: SubTabKey; label: string }[] = [
  { key: 'tracks', label: '单曲榜' },
  { key: 'albums', label: '专辑榜' },
  { key: 'artists', label: '艺人榜' },
]

export interface TrackNo1Info {
  track_id: number
  track_name: string
  artist_name: string
  artist_names?: string[]
  cover_url?: string | null
  weeks_at_no1: number
  power_score: number
  total_no1_plays: number
  longest_streak: number
  no1_weeks: string[]
}

export interface AlbumNo1Info {
  album_name: string
  artist_name: string
  cover_url?: string | null
  weeks_at_no1: number
  power_score: number
  longest_streak: number
  no1_weeks: string[]
}

export interface ArtistNo1Info {
  artist_name: string
  cover_url?: string | null
  weeks_at_no1: number
  power_score: number
  longest_streak: number
  no1_weeks: string[]
}

export type AlbumNo1WithPkWks = WeeklyAlbumEntry & { album_pk_wks: number }
export type ArtistNo1WithPkWks = WeeklyArtistEntry & { artist_pk_wks: number }

export interface NumberOnesComputed {
  trackNo1List: WeeklyTrackEntry[]
  albumNo1List: WeeklyAlbumEntry[]
  artistNo1List: WeeklyArtistEntry[]
  trackLongest: { name: string; artist: string; streak: number }
  albumLongest: { name: string; artist: string; streak: number }
  artistLongest: { name: string; streak: number }
  trackNo1WeeksSorted: TrackNo1Info[]
  albumNo1WeeksSorted: AlbumNo1Info[]
  artistNo1WeeksSorted: ArtistNo1Info[]
  albumNo1WithPkWks: AlbumNo1WithPkWks[]
  artistNo1WithPkWks: ArtistNo1WithPkWks[]
  trackMaxPlays: number
  albumMaxPlays: number
  artistMaxPlays: number
}

export interface YearFilteredNumberOnes {
  tracks: WeeklyTrackEntry[]
  albums: AlbumNo1WithPkWks[]
  artists: ArtistNo1WithPkWks[]
  trackMaxPlays: number
  albumMaxPlays: number
  artistMaxPlays: number
  uniqueTrackCount: number
  uniqueAlbumCount: number
  uniqueArtistCount: number
}

export const EMPTY_NUMBER_ONES: NumberOnesComputed = {
  trackNo1List: [],
  albumNo1List: [],
  artistNo1List: [],
  trackLongest: { name: '', artist: '', streak: 0 },
  albumLongest: { name: '', artist: '', streak: 0 },
  artistLongest: { name: '', streak: 0 },
  trackNo1WeeksSorted: [],
  albumNo1WeeksSorted: [],
  artistNo1WeeksSorted: [],
  albumNo1WithPkWks: [],
  artistNo1WithPkWks: [],
  trackMaxPlays: 1,
  albumMaxPlays: 1,
  artistMaxPlays: 1,
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n)
}

export function formatWeekStart(iso: string): string {
  if (!iso) return ''
  const date = new Date(`${iso}T00:00:00`)
  return `${date.getFullYear()}/${date.getMonth() + 1}/${date.getDate()}`
}

function longestStreak(weeks: string[]): number {
  const sorted = [...new Set(weeks)].sort()
  if (sorted.length < 2) return sorted.length
  let max = 1
  let current = 1
  for (let index = 1; index < sorted.length; index++) {
    const diff =
      (new Date(sorted[index]).getTime() - new Date(sorted[index - 1]).getTime()) /
      (1000 * 60 * 60 * 24)
    if (Math.abs(diff - 7) < 1) {
      current++
      max = Math.max(max, current)
    } else {
      current = 1
    }
  }
  return max
}

export function buildNumberOnes(data: BillboardAllTimeResponse | null | undefined): NumberOnesComputed {
  if (!data) return EMPTY_NUMBER_ONES

  const { weekly, weekly_album, weekly_artist, power_scores, album_power_scores, artist_power_scores } = data

  const psByTrack = new Map<number, number>()
  for (const score of power_scores) psByTrack.set(score.track_id, score.power_score)
  const psByAlbum = new Map<string, number>()
  for (const score of album_power_scores) psByAlbum.set(`${score.album_name}|||${score.artist_name}`, score.power_score)
  const psByArtist = new Map<string, number>()
  for (const score of artist_power_scores) psByArtist.set(score.artist_name, score.power_score)

  const trackNo1s = weekly
    .filter((entry) => entry.rank === 1)
    .sort((a, b) => b.billboard_week.localeCompare(a.billboard_week))
  const trackMaxPlays = trackNo1s.reduce((max, entry) => Math.max(max, entry.play_count), 0)
  const trackNo1Map = new Map<number, WeeklyTrackEntry[]>()
  for (const entry of trackNo1s) {
    const entries = trackNo1Map.get(entry.track_id) ?? []
    entries.push(entry)
    trackNo1Map.set(entry.track_id, entries)
  }

  const trackNo1Infos: TrackNo1Info[] = []
  let trackLongestStreak = 0
  let trackLongestName = ''
  let trackLongestArtist = ''
  for (const [trackId, entries] of trackNo1Map) {
    const weeks = entries.map((entry) => entry.billboard_week)
    const streak = longestStreak(weeks)
    trackNo1Infos.push({
      track_id: trackId,
      track_name: entries[0].track_name,
      artist_name: entries[0].artist_name,
      artist_names: entries[0].artist_names,
      cover_url: entries[0].cover_url,
      weeks_at_no1: new Set(weeks).size,
      power_score: psByTrack.get(trackId) ?? 0,
      total_no1_plays: entries.reduce((sum, entry) => sum + entry.play_count, 0),
      longest_streak: streak,
      no1_weeks: weeks,
    })
    if (streak > trackLongestStreak) {
      trackLongestStreak = streak
      trackLongestName = entries[0].track_name
      trackLongestArtist = entries[0].artist_name
    }
  }
  trackNo1Infos.sort((a, b) => b.weeks_at_no1 - a.weeks_at_no1 || b.power_score - a.power_score)

  const albumNo1s = weekly_album
    .filter((entry) => entry.rank === 1)
    .sort((a, b) => b.billboard_week.localeCompare(a.billboard_week))
  const albumMaxPlays = albumNo1s.reduce((max, entry) => Math.max(max, entry.play_count), 0)
  const albumNo1Map = new Map<string, WeeklyAlbumEntry[]>()
  for (const entry of albumNo1s) {
    const key = `${entry.album_name}|||${entry.artist_name}`
    const entries = albumNo1Map.get(key) ?? []
    entries.push(entry)
    albumNo1Map.set(key, entries)
  }

  const albumNo1Infos: AlbumNo1Info[] = []
  let albumLongestStreak = 0
  let albumLongestName = ''
  let albumLongestArtist = ''
  for (const entries of albumNo1Map.values()) {
    const weeks = entries.map((entry) => entry.billboard_week)
    const streak = longestStreak(weeks)
    albumNo1Infos.push({
      album_name: entries[0].album_name,
      artist_name: entries[0].artist_name,
      cover_url: entries[0].cover_url,
      weeks_at_no1: new Set(weeks).size,
      power_score: psByAlbum.get(`${entries[0].album_name}|||${entries[0].artist_name}`) ?? 0,
      longest_streak: streak,
      no1_weeks: weeks,
    })
    if (streak > albumLongestStreak) {
      albumLongestStreak = streak
      albumLongestName = entries[0].album_name
      albumLongestArtist = entries[0].artist_name
    }
  }
  albumNo1Infos.sort((a, b) => b.weeks_at_no1 - a.weeks_at_no1 || b.power_score - a.power_score)

  const artistNo1s = weekly_artist
    .filter((entry) => entry.rank === 1)
    .sort((a, b) => b.billboard_week.localeCompare(a.billboard_week))
  const artistMaxPlays = artistNo1s.reduce((max, entry) => Math.max(max, entry.play_count), 0)
  const artistNo1Map = new Map<string, WeeklyArtistEntry[]>()
  for (const entry of artistNo1s) {
    const entries = artistNo1Map.get(entry.artist_name) ?? []
    entries.push(entry)
    artistNo1Map.set(entry.artist_name, entries)
  }

  const artistNo1Infos: ArtistNo1Info[] = []
  let artistLongestStreak = 0
  let artistLongestName = ''
  for (const [name, entries] of artistNo1Map) {
    const weeks = entries.map((entry) => entry.billboard_week)
    const streak = longestStreak(weeks)
    artistNo1Infos.push({
      artist_name: name,
      cover_url: entries[0].cover_url,
      weeks_at_no1: new Set(weeks).size,
      power_score: psByArtist.get(name) ?? 0,
      longest_streak: streak,
      no1_weeks: weeks,
    })
    if (streak > artistLongestStreak) {
      artistLongestStreak = streak
      artistLongestName = name
    }
  }
  artistNo1Infos.sort((a, b) => b.weeks_at_no1 - a.weeks_at_no1 || b.power_score - a.power_score)

  const albumNo1WithPkWks = addAlbumPeakWeeks(albumNo1s)
  const artistNo1WithPkWks = addArtistPeakWeeks(artistNo1s)

  return {
    trackNo1List: trackNo1s,
    albumNo1List: albumNo1s,
    artistNo1List: artistNo1s,
    trackLongest: { name: trackLongestName, artist: trackLongestArtist, streak: trackLongestStreak },
    albumLongest: { name: albumLongestName, artist: albumLongestArtist, streak: albumLongestStreak },
    artistLongest: { name: artistLongestName, streak: artistLongestStreak },
    trackNo1WeeksSorted: trackNo1Infos,
    albumNo1WeeksSorted: albumNo1Infos,
    artistNo1WeeksSorted: artistNo1Infos,
    albumNo1WithPkWks,
    artistNo1WithPkWks,
    trackMaxPlays,
    albumMaxPlays,
    artistMaxPlays,
  }
}

function addAlbumPeakWeeks(albumNo1s: WeeklyAlbumEntry[]): AlbumNo1WithPkWks[] {
  const peakMap = new Map<string, number>()
  const withPeakWeeks: AlbumNo1WithPkWks[] = []
  for (const entry of [...albumNo1s].sort((a, b) => a.billboard_week.localeCompare(b.billboard_week))) {
    const key = `${entry.album_name}|||${entry.artist_name}`
    const current = (peakMap.get(key) ?? 0) + 1
    peakMap.set(key, current)
    withPeakWeeks.push({ ...entry, album_pk_wks: current })
  }
  return withPeakWeeks.reverse()
}

function addArtistPeakWeeks(artistNo1s: WeeklyArtistEntry[]): ArtistNo1WithPkWks[] {
  const peakMap = new Map<string, number>()
  const withPeakWeeks: ArtistNo1WithPkWks[] = []
  for (const entry of [...artistNo1s].sort((a, b) => a.billboard_week.localeCompare(b.billboard_week))) {
    const current = (peakMap.get(entry.artist_name) ?? 0) + 1
    peakMap.set(entry.artist_name, current)
    withPeakWeeks.push({ ...entry, artist_pk_wks: current })
  }
  return withPeakWeeks.reverse()
}

export function availableYearsForTab(computed: NumberOnesComputed, activeTab: SubTabKey): number[] {
  const entries =
    activeTab === 'tracks' ? computed.trackNo1List
      : activeTab === 'albums' ? computed.albumNo1List
        : computed.artistNo1List
  const years = new Set<number>()
  for (const entry of entries) {
    years.add(new Date(`${entry.billboard_week}T00:00:00`).getFullYear())
  }
  return [...years].sort((a, b) => b - a)
}

export function filterNumberOnesByYear(
  computed: NumberOnesComputed,
  selectedYear: number,
): YearFilteredNumberOnes {
  const filterFn = (entry: { billboard_week: string }) =>
    new Date(`${entry.billboard_week}T00:00:00`).getFullYear() === selectedYear

  const tracks = computed.trackNo1List.filter(filterFn)
  const albums = computed.albumNo1WithPkWks.filter(filterFn)
  const artists = computed.artistNo1WithPkWks.filter(filterFn)

  return {
    tracks,
    albums,
    artists,
    trackMaxPlays: Math.max(...tracks.map((entry) => entry.play_count), 1),
    albumMaxPlays: Math.max(...albums.map((entry) => entry.play_count), 1),
    artistMaxPlays: Math.max(...artists.map((entry) => entry.play_count), 1),
    uniqueTrackCount: new Set(tracks.map((entry) => entry.track_id)).size,
    uniqueAlbumCount: new Set(
      computed.albumNo1List.filter(filterFn).map((entry) => `${entry.album_name}|||${entry.artist_name}`),
    ).size,
    uniqueArtistCount: new Set(
      computed.artistNo1List.filter(filterFn).map((entry) => entry.artist_name),
    ).size,
  }
}
