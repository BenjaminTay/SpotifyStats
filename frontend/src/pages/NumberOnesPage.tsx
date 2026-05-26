import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useBillboard } from '@/hooks/useBillboard'
import { GlassCard } from '@/components/shared/GlassCard'
import ReactECharts from 'echarts-for-react'
import { useTheme } from '@/hooks/useTheme'
import { buildChartBase } from '@/components/charts/EChartsTheme'
import { getChartColors } from '@/lib/theme'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle, ArrowLeft } from 'lucide-react'
import { cn } from '@/lib/utils'
import { displayName } from '@/lib/chinese'
import type {
  WeeklyTrackEntry,
  WeeklyAlbumEntry,
  WeeklyArtistEntry,
  TrackSummary,
} from '@/types/billboard'

// ── helpers ──────────────────────────────────────────────

function formatNumber(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n)
}

function formatWeekStart(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso + 'T00:00:00')
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
}

function longestStreak(weeks: string[]): number {
  const sorted = [...new Set(weeks)].sort()
  if (sorted.length < 2) return sorted.length
  let max = 1
  let cur = 1
  for (let i = 1; i < sorted.length; i++) {
    const diff =
      (new Date(sorted[i]).getTime() - new Date(sorted[i - 1]).getTime()) /
      (1000 * 60 * 60 * 24)
    if (Math.abs(diff - 7) < 1) {
      cur++
      max = Math.max(max, cur)
    } else {
      cur = 1
    }
  }
  return max
}

// ── sub-components ────────────────────────────────────────

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

function PlayCountCell({ value, max }: { value: number; max: number }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="inline-block w-[52px] text-right font-sans text-[15px] font-semibold tabular-nums">
        {formatNumber(value)}
      </span>
      <span className="inline-block h-[3px] w-[56px] rounded-[2px] bg-muted">
        <span
          className="block h-full rounded-[2px] bg-accent-foreground transition-[width] duration-300"
          style={{ width: `${Math.round((value / (max || 1)) * 100)}%` }}
        />
      </span>
    </span>
  )
}

function No1BarChart({
  data,
  label,
}: {
  data: { name: string; value: number; subtitle?: string }[]
  label: string
}) {
  const { isDark } = useTheme()
  const base = buildChartBase(isDark)
  const colors = getChartColors(isDark)

  const chartData = [...data].reverse()
  const labels = chartData.map((d) => displayName(d.name))
  const values = chartData.map((d) => d.value)
  const subtitles = chartData.map((d) => (d.subtitle ? displayName(d.subtitle) : ''))

  const option = {
    ...base,
    tooltip: {
      ...base.tooltip,
      formatter: (params: { name: string; value: number; dataIndex: number }) =>
        `<b>${displayName(params.name)}</b><br/>${subtitles[params.dataIndex] ? subtitles[params.dataIndex] + '<br/>' : ''}${label}: ${params.value} 周`,
    },
    xAxis: { type: 'value' as const, ...base.xAxis, axisLabel: { ...base.xAxis.axisLabel } },
    yAxis: {
      type: 'category' as const,
      data: labels,
      ...base.yAxis,
      axisLabel: { ...base.yAxis.axisLabel, width: 160, overflow: 'truncate' },
      splitLine: { show: false },
    },
    series: [
      {
        type: 'bar',
        data: values.map((v) => ({
          value: v,
          itemStyle: { color: colors[0], borderRadius: [0, 4, 4, 0] },
        })),
        barMaxWidth: 24,
        label: {
          show: true,
          position: 'right',
          color: isDark ? '#A09888' : '#6B5E58',
          fontSize: 11,
          formatter: (p: { value: number }) => `${p.value} 周`,
        },
      },
    ],
    grid: { left: 8, right: 56, top: 8, bottom: 8, containLabel: true },
  }

  return <ReactECharts option={option} style={{ height: 460 }} notMerge />
}

function SkeletonBlock() {
  return (
    <>
      <Skeleton className="mb-3 h-3 w-32" />
      <Skeleton className="mb-2 h-[44px] w-72" />
      <Skeleton className="mb-8 h-5 w-48" />
      <div className="mb-8 grid grid-cols-3 gap-6">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i}>
            <Skeleton className="mb-2 h-10 w-20" />
            <Skeleton className="h-4 w-32" />
          </div>
        ))}
      </div>
      <Skeleton className="mb-6 h-[400px] w-full rounded-[16px]" />
      <Skeleton className="mb-6 h-[300px] w-full rounded-[16px]" />
    </>
  )
}

// ── shared table sub-components ───────────────────────────

function NameWithCover({
  coverUrl,
  name,
  artistName,
  nameLink,
  artistLink,
  badge,
}: {
  coverUrl?: string | null
  name: string
  artistName?: string
  nameLink: string
  artistLink?: string
  badge?: string
}) {
  return (
    <div className="flex items-center gap-3">
      <CoverImg url={coverUrl} />
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <Link
            to={nameLink}
            className="truncate font-sans text-sm font-semibold transition-colors hover:text-accent-foreground"
          >
            {displayName(name)}
          </Link>
          {badge && (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 font-sans text-[10px] font-semibold uppercase tracking-[0.6px] text-amber-600 dark:text-amber-400">
              {badge}
            </span>
          )}
        </div>
        {artistName &&
          (artistLink ? (
            <Link
              to={artistLink}
              className="mt-0.5 block font-sans text-[12px] italic text-muted-foreground transition-colors hover:text-accent-foreground"
            >
              {displayName(artistName)}
            </Link>
          ) : (
            <span className="mt-0.5 block font-sans text-[12px] italic text-muted-foreground">
              {displayName(artistName)}
            </span>
          ))}
      </div>
    </div>
  )
}

// ── types for computed data ───────────────────────────────

interface TrackNo1Info {
  track_id: number
  track_name: string
  artist_name: string
  cover_url?: string | null
  weeks_at_no1: number
  power_score: number
  total_no1_plays: number
  longest_streak: number
  no1_weeks: string[]
}

interface AlbumNo1Info {
  album_name: string
  artist_name: string
  cover_url?: string | null
  weeks_at_no1: number
  power_score: number
  longest_streak: number
  no1_weeks: string[]
}

interface ArtistNo1Info {
  artist_name: string
  cover_url?: string | null
  weeks_at_no1: number
  power_score: number
  longest_streak: number
  no1_weeks: string[]
}

interface DebutNo1 {
  track_id: number
  track_name: string
  artist_name: string
  cover_url?: string | null
  billboard_week: string
  weeks_on_chart: number
  weeks_at_no1: number
}

interface AlbumDebutNo1 {
  album_name: string
  artist_name: string
  cover_url?: string | null
  billboard_week: string
  weeks_on_chart: number
  weeks_at_no1: number
}

// ── main page ─────────────────────────────────────────────

type SubTabKey = 'tracks' | 'albums' | 'artists'

const SUB_TABS: { key: SubTabKey; label: string }[] = [
  { key: 'tracks', label: '单曲榜' },
  { key: 'albums', label: '专辑榜' },
  { key: 'artists', label: '艺人榜' },
]

export function NumberOnesPage() {
  const { data, loading, error } = useBillboard()

  // ── compute all #1 data ─────────────────────────────────

  const computed = useMemo(() => {
    const empty = {
      trackNo1List: [] as WeeklyTrackEntry[],
      albumNo1List: [] as WeeklyAlbumEntry[],
      artistNo1List: [] as WeeklyArtistEntry[],
      trackLongest: { name: '', artist: '', streak: 0 },
      albumLongest: { name: '', artist: '', streak: 0 },
      artistLongest: { name: '', streak: 0 },
      trackNo1WeeksSorted: [] as TrackNo1Info[],
      albumNo1WeeksSorted: [] as AlbumNo1Info[],
      artistNo1WeeksSorted: [] as ArtistNo1Info[],
      debutNo1Tracks: [] as DebutNo1[],
      debutNo1Albums: [] as AlbumDebutNo1[],
      trackAnnualNo1: [] as { year: number; count: number; songs: string }[],
      albumAnnualNo1: [] as { year: number; count: number; albums: string }[],
      albumNo1WithPkWks: [] as (WeeklyAlbumEntry & { album_pk_wks: number })[],
      artistNo1WithPkWks: [] as (WeeklyArtistEntry & { artist_pk_wks: number })[],
      trackMaxPlays: 1,
      albumMaxPlays: 1,
      artistMaxPlays: 1,
    }
    if (!data) return empty

    const { weekly, weekly_album, weekly_artist, track_summary, power_scores, album_power_scores, artist_power_scores } = data

    // ── Power score lookup maps ────────────────────────────
    const psByTrack = new Map<number, number>()
    for (const p of power_scores) psByTrack.set(p.track_id, p.power_score)
    const psByAlbum = new Map<string, number>()
    for (const p of album_power_scores) psByAlbum.set(`${p.album_name}|||${p.artist_name}`, p.power_score)
    const psByArtist = new Map<string, number>()
    for (const p of artist_power_scores) psByArtist.set(p.artist_name, p.power_score)

    // ── Track #1s ─────────────────────────────────────────
    const trackNo1s = weekly
      .filter((e) => e.rank === 1)
      .sort((a, b) => b.billboard_week.localeCompare(a.billboard_week))

    const trackMaxPlays = trackNo1s.reduce((m, e) => Math.max(m, e.play_count), 0)

    const trackNo1Map = new Map<number, WeeklyTrackEntry[]>()
    for (const e of trackNo1s) {
      const arr = trackNo1Map.get(e.track_id) ?? []
      arr.push(e)
      trackNo1Map.set(e.track_id, arr)
    }

    const trackNo1Infos: TrackNo1Info[] = []
    let trackLongestStreak = 0
    let trackLongestName = ''
    let trackLongestArtist = ''

    for (const [tid, entries] of trackNo1Map) {
      const weeks = entries.map((e) => e.billboard_week)
      const streak = longestStreak(weeks)
      trackNo1Infos.push({
        track_id: tid,
        track_name: entries[0].track_name,
        artist_name: entries[0].artist_name,
        cover_url: entries[0].cover_url,
        weeks_at_no1: new Set(weeks).size,
        power_score: psByTrack.get(tid) ?? 0,
        total_no1_plays: entries.reduce((s, e) => s + e.play_count, 0),
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

    // ── Album #1s ─────────────────────────────────────────
    const albumNo1s = weekly_album
      .filter((e) => e.rank === 1)
      .sort((a, b) => b.billboard_week.localeCompare(a.billboard_week))

    const albumMaxPlays = albumNo1s.reduce((m, e) => Math.max(m, e.play_count), 0)

    const albumNo1Map = new Map<string, WeeklyAlbumEntry[]>()
    for (const e of albumNo1s) {
      const key = `${e.album_name}|||${e.artist_name}`
      const arr = albumNo1Map.get(key) ?? []
      arr.push(e)
      albumNo1Map.set(key, arr)
    }

    const albumNo1Infos: AlbumNo1Info[] = []
    let albumLongestStreak = 0
    let albumLongestName = ''
    let albumLongestArtist = ''

    for (const [key, entries] of albumNo1Map) {
      const weeks = entries.map((e) => e.billboard_week)
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

    // ── Artist #1s ────────────────────────────────────────
    const artistNo1s = weekly_artist
      .filter((e) => e.rank === 1)
      .sort((a, b) => b.billboard_week.localeCompare(a.billboard_week))

    const artistMaxPlays = artistNo1s.reduce((m, e) => Math.max(m, e.play_count), 0)

    const artistNo1Map = new Map<string, WeeklyArtistEntry[]>()
    for (const e of artistNo1s) {
      const arr = artistNo1Map.get(e.artist_name) ?? []
      arr.push(e)
      artistNo1Map.set(e.artist_name, arr)
    }

    const artistNo1Infos: ArtistNo1Info[] = []
    let artistLongestStreak = 0
    let artistLongestName = ''

    for (const [name, entries] of artistNo1Map) {
      const weeks = entries.map((e) => e.billboard_week)
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

    // ── Debut at #1 (tracks) ──────────────────────────────
    const summaryMap = new Map<number, TrackSummary>()
    for (const s of track_summary) summaryMap.set(s.track_id, s)

    const firstAppearMap = new Map<number, WeeklyTrackEntry>()
    for (const e of weekly.sort((a, b) => a.billboard_week.localeCompare(b.billboard_week))) {
      if (!firstAppearMap.has(e.track_id)) firstAppearMap.set(e.track_id, e)
    }

    const debutNo1s: DebutNo1[] = []
    for (const [tid, entry] of firstAppearMap) {
      if (entry.rank === 1) {
        const s = summaryMap.get(tid)
        debutNo1s.push({
          track_id: tid,
          track_name: entry.track_name,
          artist_name: entry.artist_name,
          cover_url: entry.cover_url,
          billboard_week: entry.billboard_week,
          weeks_on_chart: s?.weeks_on_chart ?? 0,
          weeks_at_no1: s?.weeks_at_no1 ?? 0,
        })
      }
    }
    debutNo1s.sort((a, b) => b.billboard_week.localeCompare(a.billboard_week))

    // ── Debut at #1 (albums) ──────────────────────────────
    const albumSummaryMap = new Map<string, { weeks_on_chart: number; weeks_at_no1: number }>()
    for (const e of weekly_album) {
      const key = `${e.album_name}|||${e.artist_name}`
      const cur = albumSummaryMap.get(key)
      albumSummaryMap.set(key, {
        weeks_on_chart: (cur?.weeks_on_chart ?? 0) + 1,
        weeks_at_no1: (cur?.weeks_at_no1 ?? 0) + (e.rank === 1 ? 1 : 0),
      })
    }

    const albumFirstAppearMap = new Map<string, WeeklyAlbumEntry>()
    for (const e of weekly_album.sort((a, b) => a.billboard_week.localeCompare(b.billboard_week))) {
      const key = `${e.album_name}|||${e.artist_name}`
      if (!albumFirstAppearMap.has(key)) albumFirstAppearMap.set(key, e)
    }

    const albumDebutNo1s: AlbumDebutNo1[] = []
    for (const [key, entry] of albumFirstAppearMap) {
      if (entry.rank === 1) {
        const s = albumSummaryMap.get(key)
        albumDebutNo1s.push({
          album_name: entry.album_name,
          artist_name: entry.artist_name,
          cover_url: entry.cover_url,
          billboard_week: entry.billboard_week,
          weeks_on_chart: s?.weeks_on_chart ?? 0,
          weeks_at_no1: s?.weeks_at_no1 ?? 0,
        })
      }
    }
    albumDebutNo1s.sort((a, b) => b.billboard_week.localeCompare(a.billboard_week))

    // ── Annual unique #1s ─────────────────────────────────
    const annualTrackMap = new Map<number, Set<number>>()
    for (const e of trackNo1s) {
      const year = new Date(e.billboard_week + 'T00:00:00').getFullYear()
      const set = annualTrackMap.get(year) ?? new Set()
      set.add(e.track_id)
      annualTrackMap.set(year, set)
    }
    const trackAnnual: { year: number; count: number; songs: string }[] = []
    for (const [year, ids] of annualTrackMap) {
      const names = [...new Set(trackNo1s.filter((e) => {
        const y = new Date(e.billboard_week + 'T00:00:00').getFullYear()
        return y === year && ids.has(e.track_id)
      }).map((e) => e.track_name))]
      trackAnnual.push({ year, count: ids.size, songs: names.join('、') })
    }
    trackAnnual.sort((a, b) => b.year - a.year)

    const annualAlbumMap = new Map<number, Set<string>>()
    for (const e of albumNo1s) {
      const year = new Date(e.billboard_week + 'T00:00:00').getFullYear()
      const set = annualAlbumMap.get(year) ?? new Set()
      set.add(`${e.album_name}|||${e.artist_name}`)
      annualAlbumMap.set(year, set)
    }
    const albumAnnual: { year: number; count: number; albums: string }[] = []
    for (const [year, keys] of annualAlbumMap) {
      const names = [...new Set(albumNo1s.filter((e) => {
        const y = new Date(e.billboard_week + 'T00:00:00').getFullYear()
        return y === year && keys.has(`${e.album_name}|||${e.artist_name}`)
      }).map((e) => e.album_name))]
      albumAnnual.push({ year, count: keys.size, albums: names.join('、') })
    }
    albumAnnual.sort((a, b) => b.year - a.year)

    // ── Running peak wks ──────────────────────────────────
    const albumPkMap = new Map<string, number>()
    const albumNo1WithPkWks: (WeeklyAlbumEntry & { album_pk_wks: number })[] = []
    for (const e of [...albumNo1s].sort((a, b) => a.billboard_week.localeCompare(b.billboard_week))) {
      const key = `${e.album_name}|||${e.artist_name}`
      const cur = (albumPkMap.get(key) ?? 0) + 1
      albumPkMap.set(key, cur)
      albumNo1WithPkWks.push({ ...e, album_pk_wks: cur })
    }
    albumNo1WithPkWks.reverse()

    const artistPkMap = new Map<string, number>()
    const artistNo1WithPkWks: (WeeklyArtistEntry & { artist_pk_wks: number })[] = []
    for (const e of [...artistNo1s].sort((a, b) => a.billboard_week.localeCompare(b.billboard_week))) {
      const cur = (artistPkMap.get(e.artist_name) ?? 0) + 1
      artistPkMap.set(e.artist_name, cur)
      artistNo1WithPkWks.push({ ...e, artist_pk_wks: cur })
    }
    artistNo1WithPkWks.reverse()

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
      debutNo1Tracks: debutNo1s,
      debutNo1Albums: albumDebutNo1s,
      trackAnnualNo1: trackAnnual,
      albumAnnualNo1: albumAnnual,
      albumNo1WithPkWks,
      artistNo1WithPkWks,
      trackMaxPlays,
      albumMaxPlays,
      artistMaxPlays,
    }
  }, [data])

  const [activeTab, setActiveTab] = useState<SubTabKey>('tracks')

  // ── Year filter ───────────────────────────────────────

  const availableYears = useMemo(() => {
    const entries =
      activeTab === 'tracks' ? computed.trackNo1List
      : activeTab === 'albums' ? computed.albumNo1List
      : computed.artistNo1List
    const years = new Set<number>()
    for (const e of entries) {
      years.add(new Date(e.billboard_week + 'T00:00:00').getFullYear())
    }
    return [...years].sort((a, b) => b - a)
  }, [activeTab, computed.trackNo1List, computed.albumNo1List, computed.artistNo1List])

  const [selectedYear, setSelectedYear] = useState(0)

  useEffect(() => {
    if (availableYears.length === 0) return
    if (!availableYears.includes(selectedYear)) {
      setSelectedYear(availableYears[0])
    }
  }, [availableYears, selectedYear])

  const yearFiltered = useMemo(() => {
    const filterFn = (e: { billboard_week: string }) =>
      new Date(e.billboard_week + 'T00:00:00').getFullYear() === selectedYear

    const tracks = computed.trackNo1List.filter(filterFn)
    const albums = computed.albumNo1WithPkWks.filter(filterFn)
    const artists = computed.artistNo1WithPkWks.filter(filterFn)

    return {
      tracks,
      albums,
      artists,
      trackMaxPlays: Math.max(...tracks.map((e) => e.play_count), 1),
      albumMaxPlays: Math.max(...albums.map((e) => e.play_count), 1),
      artistMaxPlays: Math.max(...artists.map((e) => e.play_count), 1),
      uniqueTrackCount: new Set(tracks.map((e) => e.track_id)).size,
      uniqueAlbumCount: new Set(
        computed.albumNo1List.filter(filterFn).map((e) => `${e.album_name}|||${e.artist_name}`),
      ).size,
      uniqueArtistCount: new Set(
        computed.artistNo1List.filter(filterFn).map((e) => e.artist_name),
      ).size,
    }
  }, [selectedYear, computed])

  // ── Year switcher sub-component ───────────────────────

  function YearSwitcher({
    uniqueCount,
    unit,
  }: {
    uniqueCount: number
    unit: string
  }) {
    const idx = availableYears.indexOf(selectedYear)
    const prevYear = idx < availableYears.length - 1 ? availableYears[idx + 1] : null
    const nextYear = idx > 0 ? availableYears[idx - 1] : null

    return (
      <div className="flex items-center gap-2.5">
        <span className="font-sans text-[12px] text-muted-foreground">
          {uniqueCount} {unit}
        </span>
        <div className="flex items-center gap-0.5 rounded-[8px] border border-border bg-muted/30 p-0.5">
          <button
            onClick={() => prevYear != null && setSelectedYear(prevYear)}
            disabled={prevYear == null}
            className="inline-flex h-7 w-7 items-center justify-center rounded-[6px] text-[13px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-30"
          >
            ◀
          </button>
          <span className="inline-flex min-w-[48px] items-center justify-center font-serif text-[18px] font-bold tabular-nums">
            {selectedYear}
          </span>
          <button
            onClick={() => nextYear != null && setSelectedYear(nextYear)}
            disabled={nextYear == null}
            className="inline-flex h-7 w-7 items-center justify-center rounded-[6px] text-[13px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-30"
          >
            ▶
          </button>
        </div>
      </div>
    )
  }

  // ── Render ──────────────────────────────────────────────

  if (loading) return <SkeletonBlock />

  if (error) {
    return (
      <div className="flex flex-col items-center gap-4 py-20 text-center">
        <AlertCircle className="h-8 w-8 text-accent-foreground" />
        <p className="font-sans text-[13px] text-muted-foreground">{error}</p>
      </div>
    )
  }

  if (!data) return null

  // ── Annual #1 section component ─────────────────────────
  function AnnualSection({
    title,
    items,
  }: {
    title: string
    items: { year: number; count: number; songs: string }[]
  }) {
    if (items.length === 0) return null
    const maxCount = Math.max(...items.map((r) => r.count), 1)
    return (
      <GlassCard className="p-6">
        <h2 className="mb-6 font-serif text-[22px] font-bold tracking-[-0.3px]">{title}</h2>
        <div className="space-y-1">
          {items.map((row) => (
            <div
              key={row.year}
              className="group flex items-start gap-5 rounded-[10px] px-4 py-3.5 transition-colors hover:bg-muted/30"
            >
              <span className="w-[52px] shrink-0 pt-0.5 font-serif text-[28px] font-bold leading-none tracking-[-0.5px]">
                {row.year}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-3">
                  <span className="font-sans text-[18px] font-semibold tabular-nums">
                    {row.count} 首
                  </span>
                  <span className="h-[4px] flex-1 rounded-[2px] bg-muted">
                    <span
                      className="block h-full rounded-[2px] bg-accent-foreground/50 transition-[width] duration-500"
                      style={{ width: `${Math.round((row.count / maxCount) * 100)}%` }}
                    />
                  </span>
                </div>
                <p className="mt-1.5 font-sans text-[13px] leading-relaxed text-muted-foreground">
                  {displayName(row.songs)}
                </p>
              </div>
            </div>
          ))}
        </div>
      </GlassCard>
    )
  }

  return (
    <>
      {/* Header */}
      <section className="mb-6">
        <Link
          to="/billboard"
          className="mb-4 inline-flex items-center gap-1.5 font-sans text-[12px] font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          返回 Billboard
        </Link>
        <p className="mb-2 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          Chart / Number Ones
        </p>
        <h1 className="font-serif text-[44px] font-bold leading-[1.06] tracking-[-1.2px]">
          每周榜首
        </h1>
      </section>

      {/* Sub Tabs */}
      <div className="mb-8 flex gap-7 border-b border-border">
        {SUB_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              '-mb-px cursor-pointer border-none bg-transparent px-0 pb-2.5 font-sans text-[13px] font-medium transition-[color,border] duration-200',
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

      {/* ══════════════════════════════════════════════
          Tab: 单曲榜
          ══════════════════════════════════════════════ */}
      {activeTab === 'tracks' && (
        <>
          {/* KPI Cards */}
          <div className="mb-8 grid grid-cols-3 gap-6">
            <GlassCard className="p-6">
              <p className="mb-3 font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">
                总冠军歌曲数
              </p>
              <p className="mb-4 font-serif text-[44px] font-bold leading-none tracking-[-1px]">
                {computed.trackNo1WeeksSorted.length} <span className="text-[18px] font-normal">首</span>
              </p>
              {computed.trackNo1List[0] && (
                <NameWithCover
                  coverUrl={computed.trackNo1List[0].cover_url}
                  name={computed.trackNo1List[0].track_name}
                  artistName={computed.trackNo1List[0].artist_name}
                  nameLink={`/billboard/track/${computed.trackNo1List[0].track_id}`}
                  artistLink={`/billboard/artist/${encodeURIComponent(computed.trackNo1List[0].artist_name)}`}
                  badge="最新冠军"
                />
              )}
            </GlassCard>
            <GlassCard className="p-6">
              <p className="mb-3 font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">
                最多冠军周数
              </p>
              <p className="mb-4 font-serif text-[44px] font-bold leading-none tracking-[-1px]">
                {computed.trackNo1WeeksSorted[0]?.weeks_at_no1 ?? 0}{' '}
                <span className="text-[18px] font-normal">周</span>
              </p>
              {computed.trackNo1WeeksSorted[0] && (
                <NameWithCover
                  coverUrl={computed.trackNo1WeeksSorted[0].cover_url}
                  name={computed.trackNo1WeeksSorted[0].track_name}
                  artistName={computed.trackNo1WeeksSorted[0].artist_name}
                  nameLink={`/billboard/track/${computed.trackNo1WeeksSorted[0].track_id}`}
                  artistLink={`/billboard/artist/${encodeURIComponent(computed.trackNo1WeeksSorted[0].artist_name)}`}
                />
              )}
            </GlassCard>
            <GlassCard className="p-6">
              <p className="mb-3 font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">
                最长连冠纪录
              </p>
              <p className="mb-4 font-serif text-[44px] font-bold leading-none tracking-[-1px]">
                {computed.trackLongest.streak}{' '}
                <span className="text-[18px] font-normal">周</span>
              </p>
              {computed.trackLongest.streak > 0 && (() => {
                const e = computed.trackNo1WeeksSorted.find((t) => t.track_name === computed.trackLongest.name)
                if (!e) return null
                return (
                  <NameWithCover
                    coverUrl={e.cover_url}
                    name={e.track_name}
                    artistName={displayName(e.artist_name)}
                    nameLink={`/billboard/track/${e.track_id}`}
                    artistLink={`/billboard/artist/${encodeURIComponent(e.artist_name)}`}
                  />
                )
              })()}
            </GlassCard>
          </div>

          {/* Weekly #1 Table */}
          <GlassCard className="mb-8 overflow-hidden p-6">
            <div className="mb-5 flex items-center justify-between">
              <h2 className="font-serif text-[22px] font-bold tracking-[-0.3px]">每周冠军歌曲</h2>
              <YearSwitcher uniqueCount={yearFiltered.uniqueTrackCount} unit="首冠军歌曲" />
            </div>
            <div className="max-h-[600px] overflow-auto">
              <table className="w-full table-fixed border-collapse">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="sticky top-0 w-[96px] bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">周</th>
                    <th className="sticky top-0 bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">冠单曲目</th>
                    <th className="sticky top-0 w-[132px] bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">播放次数</th>
                    <th className="sticky top-0 w-[64px] bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">Pk Wks</th>
                  </tr>
                </thead>
                <tbody>
                  {yearFiltered.tracks.map((e) => (
                    <tr key={`${e.track_id}-${e.billboard_week}`} className="border-b border-border transition-colors hover:bg-muted/30">
                      <td className="w-[96px] py-3 font-sans text-[13px]">
                        <Link to={`/billboard?week=${e.billboard_week}`} className="text-foreground transition-colors hover:text-accent-foreground">
                          {formatWeekStart(e.billboard_week)}
                        </Link>
                      </td>
                      <td className="py-3">
                        <NameWithCover
                          coverUrl={e.cover_url}
                          name={e.track_name}
                          artistName={displayName(e.artist_name)}
                          nameLink={`/billboard/track/${e.track_id}`}
                          artistLink={`/billboard/artist/${encodeURIComponent(e.artist_name)}`}
                        />
                      </td>
                      <td className="py-3 text-right">
                        <PlayCountCell value={e.play_count} max={yearFiltered.trackMaxPlays} />
                      </td>
                      <td className="py-3 text-right font-sans text-[13px] tabular-nums">{e.running_peak_wks}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassCard>

          {/* #1 Weeks Ranking + Chart */}
          <div className="mb-8 grid grid-cols-2 gap-6">
            <GlassCard className="overflow-hidden p-6">
              <h2 className="mb-5 font-serif text-[22px] font-bold tracking-[-0.3px]">冠单周数排行</h2>
              <div className="max-h-[500px] overflow-auto">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="border-b border-border text-left">
                      <th className="sticky top-0 bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">#</th>
                      <th className="sticky top-0 bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">曲目</th>
                      <th className="sticky top-0 bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">冠单周数</th>
                    </tr>
                  </thead>
                  <tbody>
                    {computed.trackNo1WeeksSorted.slice(0, 20).map((e, i) => (
                      <tr key={e.track_id} className="border-b border-border transition-colors hover:bg-muted/30">
                        <td className="py-3 font-serif text-[15px] font-semibold tabular-nums text-muted-foreground">{i + 1}</td>
                        <td className="py-3">
                          <NameWithCover
                            coverUrl={e.cover_url}
                            name={e.track_name}
                            artistName={displayName(e.artist_name)}
                            nameLink={`/billboard/track/${e.track_id}`}
                            artistLink={`/billboard/artist/${encodeURIComponent(e.artist_name)}`}
                          />
                        </td>
                        <td className="py-3 text-right font-sans text-[13px] font-semibold tabular-nums">{e.weeks_at_no1}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </GlassCard>

            <GlassCard className="p-6">
              <h2 className="mb-5 font-serif text-[22px] font-bold tracking-[-0.3px]">单曲冠军周数 Top 15</h2>
              <No1BarChart
                label="冠单周数"
                data={computed.trackNo1WeeksSorted.slice(0, 15).map((e) => ({
                  name: e.track_name,
                  value: e.weeks_at_no1,
                  subtitle: e.artist_name,
                }))}
              />
            </GlassCard>
          </div>

          {/* Annual Unique #1 */}
          <div className="mb-8">
            <AnnualSection title="每年独特冠单统计" items={computed.trackAnnualNo1} />
          </div>

          {/* Debut at #1 */}
          <GlassCard className="overflow-hidden p-6">
            <h2 className="mb-1 font-serif text-[22px] font-bold tracking-[-0.3px]">空冠歌曲</h2>
            <p className="mb-5 font-sans text-[13px] text-muted-foreground">
              首次上榜即 #1 · 共 {computed.debutNo1Tracks.length} 首
            </p>
            {computed.debutNo1Tracks.length === 0 ? (
              <p className="py-8 text-center font-sans text-[13px] text-muted-foreground">暂无空冠歌曲</p>
            ) : (
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">曲目</th>
                    <th className="pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">首次上榜周</th>
                    <th className="pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">在榜周数</th>
                    <th className="pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">冠单周数</th>
                  </tr>
                </thead>
                <tbody>
                  {computed.debutNo1Tracks.map((e) => (
                    <tr key={e.track_id} className="border-b border-border transition-colors hover:bg-muted/30">
                      <td className="py-3">
                        <NameWithCover
                          coverUrl={e.cover_url}
                          name={e.track_name}
                          artistName={displayName(e.artist_name)}
                          nameLink={`/billboard/track/${e.track_id}`}
                          artistLink={`/billboard/artist/${encodeURIComponent(e.artist_name)}`}
                        />
                      </td>
                      <td className="py-3 font-sans text-[13px]">
                        <Link to={`/billboard?week=${e.billboard_week}`} className="text-foreground transition-colors hover:text-accent-foreground">
                          {formatWeekStart(e.billboard_week)}
                        </Link>
                      </td>
                      <td className="py-3 text-right font-sans text-[13px] tabular-nums">{e.weeks_on_chart}</td>
                      <td className="py-3 text-right font-sans text-[13px] tabular-nums">{e.weeks_at_no1}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </GlassCard>
        </>
      )}

      {/* ══════════════════════════════════════════════
          Tab: 专辑榜
          ══════════════════════════════════════════════ */}
      {activeTab === 'albums' && (
        <>
          <div className="mb-8 grid grid-cols-3 gap-6">
            <GlassCard className="p-6">
              <p className="mb-3 font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">总冠军专辑数</p>
              <p className="mb-4 font-serif text-[44px] font-bold leading-none tracking-[-1px]">
                {new Set(computed.albumNo1WeeksSorted.map((e) => e.album_name)).size}{' '}
                <span className="text-[18px] font-normal">张</span>
              </p>
              {computed.albumNo1List[0] && (
                <NameWithCover
                  coverUrl={computed.albumNo1List[0].cover_url}
                  name={computed.albumNo1List[0].album_name}
                  artistName={computed.albumNo1List[0].artist_name}
                  nameLink={`/billboard/album/${encodeURIComponent(computed.albumNo1List[0].album_name)}`}
                  artistLink={`/billboard/artist/${encodeURIComponent(computed.albumNo1List[0].artist_name)}`}
                  badge="最新冠军"
                />
              )}
            </GlassCard>
            <GlassCard className="p-6">
              <p className="mb-3 font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">最多冠军周数</p>
              <p className="mb-4 font-serif text-[44px] font-bold leading-none tracking-[-1px]">
                {computed.albumNo1WeeksSorted[0]?.weeks_at_no1 ?? 0}{' '}
                <span className="text-[18px] font-normal">周</span>
              </p>
              {computed.albumNo1WeeksSorted[0] && (
                <NameWithCover
                  coverUrl={computed.albumNo1WeeksSorted[0].cover_url}
                  name={computed.albumNo1WeeksSorted[0].album_name}
                  artistName={computed.albumNo1WeeksSorted[0].artist_name}
                  nameLink={`/billboard/album/${encodeURIComponent(computed.albumNo1WeeksSorted[0].album_name)}`}
                  artistLink={`/billboard/artist/${encodeURIComponent(computed.albumNo1WeeksSorted[0].artist_name)}`}
                />
              )}
            </GlassCard>
            <GlassCard className="p-6">
              <p className="mb-3 font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">最长连冠纪录</p>
              <p className="mb-4 font-serif text-[44px] font-bold leading-none tracking-[-1px]">
                {computed.albumLongest.streak}{' '}
                <span className="text-[18px] font-normal">周</span>
              </p>
              {computed.albumLongest.streak > 0 && (() => {
                const e = computed.albumNo1WeeksSorted.find((a) => a.album_name === computed.albumLongest.name)
                if (!e) return null
                return (
                  <NameWithCover
                    coverUrl={e.cover_url}
                    name={e.album_name}
                    artistName={displayName(e.artist_name)}
                    nameLink={`/billboard/album/${encodeURIComponent(e.album_name)}`}
                    artistLink={`/billboard/artist/${encodeURIComponent(e.artist_name)}`}
                  />
                )
              })()}
            </GlassCard>
          </div>

          <GlassCard className="mb-8 overflow-hidden p-6">
            <div className="mb-5 flex items-center justify-between">
              <h2 className="font-serif text-[22px] font-bold tracking-[-0.3px]">每周冠军专辑</h2>
              <YearSwitcher uniqueCount={yearFiltered.uniqueAlbumCount} unit="张冠军专辑" />
            </div>
            <div className="max-h-[600px] overflow-auto">
              <table className="w-full table-fixed border-collapse">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="sticky top-0 w-[96px] bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">周</th>
                    <th className="sticky top-0 bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">冠军专辑</th>
                    <th className="sticky top-0 w-[132px] bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">总播放</th>
                    <th className="sticky top-0 w-[72px] bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">入榜曲数</th>
                    <th className="sticky top-0 w-[64px] bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">Pk Wks</th>
                  </tr>
                </thead>
                <tbody>
                  {yearFiltered.albums.map((e) => (
                    <tr key={`${e.album_name}-${e.artist_name}-${e.billboard_week}`} className="border-b border-border transition-colors hover:bg-muted/30">
                      <td className="w-[96px] py-3 font-sans text-[13px]">
                        <Link to={`/billboard?week=${e.billboard_week}`} className="text-foreground transition-colors hover:text-accent-foreground">
                          {formatWeekStart(e.billboard_week)}
                        </Link>
                      </td>
                      <td className="py-3">
                        <NameWithCover
                          coverUrl={e.cover_url}
                          name={e.album_name}
                          artistName={displayName(e.artist_name)}
                          nameLink={`/billboard/album/${encodeURIComponent(e.album_name)}`}
                          artistLink={`/billboard/artist/${encodeURIComponent(e.artist_name)}`}
                        />
                      </td>
                      <td className="py-3 text-right">
                        <PlayCountCell value={e.play_count} max={yearFiltered.albumMaxPlays} />
                      </td>
                      <td className="py-3 text-right font-sans text-[13px] tabular-nums">{e.tracks_count}</td>
                      <td className="py-3 text-right font-sans text-[13px] tabular-nums">{e.album_pk_wks}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassCard>

          <div className="mb-8 grid grid-cols-2 gap-6">
            <GlassCard className="overflow-hidden p-6">
              <h2 className="mb-5 font-serif text-[22px] font-bold tracking-[-0.3px]">冠军周数排行</h2>
              <div className="max-h-[500px] overflow-auto">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="border-b border-border text-left">
                      <th className="sticky top-0 bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">#</th>
                      <th className="sticky top-0 bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">专辑</th>
                      <th className="sticky top-0 bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">冠军周数</th>
                    </tr>
                  </thead>
                  <tbody>
                    {computed.albumNo1WeeksSorted.slice(0, 20).map((e, i) => (
                      <tr key={`${e.album_name}-${e.artist_name}`} className="border-b border-border transition-colors hover:bg-muted/30">
                        <td className="py-3 font-serif text-[15px] font-semibold tabular-nums text-muted-foreground">{i + 1}</td>
                        <td className="py-3">
                          <NameWithCover
                            coverUrl={e.cover_url}
                            name={e.album_name}
                            artistName={displayName(e.artist_name)}
                            nameLink={`/billboard/album/${encodeURIComponent(e.album_name)}`}
                            artistLink={`/billboard/artist/${encodeURIComponent(e.artist_name)}`}
                          />
                        </td>
                        <td className="py-3 text-right font-sans text-[13px] font-semibold tabular-nums">{e.weeks_at_no1}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </GlassCard>

            <GlassCard className="p-6">
              <h2 className="mb-5 font-serif text-[22px] font-bold tracking-[-0.3px]">专辑冠军周数 Top 15</h2>
              {computed.albumNo1WeeksSorted.length === 0 ? (
                <p className="py-8 text-center font-sans text-[13px] text-muted-foreground">暂无专辑冠军数据</p>
              ) : (
                <No1BarChart
                  label="冠军周数"
                  data={computed.albumNo1WeeksSorted.slice(0, 15).map((e) => ({
                    name: e.album_name,
                    value: e.weeks_at_no1,
                    subtitle: e.artist_name,
                  }))}
                />
              )}
            </GlassCard>
          </div>

          <div className="mb-8">
            <AnnualSection title="每年独特冠军专辑统计" items={computed.albumAnnualNo1} />
          </div>

          <GlassCard className="overflow-hidden p-6">
            <h2 className="mb-1 font-serif text-[22px] font-bold tracking-[-0.3px]">空冠专辑</h2>
            <p className="mb-5 font-sans text-[13px] text-muted-foreground">
              首次上榜即 #1 · 共 {computed.debutNo1Albums.length} 张
            </p>
            {computed.debutNo1Albums.length === 0 ? (
              <p className="py-8 text-center font-sans text-[13px] text-muted-foreground">暂无空冠专辑</p>
            ) : (
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">专辑</th>
                    <th className="pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">首次上榜周</th>
                    <th className="pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">在榜周数</th>
                    <th className="pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">冠军周数</th>
                  </tr>
                </thead>
                <tbody>
                  {computed.debutNo1Albums.map((e) => (
                    <tr key={`${e.album_name}-${e.artist_name}`} className="border-b border-border transition-colors hover:bg-muted/30">
                      <td className="py-3">
                        <NameWithCover
                          coverUrl={e.cover_url}
                          name={e.album_name}
                          artistName={displayName(e.artist_name)}
                          nameLink={`/billboard/album/${encodeURIComponent(e.album_name)}`}
                          artistLink={`/billboard/artist/${encodeURIComponent(e.artist_name)}`}
                        />
                      </td>
                      <td className="py-3 font-sans text-[13px]">
                        <Link to={`/billboard?week=${e.billboard_week}`} className="text-foreground transition-colors hover:text-accent-foreground">
                          {formatWeekStart(e.billboard_week)}
                        </Link>
                      </td>
                      <td className="py-3 text-right font-sans text-[13px] tabular-nums">{e.weeks_on_chart}</td>
                      <td className="py-3 text-right font-sans text-[13px] tabular-nums">{e.weeks_at_no1}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </GlassCard>
        </>
      )}

      {/* ══════════════════════════════════════════════
          Tab: 艺人榜
          ══════════════════════════════════════════════ */}
      {activeTab === 'artists' && (
        <>
          <div className="mb-8 grid grid-cols-3 gap-6">
            <GlassCard className="p-6">
              <p className="mb-3 font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">总冠军艺人</p>
              <p className="mb-4 font-serif text-[44px] font-bold leading-none tracking-[-1px]">
                {computed.artistNo1WeeksSorted.length} <span className="text-[18px] font-normal">位</span>
              </p>
              {computed.artistNo1List[0] && (
                <div className="flex items-center gap-3">
                  <CoverImg url={computed.artistNo1List[0].cover_url} />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Link
                        to={`/billboard/artist/${encodeURIComponent(computed.artistNo1List[0].artist_name)}`}
                        className="truncate font-sans text-sm font-semibold transition-colors hover:text-accent-foreground"
                      >
                        {displayName(computed.artistNo1List[0].artist_name)}
                      </Link>
                      <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 font-sans text-[10px] font-semibold uppercase tracking-[0.6px] text-amber-600 dark:text-amber-400">
                        最新冠军
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </GlassCard>
            <GlassCard className="p-6">
              <p className="mb-3 font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">最多冠军周数</p>
              <p className="mb-4 font-serif text-[44px] font-bold leading-none tracking-[-1px]">
                {computed.artistNo1WeeksSorted[0]?.weeks_at_no1 ?? 0}{' '}
                <span className="text-[18px] font-normal">周</span>
              </p>
              {computed.artistNo1WeeksSorted[0] && (
                <div className="flex items-center gap-3">
                  <CoverImg url={computed.artistNo1WeeksSorted[0].cover_url} />
                  <Link
                    to={`/billboard/artist/${encodeURIComponent(computed.artistNo1WeeksSorted[0].artist_name)}`}
                    className="block truncate font-sans text-sm font-semibold transition-colors hover:text-accent-foreground"
                  >
                    {displayName(computed.artistNo1WeeksSorted[0].artist_name)}
                  </Link>
                </div>
              )}
            </GlassCard>
            <GlassCard className="p-6">
              <p className="mb-3 font-sans text-[12px] font-semibold uppercase tracking-[1px] text-muted-foreground">最长连冠纪录</p>
              <p className="mb-4 font-serif text-[44px] font-bold leading-none tracking-[-1px]">
                {computed.artistLongest.streak}{' '}
                <span className="text-[18px] font-normal">周</span>
              </p>
              {computed.artistLongest.streak > 0 && (() => {
                const e = computed.artistNo1WeeksSorted.find((a) => a.artist_name === computed.artistLongest.name)
                if (!e) return null
                return (
                  <div className="flex items-center gap-3">
                    <CoverImg url={e.cover_url} />
                    <Link
                      to={`/billboard/artist/${encodeURIComponent(e.artist_name)}`}
                      className="block truncate font-sans text-sm font-semibold transition-colors hover:text-accent-foreground"
                    >
                      {displayName(e.artist_name)}
                    </Link>
                  </div>
                )
              })()}
            </GlassCard>
          </div>

          <GlassCard className="mb-8 overflow-hidden p-6">
            <div className="mb-5 flex items-center justify-between">
              <h2 className="font-serif text-[22px] font-bold tracking-[-0.3px]">每周冠军艺人</h2>
              <YearSwitcher uniqueCount={yearFiltered.uniqueArtistCount} unit="位冠军艺人" />
            </div>
            <div className="max-h-[600px] overflow-auto">
              <table className="w-full table-fixed border-collapse">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="sticky top-0 w-[96px] bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">周</th>
                    <th className="sticky top-0 bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">冠军艺人</th>
                    <th className="sticky top-0 w-[132px] bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">总播放</th>
                    <th className="sticky top-0 w-[72px] bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">入榜曲数</th>
                    <th className="sticky top-0 w-[72px] bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">入榜专辑</th>
                    <th className="sticky top-0 w-[64px] bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">Pk Wks</th>
                  </tr>
                </thead>
                <tbody>
                  {yearFiltered.artists.map((e) => (
                    <tr key={`${e.artist_name}-${e.billboard_week}`} className="border-b border-border transition-colors hover:bg-muted/30">
                      <td className="w-[96px] py-3 font-sans text-[13px]">
                        <Link to={`/billboard?week=${e.billboard_week}`} className="text-foreground transition-colors hover:text-accent-foreground">
                          {formatWeekStart(e.billboard_week)}
                        </Link>
                      </td>
                      <td className="py-3">
                        <div className="flex items-center gap-3">
                          <CoverImg url={e.cover_url} />
                          <Link
                            to={`/billboard/artist/${encodeURIComponent(e.artist_name)}`}
                            className="block truncate font-sans text-sm font-semibold transition-colors hover:text-accent-foreground"
                          >
                            {displayName(e.artist_name)}
                          </Link>
                        </div>
                      </td>
                      <td className="py-3 text-right">
                        <PlayCountCell value={e.play_count} max={yearFiltered.artistMaxPlays} />
                      </td>
                      <td className="py-3 text-right font-sans text-[13px] tabular-nums">{e.tracks_count}</td>
                      <td className="py-3 text-right font-sans text-[13px] tabular-nums">{e.albums_count}</td>
                      <td className="py-3 text-right font-sans text-[13px] tabular-nums">{e.artist_pk_wks}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassCard>

          <div className="mb-8 grid grid-cols-2 gap-6">
            <GlassCard className="overflow-hidden p-6">
              <h2 className="mb-5 font-serif text-[22px] font-bold tracking-[-0.3px]">冠军周数排行</h2>
              <div className="max-h-[500px] overflow-auto">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="border-b border-border text-left">
                      <th className="sticky top-0 bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">#</th>
                      <th className="sticky top-0 bg-card pb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">艺人</th>
                      <th className="sticky top-0 bg-card pb-3 text-right font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">冠军周数</th>
                    </tr>
                  </thead>
                  <tbody>
                    {computed.artistNo1WeeksSorted.slice(0, 20).map((e, i) => (
                      <tr key={displayName(e.artist_name)} className="border-b border-border transition-colors hover:bg-muted/30">
                        <td className="py-3 font-serif text-[15px] font-semibold tabular-nums text-muted-foreground">{i + 1}</td>
                        <td className="py-3">
                          <div className="flex items-center gap-3">
                            <CoverImg url={e.cover_url} />
                            <Link
                              to={`/billboard/artist/${encodeURIComponent(e.artist_name)}`}
                              className="block truncate font-sans text-sm font-semibold transition-colors hover:text-accent-foreground"
                            >
                              {displayName(e.artist_name)}
                            </Link>
                          </div>
                        </td>
                        <td className="py-3 text-right font-sans text-[13px] font-semibold tabular-nums">{e.weeks_at_no1}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </GlassCard>

            <GlassCard className="p-6">
              <h2 className="mb-5 font-serif text-[22px] font-bold tracking-[-0.3px]">艺人冠军周数 Top 15</h2>
              {computed.artistNo1WeeksSorted.length === 0 ? (
                <p className="py-8 text-center font-sans text-[13px] text-muted-foreground">暂无艺人冠军数据</p>
              ) : (
                <No1BarChart
                  label="冠军周数"
                  data={computed.artistNo1WeeksSorted.slice(0, 15).map((e) => ({
                    name: e.artist_name,
                    value: e.weeks_at_no1,
                  }))}
                />
              )}
            </GlassCard>
          </div>
        </>
      )}
    </>
  )
}
