import { useState, useEffect, useMemo, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useBillboard } from '@/hooks/useBillboard'
import { GlassCard } from '@/components/shared/GlassCard'
import { BillboardSubNav } from '@/components/shared/BillboardSubNav'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle, ArrowUpDown, ArrowUp, ArrowDown, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { displayName } from '@/lib/chinese'
import type {
  PowerScoreEntry,
  TrackSummary,
  AlbumTrackCounts,
  ArtistTrackCounts,
} from '@/types/billboard'

// ── helpers ──────────────────────────────────────────────────

function formatNumber(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n)
}

function rankColorClass(rank: number): string {
  if (rank === 1) return 'text-accent-foreground'
  if (rank === 2) return 'text-muted-foreground'
  if (rank === 3) return 'text-[#C17A4E] dark:text-[#C97B6B]'
  return 'text-muted-foreground'
}

const COLUMN_WIDTH_DEFAULTS: Record<string, number> = {
  _name_tracks: 200,
  _name_albums: 200,
  _name_artists: 200,
  peak_position: 72,
  weeks_at_peak: 72,
  weeks_on_chart: 72,
  weeks_top5: 72,
  weeks_top10: 72,
  power_score: 80,
  power_rank: 72,
  total_chart_plays: 110,
  total_plays: 110,
  total_tracks: 72,
  top1_tracks: 80,
  top5_tracks: 72,
  top10_tracks: 72,
  num_no1_albums: 80,
  top5_albums: 80,
  top10_albums: 80,
}

const COL_WIDTHS_KEY = 'billboard-alltime-col-widths'

function loadColumnWidths(): Record<string, number> {
  try {
    const saved = localStorage.getItem(COL_WIDTHS_KEY)
    if (saved) return JSON.parse(saved)
  } catch { /* ignore */ }
  return {}
}

function saveColumnWidths(widths: Record<string, number>) {
  try { localStorage.setItem(COL_WIDTHS_KEY, JSON.stringify(widths)) } catch { /* ignore */ }
}

// ── merged row types ─────────────────────────────────────────

interface MergedTrackRow {
  track_id: number
  track_name: string
  artist_name: string
  cover_url: string | null
  weeks_on_chart: number
  peak_position: number
  weeks_at_peak: number
  weeks_top5: number
  weeks_top10: number
  power_score: number
  power_rank: number
  total_chart_plays: number
  is_debut_no1: boolean
}

interface MergedAlbumRow {
  album_name: string
  artist_name: string
  cover_url: string | null
  weeks_on_chart: number
  peak_position: number
  weeks_at_peak: number
  weeks_top5: number
  weeks_top10: number
  total_tracks: number
  top1_tracks: number
  top5_tracks: number
  top10_tracks: number
  power_score: number
  power_rank: number
  total_plays: number
  is_debut_no1: boolean
}

interface MergedArtistRow {
  artist_name: string
  cover_url: string | null
  weeks_on_chart: number
  peak_position: number
  weeks_at_peak: number
  weeks_top5: number
  weeks_top10: number
  total_tracks: number
  top1_tracks: number
  top5_tracks: number
  top10_tracks: number
  num_no1_albums: number
  top5_albums: number
  top10_albums: number
  power_score: number
  power_rank: number
  total_plays: number
  is_debut_no1: boolean
}

type EntityTab = 'tracks' | 'albums' | 'artists'

let cachedEntityTab: EntityTab = 'tracks'
let cachedPeakFilter: PeakFilter = 'all'
let cachedPage = 1
let cachedSortKeyTrack = 'power_score'
let cachedSortDirTrack: 'asc' | 'desc' = 'desc'
let cachedSortKeyAlbum = 'power_score'
let cachedSortDirAlbum: 'asc' | 'desc' = 'desc'
let cachedSortKeyArtist = 'power_score'
let cachedSortDirArtist: 'asc' | 'desc' = 'desc'

type PeakFilter = 'all' | 'no1' | 'top5' | 'top10' | 'debut_no1'

// ── column definitions ───────────────────────────────────────

interface ColumnDef<T> {
  key: string
  label: string
  align: 'left' | 'right' | 'center'
  getValue: (row: T) => number | string
  format: (row: T) => string
  sortable: boolean
  rankStyle?: boolean
}

const TRACK_COLUMNS: ColumnDef<MergedTrackRow>[] = [
  {
    key: 'peak_position', label: '排名峰值', align: 'right',
    getValue: (r) => r.peak_position, format: (r) => String(r.peak_position), sortable: true,
    rankStyle: true,
  },
  {
    key: 'weeks_at_peak', label: '峰值周数', align: 'right',
    getValue: (r) => r.weeks_at_peak, format: (r) => formatNumber(r.weeks_at_peak), sortable: true,
  },
  {
    key: 'weeks_on_chart', label: '在榜周数', align: 'right',
    getValue: (r) => r.weeks_on_chart, format: (r) => formatNumber(r.weeks_on_chart), sortable: true,
  },
  {
    key: 'weeks_top5', label: 'Top5周数', align: 'right',
    getValue: (r) => r.weeks_top5, format: (r) => formatNumber(r.weeks_top5), sortable: true,
  },
  {
    key: 'weeks_top10', label: 'Top10周数', align: 'right',
    getValue: (r) => r.weeks_top10, format: (r) => formatNumber(r.weeks_top10), sortable: true,
  },
  {
    key: 'power_score', label: '走势评分', align: 'right',
    getValue: (r) => r.power_score, format: (r) => formatNumber(r.power_score), sortable: true,
  },
  {
    key: 'power_rank', label: '走势排名', align: 'right',
    getValue: (r) => r.power_rank, format: (r) => String(r.power_rank), sortable: true,
    rankStyle: true,
  },
  {
    key: 'total_chart_plays', label: '总播放次数', align: 'right',
    getValue: (r) => r.total_chart_plays, format: (r) => formatNumber(r.total_chart_plays), sortable: true,
  },
]

const ALBUM_COLUMNS: ColumnDef<MergedAlbumRow>[] = [
  {
    key: 'peak_position', label: '排名峰值', align: 'right',
    getValue: (r) => r.peak_position, format: (r) => String(r.peak_position), sortable: true,
    rankStyle: true,
  },
  {
    key: 'weeks_at_peak', label: '峰值周数', align: 'right',
    getValue: (r) => r.weeks_at_peak, format: (r) => formatNumber(r.weeks_at_peak), sortable: true,
  },
  {
    key: 'weeks_on_chart', label: '在榜周数', align: 'right',
    getValue: (r) => r.weeks_on_chart, format: (r) => formatNumber(r.weeks_on_chart), sortable: true,
  },
  {
    key: 'weeks_top5', label: 'Top5周数', align: 'right',
    getValue: (r) => r.weeks_top5, format: (r) => formatNumber(r.weeks_top5), sortable: true,
  },
  {
    key: 'weeks_top10', label: 'Top10周数', align: 'right',
    getValue: (r) => r.weeks_top10, format: (r) => formatNumber(r.weeks_top10), sortable: true,
  },
  {
    key: 'total_tracks', label: '入榜曲数', align: 'right',
    getValue: (r) => r.total_tracks, format: (r) => formatNumber(r.total_tracks), sortable: true,
  },
  {
    key: 'top1_tracks', label: '冠军歌曲数', align: 'right',
    getValue: (r) => r.top1_tracks, format: (r) => formatNumber(r.top1_tracks), sortable: true,
  },
  {
    key: 'top5_tracks', label: 'Top5曲数', align: 'right',
    getValue: (r) => r.top5_tracks, format: (r) => formatNumber(r.top5_tracks), sortable: true,
  },
  {
    key: 'top10_tracks', label: 'Top10曲数', align: 'right',
    getValue: (r) => r.top10_tracks, format: (r) => formatNumber(r.top10_tracks), sortable: true,
  },
  {
    key: 'power_score', label: '走势评分', align: 'right',
    getValue: (r) => r.power_score, format: (r) => formatNumber(r.power_score), sortable: true,
  },
  {
    key: 'power_rank', label: '走势排名', align: 'right',
    getValue: (r) => r.power_rank, format: (r) => String(r.power_rank), sortable: true,
    rankStyle: true,
  },
  {
    key: 'total_plays', label: '总播放次数', align: 'right',
    getValue: (r) => r.total_plays, format: (r) => formatNumber(r.total_plays), sortable: true,
  },
]

const ARTIST_COLUMNS: ColumnDef<MergedArtistRow>[] = [
  {
    key: 'peak_position', label: '排名峰值', align: 'right',
    getValue: (r) => r.peak_position, format: (r) => String(r.peak_position), sortable: true,
    rankStyle: true,
  },
  {
    key: 'weeks_at_peak', label: '峰值周数', align: 'right',
    getValue: (r) => r.weeks_at_peak, format: (r) => formatNumber(r.weeks_at_peak), sortable: true,
  },
  {
    key: 'weeks_on_chart', label: '在榜周数', align: 'right',
    getValue: (r) => r.weeks_on_chart, format: (r) => formatNumber(r.weeks_on_chart), sortable: true,
  },
  {
    key: 'weeks_top5', label: 'Top5周数', align: 'right',
    getValue: (r) => r.weeks_top5, format: (r) => formatNumber(r.weeks_top5), sortable: true,
  },
  {
    key: 'weeks_top10', label: 'Top10周数', align: 'right',
    getValue: (r) => r.weeks_top10, format: (r) => formatNumber(r.weeks_top10), sortable: true,
  },
  {
    key: 'total_tracks', label: '入榜曲数', align: 'right',
    getValue: (r) => r.total_tracks, format: (r) => formatNumber(r.total_tracks), sortable: true,
  },
  {
    key: 'top1_tracks', label: '冠军歌曲数', align: 'right',
    getValue: (r) => r.top1_tracks, format: (r) => formatNumber(r.top1_tracks), sortable: true,
  },
  {
    key: 'top5_tracks', label: 'Top5曲数', align: 'right',
    getValue: (r) => r.top5_tracks, format: (r) => formatNumber(r.top5_tracks), sortable: true,
  },
  {
    key: 'top10_tracks', label: 'Top10曲数', align: 'right',
    getValue: (r) => r.top10_tracks, format: (r) => formatNumber(r.top10_tracks), sortable: true,
  },
  {
    key: 'num_no1_albums', label: '#1专辑数', align: 'right',
    getValue: (r) => r.num_no1_albums, format: (r) => formatNumber(r.num_no1_albums), sortable: true,
  },
  {
    key: 'top5_albums', label: 'Top5专辑数', align: 'right',
    getValue: (r) => r.top5_albums, format: (r) => formatNumber(r.top5_albums), sortable: true,
  },
  {
    key: 'top10_albums', label: 'Top10专辑数', align: 'right',
    getValue: (r) => r.top10_albums, format: (r) => formatNumber(r.top10_albums), sortable: true,
  },
  {
    key: 'power_score', label: '走势评分', align: 'right',
    getValue: (r) => r.power_score, format: (r) => formatNumber(r.power_score), sortable: true,
  },
  {
    key: 'power_rank', label: '走势排名', align: 'right',
    getValue: (r) => r.power_rank, format: (r) => String(r.power_rank), sortable: true,
    rankStyle: true,
  },
  {
    key: 'total_plays', label: '总播放次数', align: 'right',
    getValue: (r) => r.total_plays, format: (r) => formatNumber(r.total_plays), sortable: true,
  },
]

const PEAK_FILTER_OPTIONS: { value: PeakFilter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'no1', label: '#1 冠军' },
  { value: 'top5', label: 'Top 5' },
  { value: 'top10', label: 'Top 10' },
  { value: 'debut_no1', label: '空冠' },
]

const TABS: { key: EntityTab; label: string }[] = [
  { key: 'tracks', label: '歌曲' },
  { key: 'albums', label: '专辑' },
  { key: 'artists', label: '艺人' },
]

// ── sub-components ───────────────────────────────────────────

function CoverImg({ url }: { url?: string | null }) {
  const [imgError, setImgError] = useState(false)
  useEffect(() => { setImgError(false) }, [url])

  if (url && !imgError) {
    return (
      <img
        src={url}
        alt=""
        className="h-10 w-10 shrink-0 rounded-[8px] object-cover"
        onError={() => setImgError(true)}
        loading="lazy"
      />
    )
  }
  return (
    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[8px] bg-muted text-base">
      🎵
    </div>
  )
}

function SortIcon({ active, dir }: { active: boolean; dir: 'asc' | 'desc' }) {
  if (!active) return <ArrowUpDown className="ml-1 inline h-3 w-3 text-muted-foreground/40" />
  return dir === 'asc'
    ? <ArrowUp className="ml-1 inline h-3 w-3 text-accent-foreground" />
    : <ArrowDown className="ml-1 inline h-3 w-3 text-accent-foreground" />
}

// ── main component ───────────────────────────────────────────

export function AllTimeChartsPage() {
  const { data, loading, error, refetch } = useBillboard()

  const PAGE_SIZE = 50
  const [activeTab, setActiveTab] = useState<EntityTab>(cachedEntityTab)
  const [peakFilter, setPeakFilter] = useState<PeakFilter>(cachedPeakFilter)
  const [page, setPage] = useState(cachedPage)
  const [sortKeyTrack, setSortKeyTrack] = useState(cachedSortKeyTrack)
  const [sortDirTrack, setSortDirTrack] = useState<'asc' | 'desc'>(cachedSortDirTrack)
  const [sortKeyAlbum, setSortKeyAlbum] = useState(cachedSortKeyAlbum)
  const [sortDirAlbum, setSortDirAlbum] = useState<'asc' | 'desc'>(cachedSortDirAlbum)
  const [sortKeyArtist, setSortKeyArtist] = useState(cachedSortKeyArtist)
  const [sortDirArtist, setSortDirArtist] = useState<'asc' | 'desc'>(cachedSortDirArtist)

  const sortKey = activeTab === 'tracks' ? sortKeyTrack : activeTab === 'albums' ? sortKeyAlbum : sortKeyArtist
  const sortDir = activeTab === 'tracks' ? sortDirTrack : activeTab === 'albums' ? sortDirAlbum : sortDirArtist
  const setSortKey = activeTab === 'tracks' ? setSortKeyTrack : activeTab === 'albums' ? setSortKeyAlbum : setSortKeyArtist
  const setSortDir = activeTab === 'tracks' ? setSortDirTrack : activeTab === 'albums' ? setSortDirAlbum : setSortDirArtist

  // Reset page when tab, filter, or sort changes
  useEffect(() => { setPage(1) }, [activeTab, peakFilter, sortKey, sortDir])

  // Sync state to module-level cache for persistence across navigations
  useEffect(() => { cachedEntityTab = activeTab }, [activeTab])
  useEffect(() => { cachedPeakFilter = peakFilter }, [peakFilter])
  useEffect(() => { cachedPage = page }, [page])
  useEffect(() => { cachedSortKeyTrack = sortKeyTrack }, [sortKeyTrack])
  useEffect(() => { cachedSortDirTrack = sortDirTrack }, [sortDirTrack])
  useEffect(() => { cachedSortKeyAlbum = sortKeyAlbum }, [sortKeyAlbum])
  useEffect(() => { cachedSortDirAlbum = sortDirAlbum }, [sortDirAlbum])
  useEffect(() => { cachedSortKeyArtist = sortKeyArtist }, [sortKeyArtist])
  useEffect(() => { cachedSortDirArtist = sortDirArtist }, [sortDirArtist])

  // ── weekly-based stats for albums (missing from backend) ──

  const albumWeeklyStats = useMemo(() => {
    if (!data) return new Map<string, { weeksAtPeak: number; weeksTop5: number; weeksTop10: number; totalPlays: number; firstWeek: string }>()
    const map = new Map<string, { minRank: number; weeksAtPeak: number; weeksTop5: number; weeksTop10: number; totalPlays: number; firstWeek: string }>()
    for (const e of data.weekly_album) {
      const key = `${e.album_name}||${e.artist_name}`
      const cur = map.get(key)
      if (cur) {
        if (e.rank < cur.minRank) {
          cur.minRank = e.rank
          cur.weeksAtPeak = 1
        } else if (e.rank === cur.minRank) {
          cur.weeksAtPeak++
        }
        if (e.rank <= 5) cur.weeksTop5++
        if (e.rank <= 10) cur.weeksTop10++
        cur.totalPlays += e.play_count
        if (e.billboard_week < cur.firstWeek) cur.firstWeek = e.billboard_week
      } else {
        map.set(key, {
          minRank: e.rank,
          weeksAtPeak: 1,
          weeksTop5: e.rank <= 5 ? 1 : 0,
          weeksTop10: e.rank <= 10 ? 1 : 0,
          totalPlays: e.play_count,
          firstWeek: e.billboard_week,
        })
      }
    }
    const result = new Map<string, { weeksAtPeak: number; weeksTop5: number; weeksTop10: number; totalPlays: number; firstWeek: string }>()
    for (const [k, v] of map) {
      result.set(k, { weeksAtPeak: v.weeksAtPeak, weeksTop5: v.weeksTop5, weeksTop10: v.weeksTop10, totalPlays: v.totalPlays, firstWeek: v.firstWeek })
    }
    return result
  }, [data])

  const albumCoverMap = useMemo(() => {
    const map = new Map<string, string | null>()
    if (!data) return map
    for (const e of data.weekly_album) {
      const key = `${e.album_name}||${e.artist_name}`
      if (!map.has(key) && e.cover_url) map.set(key, e.cover_url)
    }
    return map
  }, [data])

  // ── weekly-based stats for artists (missing from backend) ──

  const artistWeeklyStats = useMemo(() => {
    if (!data) return new Map<string, { weeksAtPeak: number; weeksTop5: number; weeksTop10: number; totalPlays: number; firstWeek: string }>()
    const map = new Map<string, { minRank: number; weeksAtPeak: number; weeksTop5: number; weeksTop10: number; totalPlays: number; firstWeek: string }>()
    for (const e of data.weekly_artist) {
      const key = e.artist_name
      const cur = map.get(key)
      if (cur) {
        if (e.rank < cur.minRank) {
          cur.minRank = e.rank
          cur.weeksAtPeak = 1
        } else if (e.rank === cur.minRank) {
          cur.weeksAtPeak++
        }
        if (e.rank <= 5) cur.weeksTop5++
        if (e.rank <= 10) cur.weeksTop10++
        cur.totalPlays += e.play_count
        if (e.billboard_week < cur.firstWeek) cur.firstWeek = e.billboard_week
      } else {
        map.set(key, {
          minRank: e.rank,
          weeksAtPeak: 1,
          weeksTop5: e.rank <= 5 ? 1 : 0,
          weeksTop10: e.rank <= 10 ? 1 : 0,
          totalPlays: e.play_count,
          firstWeek: e.billboard_week,
        })
      }
    }
    const result = new Map<string, { weeksAtPeak: number; weeksTop5: number; weeksTop10: number; totalPlays: number; firstWeek: string }>()
    for (const [k, v] of map) {
      result.set(k, { weeksAtPeak: v.weeksAtPeak, weeksTop5: v.weeksTop5, weeksTop10: v.weeksTop10, totalPlays: v.totalPlays, firstWeek: v.firstWeek })
    }
    return result
  }, [data])

  const artistCoverMap = useMemo(() => {
    const map = new Map<string, string | null>()
    if (!data) return map
    for (const e of data.weekly_artist) {
      if (!map.has(e.artist_name) && e.cover_url) map.set(e.artist_name, e.cover_url)
    }
    return map
  }, [data])

  // ── artist album stats (top5_albums, top10_albums from weekly_album) ──

  const artistAlbumStats = useMemo(() => {
    if (!data) return new Map<string, { top5Albums: number; top10Albums: number }>()
    // For each (artist, album), get min rank, then count per artist
    const albumPeaks = new Map<string, { artist: string; peak: number }>()
    for (const e of data.weekly_album) {
      const key = `${e.artist_name}||${e.album_name}`
      const cur = albumPeaks.get(key)
      if (!cur || e.rank < cur.peak) {
        albumPeaks.set(key, { artist: e.artist_name, peak: e.rank })
      }
    }
    const artistMap = new Map<string, { top5Albums: number; top10Albums: number }>()
    for (const [, v] of albumPeaks) {
      const cur = artistMap.get(v.artist) ?? { top5Albums: 0, top10Albums: 0 }
      if (v.peak <= 5) cur.top5Albums++
      if (v.peak <= 10) cur.top10Albums++
      artistMap.set(v.artist, cur)
    }
    return artistMap
  }, [data])

  // ── merged rows ────────────────────────────────────────────

  const mergedTracks = useMemo<MergedTrackRow[]>(() => {
    if (!data) return []
    const psMap = new Map<number, PowerScoreEntry>()
    for (const ps of data.power_scores) psMap.set(ps.track_id, ps)

    const tsMap = new Map<number, TrackSummary>()
    for (const ts of data.track_summary) tsMap.set(ts.track_id, ts)

    // Build cover lookup
    const coverMap = new Map<number, string | null>()
    for (const w of data.weekly) {
      if (!coverMap.has(w.track_id) && w.cover_url) coverMap.set(w.track_id, w.cover_url)
    }

    const rows: MergedTrackRow[] = []
    for (const ps of data.power_scores) {
      const ts = tsMap.get(ps.track_id)
      const isDebutNo1 = ts ? (ts.peak_position === 1 && ts.first_week === (ts.first_peak_week ?? '')) : false
      rows.push({
        track_id: ps.track_id,
        track_name: ps.track_name,
        artist_name: ps.artist_name,
        cover_url: coverMap.get(ps.track_id) ?? null,
        weeks_on_chart: ps.weeks_on_chart,
        peak_position: ps.peak_position,
        weeks_at_peak: ts?.weeks_at_peak ?? 0,
        weeks_top5: ps.weeks_top5,
        weeks_top10: ps.weeks_top10,
        power_score: ps.power_score,
        power_rank: 0, // filled below
        total_chart_plays: ts?.total_chart_plays ?? 0,
        is_debut_no1: isDebutNo1,
      })
    }
    // Sort by power_score desc to assign power_rank
    rows.sort((a, b) => b.power_score - a.power_score)
    rows.forEach((r, i) => { r.power_rank = i + 1 })
    return rows
  }, [data])

  const mergedAlbums = useMemo<MergedAlbumRow[]>(() => {
    if (!data) return []
    const atcMap = new Map<string, AlbumTrackCounts>()
    for (const atc of data.album_track_counts) {
      atcMap.set(`${atc.album_name}||${atc.artist_name}`, atc)
    }

    const rows: MergedAlbumRow[] = []
    for (const aps of data.album_power_scores) {
      const key = `${aps.album_name}||${aps.artist_name}`
      const atc = atcMap.get(key)
      const ws = albumWeeklyStats.get(key)
      const firstWeek = ws?.firstWeek ?? ''
      const isDebutNo1 = firstWeek !== '' && aps.peak_position === 1 &&
        data.weekly_album.some(e => e.album_name === aps.album_name && e.artist_name === aps.artist_name && e.billboard_week === firstWeek && e.rank === 1)

      rows.push({
        album_name: aps.album_name,
        artist_name: aps.artist_name,
        cover_url: albumCoverMap.get(key) ?? null,
        weeks_on_chart: aps.weeks_on_chart,
        peak_position: aps.peak_position,
        weeks_at_peak: ws?.weeksAtPeak ?? 0,
        weeks_top5: ws?.weeksTop5 ?? 0,
        weeks_top10: ws?.weeksTop10 ?? 0,
        total_tracks: atc?.total_tracks ?? 0,
        top1_tracks: atc?.top1 ?? 0,
        top5_tracks: atc?.top5 ?? 0,
        top10_tracks: atc?.top10 ?? 0,
        power_score: aps.power_score,
        power_rank: 0, // filled below
        total_plays: ws?.totalPlays ?? 0,
        is_debut_no1: isDebutNo1,
      })
    }
    // Sort by power_score desc to assign power_rank
    rows.sort((a, b) => b.power_score - a.power_score)
    rows.forEach((r, i) => { r.power_rank = i + 1 })
    return rows
  }, [data, albumWeeklyStats, albumCoverMap])

  const mergedArtists = useMemo<MergedArtistRow[]>(() => {
    if (!data) return []
    const atcMap = new Map<string, ArtistTrackCounts>()
    for (const atc of data.artist_track_counts) {
      atcMap.set(atc.artist_name, atc)
    }

    const rows: MergedArtistRow[] = []
    for (const aps of data.artist_power_scores) {
      const atc = atcMap.get(aps.artist_name)
      const ws = artistWeeklyStats.get(aps.artist_name)
      const aaStats = artistAlbumStats.get(aps.artist_name)
      const firstWeek = ws?.firstWeek ?? ''
      const isDebutNo1 = firstWeek !== '' && aps.peak_position === 1 &&
        data.weekly_artist.some(e => e.artist_name === aps.artist_name && e.billboard_week === firstWeek && e.rank === 1)

      rows.push({
        artist_name: aps.artist_name,
        cover_url: artistCoverMap.get(aps.artist_name) ?? null,
        weeks_on_chart: atc?.total_weeks ?? aps.weeks_on_chart,
        peak_position: atc?.best_peak ?? aps.peak_position,
        weeks_at_peak: ws?.weeksAtPeak ?? 0,
        weeks_top5: ws?.weeksTop5 ?? 0,
        weeks_top10: ws?.weeksTop10 ?? 0,
        total_tracks: atc?.total_tracks ?? 0,
        top1_tracks: atc?.top1 ?? 0,
        top5_tracks: atc?.top5 ?? 0,
        top10_tracks: atc?.top10 ?? 0,
        num_no1_albums: atc?.num_no1_albums ?? 0,
        top5_albums: aaStats?.top5Albums ?? 0,
        top10_albums: aaStats?.top10Albums ?? 0,
        power_score: aps.power_score,
        power_rank: 0, // filled below
        total_plays: ws?.totalPlays ?? 0,
        is_debut_no1: isDebutNo1,
      })
    }
    // Sort by power_score desc to assign power_rank
    rows.sort((a, b) => b.power_score - a.power_score)
    rows.forEach((r, i) => { r.power_rank = i + 1 })
    return rows
  }, [data, artistWeeklyStats, artistCoverMap, artistAlbumStats])

  // ── filter + sort ──────────────────────────────────────────

  function applyPeakFilter<T extends { peak_position: number; is_debut_no1: boolean }>(rows: T[], filter: PeakFilter): T[] {
    switch (filter) {
      case 'no1': return rows.filter(r => r.peak_position === 1)
      case 'top5': return rows.filter(r => r.peak_position <= 5)
      case 'top10': return rows.filter(r => r.peak_position <= 10)
      case 'debut_no1': return rows.filter(r => r.is_debut_no1)
      default: return rows
    }
  }

  const displayRows = useMemo(() => {
    let rows: MergedTrackRow[] | MergedAlbumRow[] | MergedArtistRow[]
    let columns: ColumnDef<any>[]

    if (activeTab === 'tracks') {
      rows = mergedTracks
      columns = TRACK_COLUMNS
    } else if (activeTab === 'albums') {
      rows = mergedAlbums
      columns = ALBUM_COLUMNS
    } else {
      rows = mergedArtists
      columns = ARTIST_COLUMNS
    }

    // Filter
    const filtered = applyPeakFilter(rows as any, peakFilter)

    // Sort
    const col = columns.find(c => c.key === sortKey)
    if (col) {
      filtered.sort((a, b) => {
        const va = col.getValue(a)
        const vb = col.getValue(b)
        const na = typeof va === 'number' ? va : String(va)
        const nb = typeof vb === 'number' ? vb : String(vb)
        if (na < nb) return sortDir === 'asc' ? -1 : 1
        if (na > nb) return sortDir === 'asc' ? 1 : -1
        return 0
      })
    }

    return { rows: filtered, columns, total: rows.length }
  }, [activeTab, mergedTracks, mergedAlbums, mergedArtists, peakFilter, sortKey, sortDir])

  function handleColumnClick(col: ColumnDef<any>) {
    if (didResizeRef.current) {
      didResizeRef.current = false
      return
    }
    if (!col.sortable) return
    if (sortKey === col.key) {
      setSortDir(sortDir === 'desc' ? 'asc' : 'desc')
    } else {
      setSortKey(col.key)
      setSortDir('desc')
    }
  }

  // ── loading ─────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-9 w-48" />
        <div className="flex gap-4">
          <Skeleton className="h-8 w-16" />
          <Skeleton className="h-8 w-16" />
          <Skeleton className="h-8 w-16" />
        </div>
        <Skeleton className="h-10 w-40" />
        <Skeleton className="h-[400px] w-full rounded-2xl" />
      </div>
    )
  }

  // ── error ───────────────────────────────────────────────────

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24">
        <AlertCircle className="h-10 w-10 text-muted-foreground" />
        <p className="text-base text-muted-foreground">{error}</p>
        <button
          onClick={refetch}
          className="rounded-lg bg-accent-foreground px-5 py-2 text-sm font-medium text-primary-foreground hover:opacity-80"
        >
          重新加载
        </button>
      </div>
    )
  }

  if (!data) return null

  // ── render helpers ──────────────────────────────────────────

  function renderTrackName(row: MergedTrackRow) {
    return (
      <div className="flex items-center gap-3">
        <CoverImg url={row.cover_url} />
        <div className="min-w-0">
          <Link
            to={`/billboard/track/${row.track_id}`}
            className="block truncate font-sans text-[14px] font-semibold text-foreground hover:text-accent-foreground transition-colors"
          >
            {displayName(row.track_name)}
          </Link>
          <Link
            to={`/billboard/artist/${encodeURIComponent(row.artist_name)}`}
            className="block truncate font-sans text-[12px] text-muted-foreground hover:text-accent-foreground transition-colors"
          >
            {displayName(row.artist_name)}
          </Link>
        </div>
      </div>
    )
  }

  function renderAlbumName(row: MergedAlbumRow) {
    return (
      <div className="flex items-center gap-3">
        <CoverImg url={row.cover_url} />
        <div className="min-w-0">
          <Link
            to={`/billboard/album/${encodeURIComponent(row.album_name)}?artist=${encodeURIComponent(row.artist_name)}`}
            className="block truncate font-sans text-[14px] font-semibold text-foreground hover:text-accent-foreground transition-colors"
          >
            {displayName(row.album_name)}
          </Link>
          <Link
            to={`/billboard/artist/${encodeURIComponent(row.artist_name)}`}
            className="block truncate font-sans text-[12px] text-muted-foreground hover:text-accent-foreground transition-colors"
          >
            {displayName(row.artist_name)}
          </Link>
        </div>
      </div>
    )
  }

  function renderArtistName(row: MergedArtistRow) {
    return (
      <div className="flex items-center gap-3">
        <CoverImg url={row.cover_url} />
        <Link
          to={`/billboard/artist/${encodeURIComponent(row.artist_name)}`}
          className="font-sans text-[14px] font-semibold text-foreground hover:text-accent-foreground transition-colors"
        >
          {displayName(row.artist_name)}
        </Link>
      </div>
    )
  }

  // ── column widths (localStorage persisted) ──────────────────

  const [columnWidths, setColumnWidths] = useState<Record<string, number>>(loadColumnWidths)
  const columnWidthsRef = useRef(columnWidths)
  columnWidthsRef.current = columnWidths
  const didResizeRef = useRef(false)
  const [resizing, setResizing] = useState<{ key: string; startX: number; startWidth: number } | null>(null)

  const getColWidth = (key: string) => columnWidths[key] ?? COLUMN_WIDTH_DEFAULTS[key] ?? 80

  useEffect(() => {
    if (!resizing) return
    const handleMouseMove = (e: MouseEvent) => {
      const diff = e.clientX - resizing.startX
      const newWidth = Math.max(48, resizing.startWidth + diff)
      setColumnWidths(prev => ({ ...prev, [resizing.key]: newWidth }))
    }
    const handleMouseUp = () => {
      saveColumnWidths(columnWidthsRef.current)
      didResizeRef.current = true
      setResizing(null)
    }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    return () => {
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [resizing])

  // Max plays for visual bar (inline bar style, matching weekly chart)
  const maxBarValue = useMemo(() => {
    if (activeTab === 'tracks') {
      if (mergedTracks.length === 0) return 1
      return Math.max(...mergedTracks.map(r => r.total_chart_plays))
    }
    if (activeTab === 'albums') {
      if (mergedAlbums.length === 0) return 1
      return Math.max(...mergedAlbums.map(r => r.total_plays))
    }
    if (mergedArtists.length === 0) return 1
    return Math.max(...mergedArtists.map(r => r.total_plays))
  }, [activeTab, mergedTracks, mergedAlbums, mergedArtists])

  const isTotalPlaysCol = (key: string) => key === 'total_chart_plays' || key === 'total_plays'

  function renderTableCell(row: any, col: ColumnDef<any>) {
    const val = col.format(row)
    const rawVal = col.getValue(row)
    const isSortCol = col.key === sortKey
    const isRankCol = col.rankStyle && typeof rawVal === 'number'
    const showBar = isTotalPlaysCol(col.key) && typeof rawVal === 'number'
    return (
      <td
        key={col.key}
        className={cn(
          'px-3 py-2.5 whitespace-nowrap tabular-nums',
          isRankCol ? 'font-serif text-[17px] font-semibold' : 'font-sans text-[13px]',
          col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left',
          isRankCol ? rankColorClass(rawVal as number) : isSortCol ? 'text-accent-foreground font-semibold' : 'text-foreground/80',
        )}
      >
        {isRankCol ? String(rawVal).padStart(2, '0') : val}
        {showBar && (
          <span className="ml-2 inline-block h-[3px] w-[70px] rounded-[2px] bg-muted align-middle">
            <span
              className="block h-full rounded-[2px] bg-accent-foreground transition-[width] duration-300"
              style={{ width: `${Math.round(((rawVal as number) / maxBarValue) * 100)}%` }}
            />
          </span>
        )}
      </td>
    )
  }

  const { rows: allFilteredRows, columns: activeColumns, total } = displayRows
  const totalPages = Math.max(1, Math.ceil(allFilteredRows.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages)
  const paginatedRows = allFilteredRows.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)
  const filteredCount = allFilteredRows.length

  return (
    <>
      <BillboardSubNav active="all-time" />

      {/* Header */}
      <section className="mt-6 mb-6">
        <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          Chart / All-Time
        </p>
        <h1 className="font-serif text-[44px] font-bold leading-[1.06] tracking-[-1.2px]">
          Billboard 总榜
        </h1>
      </section>

      {/* Entity Tabs */}
      <div className="mb-5 flex gap-7 border-b border-border" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={activeTab === tab.key}
            onClick={() => { cachedEntityTab = tab.key; setActiveTab(tab.key) }}
            className={cn(
              '-mb-px border-none bg-transparent px-0 pb-2.5 font-sans text-[13px] font-medium transition-[color,border] duration-200',
              'border-b-2',
              activeTab === tab.key
                ? 'border-accent-foreground font-semibold text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Peak Filter + Top Pagination */}
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-sans text-[12px] font-medium text-muted-foreground uppercase tracking-[1px]">筛选</span>
          <div className="flex gap-1.5">
            {PEAK_FILTER_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => { setPeakFilter(opt.value); setPage(1) }}
                className={cn(
                  'rounded-full px-3.5 py-1.5 font-sans text-[12px] font-medium transition-colors',
                  peakFilter === opt.value
                    ? 'bg-accent-foreground text-primary-foreground'
                    : 'bg-muted/60 text-muted-foreground hover:text-foreground hover:bg-muted',
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <span className="mr-2 font-sans text-[12px] text-muted-foreground tabular-nums">
            {safePage} / {totalPages}
          </span>
          <button
            onClick={() => setPage(1)}
            disabled={safePage <= 1}
            className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
          >
            <ChevronsLeft className="h-4 w-4" />
          </button>
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={safePage <= 1}
            className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={safePage >= totalPages}
            className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <button
            onClick={() => setPage(totalPages)}
            disabled={safePage >= totalPages}
            className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground disabled:opacity-30 transition-colors"
          >
            <ChevronsRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Table */}
      <GlassCard className="overflow-x-auto p-0">
        <table className="table-fixed border-collapse" style={{ width: 44 + getColWidth(`_name_${activeTab}`) + activeColumns.reduce((s, c) => s + getColWidth(c.key), 0) }}>
          <thead>
            <tr className="border-b border-border">
              <th style={{ width: 44 }} className="sticky top-0 z-10 bg-card px-2 py-3 text-center font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                #
              </th>
              <th
                style={{ width: getColWidth(`_name_${activeTab}`) }}
                className="sticky top-0 z-10 bg-card px-3 py-3 text-left font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground relative"
              >
                名称
                <div
                  className="absolute right-0 top-0 bottom-0 w-[6px] cursor-col-resize hover:bg-accent-foreground/25 transition-colors"
                  onMouseDown={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    const key = `_name_${activeTab}`
                    setResizing({ key, startX: e.clientX, startWidth: getColWidth(key) })
                  }}
                />
              </th>
              {activeColumns.map((col) => (
                <th
                  key={col.key}
                  onClick={() => handleColumnClick(col)}
                  style={{ width: getColWidth(col.key) }}
                  className={cn(
                    'sticky top-0 z-10 bg-card px-2 py-3 font-sans text-[10px] font-bold uppercase tracking-[1.2px] cursor-pointer select-none hover:text-foreground transition-colors whitespace-nowrap relative',
                    col.align === 'right' ? 'text-right' : 'text-left',
                    col.key === sortKey ? 'text-accent-foreground' : 'text-muted-foreground',
                  )}
                >
                  {col.label}
                  <SortIcon active={col.key === sortKey} dir={col.key === sortKey ? sortDir : 'desc'} />
                  <div
                    className="absolute right-0 top-0 bottom-0 w-[6px] cursor-col-resize hover:bg-accent-foreground/25 transition-colors"
                    onMouseDown={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      setResizing({ key: col.key, startX: e.clientX, startWidth: getColWidth(col.key) })
                    }}
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginatedRows.map((row: any, i: number) => {
              const globalIndex = (safePage - 1) * PAGE_SIZE + i
              return (
              <tr
                key={activeTab === 'tracks' ? row.track_id : activeTab === 'albums' ? `${row.album_name}||${row.artist_name}` : row.artist_name}
                className="border-b border-border/50 hover:bg-muted/50 transition-colors"
              >
                {/* Rank */}
                <td className={cn(
                  'px-2 py-2.5 text-center font-serif text-[17px] font-semibold tabular-nums',
                  rankColorClass(globalIndex + 1),
                )}>
                  {String(globalIndex + 1).padStart(2, '0')}
                </td>
                {/* Name */}
                <td className="px-3 py-2.5" style={{ maxWidth: getColWidth(`_name_${activeTab}`) }}>
                  {activeTab === 'tracks'
                    ? renderTrackName(row as MergedTrackRow)
                    : activeTab === 'albums'
                      ? renderAlbumName(row as MergedAlbumRow)
                      : renderArtistName(row as MergedArtistRow)
                  }
                </td>
                {/* Metric columns */}
                {activeColumns.map((col) => renderTableCell(row, col))}
              </tr>
            )})}
            {paginatedRows.length === 0 && (
              <tr>
                <td colSpan={2 + activeColumns.length} className="px-3 py-16 text-center font-sans text-[14px] text-muted-foreground">
                  暂无数据
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </GlassCard>

      {/* Count */}
      <p className="mb-5 font-sans text-[12px] text-muted-foreground">
        显示 {(safePage - 1) * PAGE_SIZE + 1}-{Math.min(safePage * PAGE_SIZE, filteredCount)} / 总数 {formatNumber(filteredCount)} 条
        {filteredCount !== total && <>（共 {formatNumber(total)} 条）</>}
      </p>
    </>
  )
}
