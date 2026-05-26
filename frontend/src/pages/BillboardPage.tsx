import { useState, useMemo, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useBillboard } from '@/hooks/useBillboard'
import { GlassCard } from '@/components/shared/GlassCard'
import { WeekSelector } from '@/components/shared/WeekSelector'

import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { WeeklyTrackEntry, WeeklyAlbumEntry, WeeklyArtistEntry } from '@/types/billboard'
import { type RankChange, ChangeCell } from '@/components/shared/ChangeCell'

// ── helpers ──────────────────────────────────────────────

function formatWeekLabel(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso + 'T00:00:00')
  const end = new Date(d)
  end.setDate(end.getDate() + 6)
  const y = d.getFullYear()
  const weekNum = Math.ceil(
    ((d.getTime() - new Date(y, 0, 1).getTime()) / 86400000 + new Date(y, 0, 1).getDay() + 1) / 7,
  )
  return `Week ${weekNum}, ${y}`
}

function formatDateRange(iso: string): string {
  if (!iso) return ''
  const fmt = (d: Date) =>
    `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
  const start = new Date(iso + 'T00:00:00')
  const end = new Date(start)
  end.setDate(end.getDate() + 6)
  return `${fmt(start)} — ${fmt(end)}`
}

function formatNumber(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n)
}

const CHART_COLORS = [
  'oklch(0.563 0.18 28.2)',
  'oklch(0.583 0.108 51.4)',
  'oklch(0.623 0.14 79.9)',
  'oklch(0.443 0.065 151.5)',
  'oklch(0.425 0.095 267.8)',
  'oklch(0.47 0.06 330)',
]

type TabKey = 'tracks' | 'albums' | 'artists'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'tracks', label: '单曲榜' },
  { key: 'albums', label: '专辑榜' },
  { key: 'artists', label: '艺人榜' },
]

// ── rank change computation ───────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyEntry = any

function computeRankChange(
  entry: WeeklyTrackEntry | WeeklyAlbumEntry | WeeklyArtistEntry,
  prevWeekEntries: (WeeklyTrackEntry | WeeklyAlbumEntry | WeeklyArtistEntry)[],
  allWeeksEntries: (WeeklyTrackEntry | WeeklyAlbumEntry | WeeklyArtistEntry)[],
  field: 'track_id' | 'album_name' | 'artist_name',
): RankChange {
  const e = entry as AnyEntry
  const id = e[field]
  const prev = prevWeekEntries.find(
    (p) => (p as AnyEntry)[field] === id,
  )
  if (prev) {
    const prevE = prev as AnyEntry
    const delta = prevE.rank - e.rank
    if (delta > 0) return { type: 'up', delta }
    if (delta < 0) return { type: 'down', delta: Math.abs(delta) }
    return { type: 'same' }
  }
  const appearedBefore = allWeeksEntries.some(
    (p) => (p as AnyEntry)[field] === id,
  )
  return appearedBefore ? { type: 're' } : { type: 'new' }
}

// ── sub-components ────────────────────────────────────────

function CoverCell({ index, isNewOrRe, coverUrl }: { index: number; isNewOrRe: boolean; coverUrl?: string | null }) {
  const [imgError, setImgError] = useState(false)
  useEffect(() => { setImgError(false) }, [coverUrl])

  if (isNewOrRe) {
    if (coverUrl && !imgError) {
      return (
        <img
          src={coverUrl}
          alt=""
          className="h-10 w-10 rounded-[8px] object-cover"
          onError={() => setImgError(true)}
          loading="lazy"
        />
      )
    }
    return (
      <div className="flex h-10 w-10 items-center justify-center rounded-[8px] bg-muted text-base">
        {'🆕'}
      </div>
    )
  }
  if (coverUrl && !imgError) {
    return (
      <img
        src={coverUrl}
        alt=""
        className="h-10 w-10 rounded-[8px] object-cover"
        onError={() => setImgError(true)}
        loading="lazy"
      />
    )
  }
  const c = CHART_COLORS[index % CHART_COLORS.length]
  const c2 = CHART_COLORS[(index + 1) % CHART_COLORS.length]
  return (
    <div
      className="flex h-10 w-10 items-center justify-center rounded-[8px] text-base opacity-85"
      style={{ background: `linear-gradient(135deg, ${c}, ${c2})` }}
    >
      🎵
    </div>
  )
}

function BillboardSkeleton() {
  return (
    <>
      <div className="mb-6">
        <Skeleton className="mb-3 h-3 w-24" />
        <Skeleton className="h-[44px] w-64" />
      </div>
      <div className="mb-5 flex gap-7">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-6 w-16" />
        ))}
      </div>
      <div className="mb-6 flex gap-3.5">
        <Skeleton className="h-[34px] w-[34px] rounded-full" />
        <Skeleton className="h-[50px] w-48" />
        <Skeleton className="h-[34px] w-[34px] rounded-full" />
      </div>
      <Skeleton className="mb-6 h-12 w-full rounded-[16px]" />
      <Skeleton className="h-[600px] w-full rounded-[16px]" />
    </>
  )
}

// ── main page ─────────────────────────────────────────────

export function BillboardPage() {
  const [searchParams] = useSearchParams()
  const initialWeek = searchParams.get('week')

  const {
    data,
    loading,
    error,
    refetch,
    selectedWeek,
    currentWeekData,
    currentIndex,
    totalWeeks,
    goNext,
    goPrev,
  } = useBillboard(initialWeek)

  const [activeTab, setActiveTab] = useState<TabKey>('tracks')

  // compute rank changes for current tab
  const prevWeek = data?.meta.all_weeks_desc[currentIndex + 1]
  const prevWeekData = useMemo(() => {
    if (!data || !prevWeek) return []
    switch (activeTab) {
      case 'tracks':
        return data.weekly.filter((w) => w.billboard_week === prevWeek)
      case 'albums':
        return data.weekly_album.filter((w) => w.billboard_week === prevWeek)
      case 'artists':
        return data.weekly_artist.filter((w) => w.billboard_week === prevWeek)
    }
  }, [data, prevWeek, activeTab])

  const allWeeksData = useMemo(() => {
    if (!data) return []
    const weeksBefore = data.meta.all_weeks_desc.slice(currentIndex + 1)
    switch (activeTab) {
      case 'tracks':
        return data.weekly.filter((w) => weeksBefore.includes(w.billboard_week))
      case 'albums':
        return data.weekly_album.filter((w) => weeksBefore.includes(w.billboard_week))
      case 'artists':
        return data.weekly_artist.filter((w) => weeksBefore.includes(w.billboard_week))
    }
  }, [data, activeTab, currentIndex])

  // Summary stats
  const summary = useMemo(() => {
    const entries = currentWeekData[activeTab]
    const maxPlays = entries.reduce((max, e) => Math.max(max, e.play_count), 0)
    const totalPlays = entries.reduce((sum, e) => sum + e.play_count, 0)
    let newCount = 0, reCount = 0
    const idField = activeTab === 'tracks' ? 'track_id' : activeTab === 'albums' ? 'album_name' : 'artist_name'
    entries.forEach((entry) => {
      const ch = computeRankChange(
        entry as WeeklyTrackEntry & WeeklyAlbumEntry & WeeklyArtistEntry,
        prevWeekData as (WeeklyTrackEntry & WeeklyAlbumEntry & WeeklyArtistEntry)[],
        allWeeksData as (WeeklyTrackEntry & WeeklyAlbumEntry & WeeklyArtistEntry)[],
        idField,
      )
      if (ch.type === 'new') newCount++
      if (ch.type === 're') reCount++
    })
    return { maxPlays, totalPlays, newCount, reCount, total: entries.length }
  }, [currentWeekData, activeTab, prevWeekData, allWeeksData])

  return (
    <>
      {loading && <BillboardSkeleton />}

      {error && (
        <div className="flex flex-col items-center gap-4 py-20 text-center">
          <AlertCircle className="h-8 w-8 text-accent-foreground" />
          <p className="text-muted-foreground">加载失败：{error}</p>
          <button
            onClick={refetch}
            className="rounded-full bg-accent-foreground px-6 py-2 text-[13px] font-semibold text-primary-foreground transition-opacity hover:opacity-85"
          >
            重新加载
          </button>
        </div>
      )}

      {data && !loading && (
        <>
          {/* Hero */}
          <section className="mb-6">
            <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
              Chart / Weekly
            </p>
            <div className="flex items-end justify-between">
              <h1 className="font-serif text-[44px] font-bold leading-[1.06] tracking-[-1.2px]">
                Billboard 周榜
              </h1>
              <Link
                to="/billboard/number-ones"
                className="mb-1 font-sans text-[13px] font-medium text-muted-foreground transition-colors hover:text-foreground"
              >
                每周榜首 →
              </Link>
            </div>
          </section>

          {/* Tabs */}
          <div className="mb-5 flex gap-7 border-b border-border">
            {TABS.map((tab) => (
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

          {/* Week Selector */}
          <WeekSelector
            weekLabel={formatWeekLabel(selectedWeek)}
            dateRange={formatDateRange(selectedWeek)}
            onPrev={() => goPrev()}
            onNext={() => goNext()}
            disablePrev={currentIndex >= totalWeeks - 1}
            disableNext={currentIndex <= 0}
          />

          {/* Summary Strip */}
          <div className="mb-6 flex gap-9 border-b border-border py-4">
            <div>
              <span className="font-serif text-2xl font-semibold text-[#3B5998] dark:text-[#7B9CC8]">
                {summary.newCount}
              </span>
              <span className="ml-2 font-sans text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">
                新入榜
              </span>
            </div>
            <div>
              <span className="font-serif text-2xl font-semibold text-[#B8860B] dark:text-[#D4A24E]">
                {summary.reCount}
              </span>
              <span className="ml-2 font-sans text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">
                重回榜
              </span>
            </div>
            <div>
              <span className="font-serif text-2xl font-semibold">
                {formatNumber(summary.maxPlays)}
              </span>
              <span className="ml-2 font-sans text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">
                当周最高播放
              </span>
            </div>
            <div>
              <span className="font-serif text-2xl font-semibold">
                {formatNumber(summary.totalPlays)}
              </span>
              <span className="ml-2 font-sans text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">
                当周总播放
              </span>
            </div>
          </div>

          {/* Ranking Table */}
          <GlassCard className="overflow-hidden p-0">
            <table className="mx-7 my-0 w-[calc(100%-56px)] border-collapse">
              <thead>
                <tr>
                  <th className="w-10 pb-3.5 pt-4 text-center font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    #
                  </th>
                  <th className="w-11 pb-3.5 pt-4 font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    变动
                  </th>
                  <th className="w-[52px] pb-3.5 pt-4" />
                  <th className="pb-3.5 pt-4 text-left font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    曲目
                  </th>
                  <th className="pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    播放
                  </th>
                  <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    PK
                  </th>
                  <th className="w-16 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    PK Wks
                  </th>
                  <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    在榜
                  </th>
                </tr>
              </thead>
              <tbody>
                {(currentWeekData[activeTab] as (WeeklyTrackEntry & WeeklyAlbumEntry & WeeklyArtistEntry)[]).map(
                  (entry, i) => {
                    const idField =
                      activeTab === 'tracks'
                        ? 'track_id'
                        : activeTab === 'albums'
                          ? 'album_name'
                          : 'artist_name'
                    const change = computeRankChange(
                      entry,
                      prevWeekData as (WeeklyTrackEntry & WeeklyAlbumEntry & WeeklyArtistEntry)[],
                      allWeeksData as (WeeklyTrackEntry & WeeklyAlbumEntry & WeeklyArtistEntry)[],
                      idField,
                    )
                    const isNewOrRe = change.type === 'new' || change.type === 're'
                    const isTop3 = i < 3
                    const rankColor = i === 0 ? 'text-accent-foreground' : i === 1 ? 'text-muted-foreground' : 'text-[#C17A4E] dark:text-[#C97B6B]'

                    // Navigation links
                    const detailLink =
                      activeTab === 'artists'
                        ? `/billboard/artist/${encodeURIComponent((entry as WeeklyArtistEntry).artist_name)}`
                        : activeTab === 'albums'
                          ? `/billboard/album/${encodeURIComponent((entry as WeeklyAlbumEntry).album_name)}?artist=${encodeURIComponent((entry as WeeklyAlbumEntry).artist_name)}`
                          : `/billboard/track/${(entry as WeeklyTrackEntry).track_id}`
                    const displayName =
                      activeTab === 'artists'
                        ? (entry as WeeklyArtistEntry).artist_name
                        : activeTab === 'albums'
                          ? (entry as WeeklyAlbumEntry).album_name
                          : (entry as WeeklyTrackEntry).track_name
                    const artistLink =
                      activeTab !== 'artists'
                        ? `/billboard/artist/${encodeURIComponent(
                            activeTab === 'tracks'
                              ? (entry as WeeklyTrackEntry).artist_name
                              : (entry as WeeklyAlbumEntry).artist_name,
                          )}`
                        : null
                    const subLabel =
                      activeTab === 'tracks'
                        ? (entry as WeeklyTrackEntry).artist_name
                        : activeTab === 'albums'
                          ? (entry as WeeklyAlbumEntry).artist_name
                          : `${(entry as WeeklyArtistEntry).tracks_count} 首曲目`

                    // As-of-week metrics from weekly entry (PK, Wks, PK Wks are
                    // computed up to and including the current week, not all-time)
                    const runningPeak = entry.running_peak ?? entry.rank
                    const runningWks = entry.running_wks ?? 1
                    const runningPeakWks = entry.running_peak_wks ?? 0

                    return (
                      <tr
                        key={`${activeTab}-${i}`}
                        className="transition-colors hover:bg-muted/50"
                      >
                        <td
                          className={cn(
                            'pb-3.5 pt-3.5 text-center font-serif text-[22px] font-semibold',
                            isTop3 ? rankColor : 'text-muted-foreground',
                          )}
                        >
                          {String(entry.rank).padStart(2, '0')}
                        </td>
                        <td className="pb-3.5 pt-3.5 text-center">
                          <ChangeCell change={change} />
                        </td>
                        <td className="pb-3.5 pt-3.5">
                          <CoverCell index={i} isNewOrRe={isNewOrRe} coverUrl={entry.cover_url} />
                        </td>
                        <td className="pb-3.5 pt-3.5">
                          <Link
                            to={detailLink}
                            className="font-sans text-sm font-semibold transition-colors hover:text-accent-foreground"
                          >
                            {displayName}
                          </Link>
                          {artistLink ? (
                            <Link
                              to={artistLink}
                              className="mt-0.5 block font-sans text-[12px] italic text-muted-foreground transition-colors hover:text-accent-foreground"
                            >
                              {subLabel}
                            </Link>
                          ) : (
                            <div className="mt-0.5 font-sans text-[12px] italic text-muted-foreground">
                              {subLabel}
                            </div>
                          )}
                        </td>
                        <td className="pb-3.5 pt-3.5 text-right font-sans text-[15px] font-semibold tabular-nums">
                          {formatNumber(entry.play_count)}
                          <span className="ml-2 inline-block h-[3px] w-[70px] rounded-[2px] bg-muted align-middle">
                            <span
                              className="block h-full rounded-[2px] bg-accent-foreground transition-[width] duration-300"
                              style={{
                                width: `${Math.round((entry.play_count / (summary.maxPlays || 1)) * 100)}%`,
                              }}
                            />
                          </span>
                        </td>
                        <td
                          className={cn(
                            'pb-3.5 pt-3.5 text-right font-sans text-[13px]',
                            (isNewOrRe ? entry.rank : runningPeak) === 1 ? 'font-bold text-accent-foreground' : 'text-muted-foreground',
                          )}
                        >
                          {isNewOrRe ? entry.rank : runningPeak}
                        </td>
                        <td className="pb-3.5 pt-3.5 text-right font-sans text-[13px] text-muted-foreground">
                          {runningPeakWks > 0 ? (
                            <span className="font-semibold">{runningPeakWks}</span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="pb-3.5 pt-3.5 text-right font-sans text-[13px] text-muted-foreground">
                          {runningWks}
                        </td>
                      </tr>
                    )
                  },
                )}
              </tbody>
            </table>
          </GlassCard>

          {/* Footer */}
          <p className="mt-6 font-serif text-[13px] italic text-muted-foreground">
            共 {summary.total} {activeTab === 'tracks' ? '首曲目' : activeTab === 'albums' ? '张专辑' : '组艺人'}
            {' · '}
            更新时间 {new Date().toLocaleDateString('zh-CN')} CST
          </p>
        </>
      )}
    </>
  )
}
