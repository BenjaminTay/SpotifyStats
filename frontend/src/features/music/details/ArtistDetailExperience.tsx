import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { queryKeys } from '@/api/query-keys'
import type { ArtistDetailResponse, ArtistEnrichmentResponse, ReleaseCycleArtistOverviewResponse } from '@/types/billboard'
import { GlassCard } from '@/components/shared/GlassCard'
import { ChangeCell } from '@/components/shared/ChangeCell'
import { CoverCell } from '@/components/shared/CoverCell'
import { FormattedText } from '@/components/shared/FormattedText'
import { ArtistEnrichmentView } from '@/components/shared/ArtistEnrichmentView'
import { EntityStatsPanel } from '@/components/shared/EntityStatsPanel'
import { RankTrendChart } from '@/components/charts/RankTrendChart'
import { displayName } from '@/lib/chinese'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle, ArrowLeft, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  KpiCard,
  KpiStrip,
  PlaysCell,
  dateOnly,
  formatDateShort,
  formatNumber,
  formatTimeSpan,
  formatWeekStart,
} from './MusicDetailPrimitives'
import { ReleaseCycleSection } from './ArtistReleaseCycleSection'

function formatFollowers(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

type ReleaseCoverSource = {
  cover_url?: string | null
  db_album_id?: number | null
}

function releaseCoverUrl(item: ReleaseCoverSource): string | null {
  if (item.cover_url) return item.cover_url
  if (item.db_album_id != null) return `/covers/albums/${item.db_album_id}.jpg`
  return null
}

type TabKey = 'stats' | 'releases' | 'career' | 'overview' | 'tracks' | 'albums'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'stats', label: '播放统计' },
  { key: 'releases', label: '发行周期' },
  { key: 'career', label: '艺人生涯' },
  { key: 'overview', label: '榜单成绩' },
  { key: 'tracks', label: '单曲成绩' },
  { key: 'albums', label: '专辑成绩' },
]

function ArtistDetailSkeleton() {
  return (
    <>
      <Skeleton className="mb-3 h-3 w-32" />
      <Skeleton className="mb-2 h-[44px] w-72" />
      <Skeleton className="mb-6 h-4 w-64" />
      <div className="mb-5 flex gap-7">
        {TABS.map((_, i) => (
          <Skeleton key={i} className="h-6 w-16" />
        ))}
      </div>
      <div className="mb-6 grid grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-[80px] w-full rounded-[16px]" />
        ))}
      </div>
      <Skeleton className="h-[360px] w-full rounded-[16px]" />
    </>
  )
}

function formatReleaseType(type: string): string {
  if (type === 'album') return '专辑'
  if (type === 'single') return '单曲'
  return type
}

// ═══════════════════════════════════════════════════════════
// Page
// ═══════════════════════════════════════════════════════════

export function ArtistDetailExperience() {
  const { artistName } = useParams<{ artistName: string }>()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<TabKey>('stats')

  const { data, isPending, error, refetch } = useQuery({
    queryKey: queryKeys.music.artistDetail(artistName ?? ''),
    queryFn: () => api.get<ArtistDetailResponse>('/billboard/artist/' + artistName!),
    enabled: !!artistName,
  })

  const releaseCycleParams = { weeks_before: 4, weeks_after: 24, cover_version: 2 }
  const {
    data: enrichment = null,
    isFetching: enrichmentLoading,
  } = useQuery({
    queryKey: queryKeys.music.artistEnrichment(data?.artist_name ?? ''),
    queryFn: () =>
      api.get<ArtistEnrichmentResponse>(
        '/billboard/enrichment/artist/' + encodeURIComponent(data!.artist_name),
      ),
    enabled: activeTab === 'career' && !!data?.found,
  })
  const {
    data: releaseCycle = null,
    isFetching: releaseCycleLoading,
    error: releaseCycleQueryError,
  } = useQuery({
    queryKey: queryKeys.music.artistReleaseCycle(data?.artist_name ?? '', releaseCycleParams),
    queryFn: () =>
      api.get<ReleaseCycleArtistOverviewResponse>(
        '/billboard/release-cycle/artist/' + encodeURIComponent(data!.artist_name),
        { weeks_before: 4, weeks_after: 24 },
      ),
    enabled: activeTab === 'releases' && !!data?.found,
  })
  const releaseCycleError = releaseCycleQueryError?.message || null

  const releaseCycles = releaseCycle?.cycles ?? []
  const albumReleaseCycles = releaseCycles.filter((cycle) => cycle.album_type === 'album')
  const singleReleaseCycles = releaseCycles.filter((cycle) => cycle.album_type === 'single')
  const releaseTrendPoints = releaseCycle?.rank_trend
    .filter((entry) => entry.rank != null)
    .map((entry) => ({
      week: dateOnly(entry.billboard_week),
      rank: entry.rank,
    })) ?? []

  return (
    <>
      {isPending && <ArtistDetailSkeleton />}

      {error && (
        <div className="flex flex-col items-center gap-4 py-20 text-center">
          <AlertCircle className="h-8 w-8 text-accent-foreground" />
          <p className="text-muted-foreground">加载失败：{error.message}</p>
          <button
            onClick={() => refetch()}
            className="rounded-full bg-accent-foreground px-6 py-2 text-[13px] font-semibold text-primary-foreground transition-opacity hover:opacity-85"
          >
            重新加载
          </button>
        </div>
      )}

      {data && !isPending && (
        <>
          {!data.found ? (
            <div className="flex flex-col items-center gap-4 py-20 text-center">
              <AlertCircle className="h-8 w-8 text-accent-foreground" />
              <p className="text-muted-foreground">未找到该艺人的榜单数据</p>
              <button
                onClick={() => navigate(-1)}
                className="rounded-full border border-border px-6 py-2 text-[13px] font-semibold transition-colors hover:bg-muted"
              >
                返回 Billboard
              </button>
            </div>
          ) : (
            <>
              {/* Hero */}
              <section className="mb-6">
                <button
                  onClick={() => navigate(-1)}
                  className="mb-4 inline-flex items-center gap-1.5 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-muted-foreground transition-colors hover:text-accent-foreground"
                >
                  <ArrowLeft className="h-3 w-3" />
                  Music / 艺人详情
                </button>
                <div className="flex items-start gap-6">
                  {data.cover_url && (
                    <img
                      src={data.cover_url}
                      alt={data.artist_name}
                      className="h-[120px] w-[120px] flex-shrink-0 rounded-full object-cover shadow-lg"
                    />
                  )}
                  <div>
                    <h1 className="font-serif text-[44px] font-bold leading-[1.06] tracking-[-1.2px]">
                      {displayName(data.artist_name)}
                    </h1>
                    {data.meta && (
                      <div className="mt-2 font-sans text-[14px] text-muted-foreground">
                        {data.meta.genres && data.meta.genres.length > 0 && (
                          <p>
                            {data.meta.genres.slice(0, 4).map(
                              (g) => g.charAt(0).toUpperCase() + g.slice(1)
                            ).join(' · ')}
                          </p>
                        )}
                        {[
                          data.meta.followers && `${formatFollowers(data.meta.followers)} followers`,
                        ].filter(Boolean).length > 0 && (
                          <p>
                            {[
                              data.meta.followers && `${formatFollowers(data.meta.followers)} followers`,
                            ].filter(Boolean).join(' · ')}
                          </p>
                        )}
                        {data.meta.popularity != null && (
                          <div className="mt-1.5 flex items-center gap-2">
                            <span className="font-sans text-[12px] text-muted-foreground">Popularity</span>
                            <span className="inline-block h-[5px] w-[120px] rounded-[3px] bg-muted align-middle">
                              <span
                                className="block h-full rounded-[3px] bg-accent-foreground"
                                style={{ width: `${data.meta.popularity}%` }}
                              />
                            </span>
                            <span className="font-sans text-[12px] font-semibold tabular-nums">{data.meta.popularity}</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </section>

              {/* Tabs */}
              <div className="mb-6 flex gap-7 border-b border-border">
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

              {/* ═══ Tab 1: 榜单表现 ═══ */}
              {activeTab === 'overview' && (
                <>
                  {/* KPI Cards — 2 rows × 2 */}
                  {data.chart_summary && (
                    <div className="mb-8 grid grid-cols-2 gap-5">
                      <KpiCard
                        label="最高排名"
                        value={`#${data.chart_summary.peak_position}${data.chart_summary.peak_weeks > 1 ? ` (${data.chart_summary.peak_weeks}wks)` : ''}`}
                        sub={`首次达峰 ${formatDateShort(data.chart_summary.first_peak_week)}`}
                        accent={data.chart_summary.peak_position === 1}
                      />
                      <KpiCard
                        label="在榜周数"
                        value={formatNumber(data.chart_summary.weeks_on_chart)}
                        sub={`首次入榜 ${formatDateShort(data.chart_summary.first_week)}`}
                      />
                      <KpiCard
                        label="走势点数"
                        value={formatNumber(data.chart_summary.power_score)}
                        sub={
                          data.chart_summary.power_rank
                            ? `走势排名 #${data.chart_summary.power_rank}`
                            : '—'
                        }
                        accentColor="#d94a4a"
                      />
                      <KpiCard
                        label="在榜跨度"
                        value={formatTimeSpan(
                          data.chart_summary.first_week,
                          data.chart_summary.latest_week,
                        )}
                        sub={`${formatDateShort(data.chart_summary.first_week)} — ${formatDateShort(data.chart_summary.latest_week)}`}
                      />
                    </div>
                  )}

                  {/* Rank Trend Chart */}
                  {data.artist_weekly_history.length > 0 && (
                    <div className="mb-8">
                      <h3 className="mb-4 font-serif text-xl font-semibold">艺人排名趋势</h3>
                      <GlassCard className="p-6">
                        <RankTrendChart
                          data={data.artist_weekly_history.map((e) => ({
                            week: e.week,
                            rank: e.rank,
                          }))}
                          topN={30}
                          peakPosition={data.chart_summary?.peak_position}
                          overlayData={data.best_singles_overlay.length > 0 ? data.best_singles_overlay : undefined}
                          overlayLabel="最佳单曲"
                        />
                      </GlassCard>
                    </div>
                  )}

                  {/* Weekly History Table */}
                  {data.artist_weekly_history.length > 0 && (
                    <div className="mb-8">
                      <h3 className="mb-4 font-serif text-xl font-semibold">周榜历史</h3>
                      <GlassCard className="overflow-hidden p-0">
                        <table className="mx-7 my-0 w-[calc(100%-56px)] border-collapse">
                          <thead>
                            <tr>
                              <th className="w-[104px] pb-3.5 pt-4 text-left font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                                榜单周
                              </th>
                              <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                                排名
                              </th>
                              <th className="w-16 pb-3.5 pt-4 text-center font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                                变动
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
                            {(() => {
                              const maxPlays = Math.max(
                                ...data.artist_weekly_history.map((e) => e.play_count),
                                1,
                              )
                              return data.artist_weekly_history.map((entry) => {
                                const change = entry.change
                                  ? (() => {
                                      if (entry.change === 'NEW') return { type: 'new' as const }
                                      if (entry.change === 'RE') return { type: 're' as const }
                                      if (entry.change === '—') return { type: 'same' as const }
                                      const match = entry.change.match(/^▲(\d+)$/)
                                      if (match)
                                        return { type: 'up' as const, delta: parseInt(match[1]) }
                                      const matchD = entry.change.match(/^▼(\d+)$/)
                                      if (matchD)
                                        return { type: 'down' as const, delta: parseInt(matchD[1]) }
                                      return { type: 'same' as const }
                                    })()
                                  : { type: 'new' as const }
                                const isNewOrRe = change.type === 'new' || change.type === 're'
                                const rankColor =
                                  entry.rank === 1
                                    ? 'var(--accent-foreground)'
                                    : entry.rank === 2
                                      ? undefined
                                      : entry.rank === 3
                                        ? '#C17A4E'
                                        : undefined

                                return (
                                  <tr key={entry.week} className="transition-colors hover:bg-muted/50">
                                    <td className="pb-3.5 pt-3.5">
                                      <Link
                                        to={`/billboard?week=${entry.week}`}
                                        className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                                      >
                                        {formatWeekStart(entry.week)}
                                      </Link>
                                    </td>
                                    <td
                                      className="pb-3.5 pt-3.5 text-right font-serif text-[22px] font-semibold"
                                      style={rankColor ? { color: rankColor } : undefined}
                                    >
                                      {String(entry.rank).padStart(2, '0')}
                                    </td>
                                    <td className="pb-3.5 pt-3.5 text-center">
                                      <ChangeCell change={change} />
                                    </td>
                                    <td className="pb-3.5 pt-3.5 text-right font-sans text-[15px] font-semibold tabular-nums">
                                      {formatNumber(entry.play_count)}
                                      <span className="ml-2 inline-block h-[3px] w-[70px] rounded-[2px] bg-muted align-middle">
                                        <span
                                          className="block h-full rounded-[2px] bg-accent-foreground transition-[width] duration-300"
                                          style={{
                                            width: `${Math.round((entry.play_count / maxPlays) * 100)}%`,
                                          }}
                                        />
                                      </span>
                                    </td>
                                    <td
                                      className={cn(
                                        'pb-3.5 pt-3.5 text-right font-sans text-[13px]',
                                        (isNewOrRe ? entry.rank : entry.running_peak) === 1
                                          ? 'font-bold text-accent-foreground'
                                          : 'text-muted-foreground',
                                      )}
                                    >
                                      {isNewOrRe ? entry.rank : entry.running_peak}
                                    </td>
                                    <td className="pb-3.5 pt-3.5 text-right font-sans text-[13px] text-muted-foreground">
                                      {entry.running_peak_wks > 0 ? (
                                        <span className="font-semibold">{entry.running_peak_wks}</span>
                                      ) : (
                                        '—'
                                      )}
                                    </td>
                                    <td className="pb-3.5 pt-3.5 text-right font-sans text-[13px] text-muted-foreground">
                                      {entry.running_wks}
                                    </td>
                                  </tr>
                                )
                              })
                            })()}
                          </tbody>
                        </table>
                      </GlassCard>
                    </div>
                  )}
                </>
              )}

              {/* ═══ Tab 2: 单曲成绩 ═══ */}
              <div className={activeTab === 'stats' ? '' : 'hidden'}>
                <EntityStatsPanel kind="artist" artistName={data?.artist_name} />
              </div>

              {activeTab === 'tracks' && (
                <div className="mb-8">
                  <KpiStrip
                    items={[
                      { label: '入榜曲目', value: formatNumber(data.info.total_tracks) },
                      { label: '#1 曲目', value: formatNumber(data.info.top1), accent: data.info.top1 > 0 },
                      { label: 'Top 5', value: formatNumber(data.info.top5) },
                      { label: 'Top 10', value: formatNumber(data.info.top10) },
                      { label: '冠军周数', value: formatNumber(data.info.weeks_at_no1), accent: data.info.weeks_at_no1 > 0 },
                    ]}
                  />

                  <GlassCard className="overflow-hidden p-0">
                    <table className="mx-7 my-0 w-[calc(100%-56px)] border-collapse">
                      <thead>
                        <tr>
                          <th className="w-[44px] pb-3.5 pt-4 font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground" />
                          <th className="pb-3.5 pt-4 text-left font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            曲目
                          </th>
                          <th className="w-16 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            峰值
                          </th>
                          <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            峰位周
                          </th>
                          <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            在榜
                          </th>
                          <th className="w-28 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            上榜播放
                          </th>
                          <th className="w-[72px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            走势点数
                          </th>
                          <th className="w-[60px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            走势排名
                          </th>
                          <th className="w-[78px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            首周
                          </th>
                          <th className="w-[78px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            首次达峰
                          </th>
                          <th className="w-[78px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                            末周
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {(() => {
                          const maxPlays = Math.max(
                            ...data.tracks.map((t) => t.total_chart_plays),
                            1,
                          )
                          return data.tracks.map((t, i) => (
                            <tr key={t.track_id} className="transition-colors hover:bg-muted/50">
                              <td className="py-3.5 pr-2">
                                <CoverCell index={i} coverUrl={t.cover_url} />
                              </td>
                              <td className="py-3.5 pl-1">
                                <Link
                                  to={`/music/tracks/${t.track_id}`}
                                  className="font-sans text-sm font-semibold leading-snug transition-colors hover:text-accent-foreground"
                                >
                                  {displayName(t.track_name)}
                                </Link>
                                <div className="mt-0.5 font-sans text-[12px] italic text-muted-foreground">
                                  {displayName(data.artist_name)}
                                </div>
                              </td>
                              <td
                                className="py-3.5 text-right font-serif text-[22px] font-bold italic"
                                style={{ color: t.peak_position === 1 ? 'var(--accent-foreground)' : undefined }}
                              >
                                {t.peak_position}
                              </td>
                              <td className="py-3.5 text-right font-sans text-[13px] text-muted-foreground">
                                {t.weeks_at_peak}
                              </td>
                              <td className="py-3.5 text-right font-sans text-[13px] text-muted-foreground">
                                {t.weeks_on_chart}
                              </td>
                              <td className="py-3.5 text-right">
                                <PlaysCell plays={t.total_chart_plays} maxPlays={maxPlays} />
                              </td>
                              <td className="py-3.5 text-right font-sans text-[13px] tabular-nums">
                                {t.power_score > 0 ? formatNumber(t.power_score) : '—'}
                              </td>
                              <td className="py-3.5 text-right font-serif text-[22px] italic text-muted-foreground">
                                {t.power_rank ?? '—'}
                              </td>
                              <td className="py-3.5 text-right">
                                <Link
                                  to={`/billboard?week=${t.first_week}`}
                                  className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                                >
                                  {formatDateShort(t.first_week)}
                                </Link>
                              </td>
                              <td className="py-3.5 text-right">
                                <Link
                                  to={`/billboard?week=${t.first_peak_week}`}
                                  className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                                >
                                  {formatDateShort(t.first_peak_week)}
                                </Link>
                              </td>
                              <td className="py-3.5 text-right">
                                <Link
                                  to={`/billboard?week=${t.last_week}`}
                                  className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                                >
                                  {formatDateShort(t.last_week)}
                                </Link>
                              </td>
                            </tr>
                          ))
                        })()}
                      </tbody>
                    </table>
                  </GlassCard>
                </div>
              )}

              {/* ═══ Tab 3: 专辑成绩 ═══ */}
              {activeTab === 'albums' && (
                <div className="mb-8">
                  <KpiStrip
                    items={[
                      { label: '#1 专辑', value: formatNumber(data.info.num_no1_albums), accent: data.info.num_no1_albums > 0 },
                      { label: '冠军周数', value: formatNumber(data.info.album_no1_weeks), accent: data.info.album_no1_weeks > 0 },
                      { label: '入榜专辑', value: formatNumber(data.albums.length) },
                    ]}
                  />

                  {data.albums.length > 0 ? (
                    <GlassCard className="overflow-hidden p-0">
                      <table className="mx-7 my-0 w-[calc(100%-56px)] border-collapse">
                        <thead>
                          <tr>
                            <th className="w-[44px] pb-3.5 pt-4 font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground" />
                            <th className="pb-3.5 pt-4 text-left font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              专辑
                            </th>
                            <th className="w-16 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              峰值
                            </th>
                            <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              峰位周
                            </th>
                            <th className="w-14 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              在榜
                            </th>
                            <th className="w-28 pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              总播放
                            </th>
                            <th className="w-[72px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              走势点数
                            </th>
                            <th className="w-[60px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              走势
                            </th>
                            <th className="w-[78px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              首周
                            </th>
                            <th className="w-[78px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              首次达峰
                            </th>
                            <th className="w-[78px] pb-3.5 pt-4 text-right font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                              末周
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {(() => {
                            const maxPlays = Math.max(
                              ...data.albums.map((a) => a.total_plays),
                              1,
                            )
                            return data.albums.map((a, i) => (
                              <tr key={a.album_name} className="transition-colors hover:bg-muted/50">
                                <td className="py-3.5 pr-2">
                                  <CoverCell index={i} coverUrl={a.cover_url} />
                                </td>
                                <td className="py-3.5 pl-1">
                                  <Link
                                    to={`/music/albums/${encodeURIComponent(a.album_name)}?artist=${encodeURIComponent(data.artist_name)}`}
                                    className="font-sans text-sm font-semibold leading-snug transition-colors hover:text-accent-foreground"
                                  >
                                    {displayName(a.album_name)}
                                  </Link>
                                  <div className="mt-0.5 font-sans text-[12px] italic text-muted-foreground">
                                    {displayName(data.artist_name)}
                                  </div>
                                </td>
                                <td
                                  className="py-3.5 text-right font-serif text-[22px] font-bold italic"
                                  style={{ color: a.peak === 1 ? 'var(--accent-foreground)' : undefined }}
                                >
                                  {a.peak}
                                </td>
                                <td className="py-3.5 text-right font-sans text-[13px] text-muted-foreground">
                                  {a.pk_wks}
                                </td>
                                <td className="py-3.5 text-right font-sans text-[13px] text-muted-foreground">
                                  {a.weeks}
                                </td>
                                <td className="py-3.5 text-right">
                                  <PlaysCell plays={a.total_plays} maxPlays={maxPlays} />
                                </td>
                                <td className="py-3.5 text-right font-sans text-[13px] tabular-nums">
                                  {a.power_score > 0 ? formatNumber(a.power_score) : '—'}
                                </td>
                                <td className="py-3.5 text-right font-serif text-[22px] italic text-muted-foreground">
                                  {a.power_rank ?? '—'}
                                </td>
                                <td className="py-3.5 text-right">
                                  <Link
                                    to={`/billboard?week=${a.first_week}`}
                                    className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                                  >
                                    {formatDateShort(a.first_week)}
                                  </Link>
                                </td>
                                <td className="py-3.5 text-right">
                                  <Link
                                    to={`/billboard?week=${a.first_peak_week}`}
                                    className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                                  >
                                    {formatDateShort(a.first_peak_week)}
                                  </Link>
                                </td>
                                <td className="py-3.5 text-right">
                                  <Link
                                    to={`/billboard?week=${a.last_week}`}
                                    className="font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                                  >
                                    {formatDateShort(a.last_week)}
                                  </Link>
                                </td>
                              </tr>
                            ))
                          })()}
                        </tbody>
                      </table>
                    </GlassCard>
                  ) : (
                    <p className="py-12 text-center font-sans text-[13px] text-muted-foreground">
                      暂无专辑入榜数据
                    </p>
                  )}
                </div>
              )}

              {/* ═══ Tab 4: 发行周期 ═══ */}
              {activeTab === 'releases' && (
                <div className="mb-8">
                  {releaseCycleLoading ? (
                    <div className="space-y-4">
                      <Skeleton className="h-[112px] w-full rounded-[16px]" />
                      <Skeleton className="h-[340px] w-full rounded-[16px]" />
                    </div>
                  ) : releaseCycleError ? (
                    <GlassCard className="p-8 text-center">
                      <p className="font-sans text-[14px] text-destructive">
                        发行周期数据加载失败：{releaseCycleError}
                      </p>
                    </GlassCard>
                  ) : releaseCycle?.summary ? (
                    <>
                      <div className="mb-8 grid grid-cols-2 gap-5 lg:grid-cols-4">
                        <KpiCard
                          label="发行总数"
                          value={`${releaseCycle.summary.total_albums}/${releaseCycle.summary.total_singles}`}
                          sub="专辑 / 单曲"
                        />
                        <KpiCard
                          label="空冠发行"
                          value={`${releaseCycle.summary.album_debut_no1_count + releaseCycle.summary.single_debut_no1_count}`}
                          sub={`专辑 ${releaseCycle.summary.album_debut_no1_count} · 单曲 ${releaseCycle.summary.single_debut_no1_count}`}
                          accent={releaseCycle.summary.album_debut_no1_count + releaseCycle.summary.single_debut_no1_count > 0}
                        />
                        <KpiCard
                          label="同周双空冠"
                          value={formatNumber(releaseCycle.summary.double_debut_count)}
                          sub="单曲榜与专辑榜同周空冠"
                          accent={releaseCycle.summary.double_debut_count > 0}
                        />
                        <KpiCard
                          label="老歌回榜"
                          value={formatNumber(releaseCycle.summary.total_catalog_reentries)}
                          sub="新发行带动旧作回流"
                        />
                        <KpiCard
                          label="最大艺人冲击"
                          value={releaseCycle.summary.max_artist_impact_fmt ?? '—'}
                          sub={releaseCycle.summary.max_artist_impact_album ? displayName(releaseCycle.summary.max_artist_impact_album) : undefined}
                          accent
                        />
                        <KpiCard
                          label="最大大盘冲击"
                          value={releaseCycle.summary.max_market_impact_fmt ?? '—'}
                          sub={releaseCycle.summary.max_market_impact_album ? displayName(releaseCycle.summary.max_market_impact_album) : undefined}
                        />
                        <KpiCard
                          label="发行事件"
                          value={formatNumber(releaseCycle.release_events.length)}
                          sub="落在播放历史附近的发行"
                        />
                        <KpiCard
                          label="统计跨度"
                          value={formatTimeSpan(releaseCycle.first_play_week ?? '', releaseCycle.last_play_week ?? '')}
                          sub={releaseCycle.first_play_week && releaseCycle.last_play_week ? `${formatDateShort(releaseCycle.first_play_week)} — ${formatDateShort(releaseCycle.last_play_week)}` : undefined}
                        />
                      </div>

                      <div className="mb-8">
                        <h3 className="mb-4 font-serif text-xl font-semibold">发行事件与艺人走势</h3>
                        <GlassCard className="p-6">
                          {releaseTrendPoints.length > 0 ? (
                            <RankTrendChart data={releaseTrendPoints} topN={30} />
                          ) : (
                            <div className="flex h-[220px] items-center justify-center rounded-[12px] border border-dashed border-border">
                              <p className="font-sans text-[13px] text-muted-foreground">
                                当前筛选范围内没有艺人榜排名点。
                              </p>
                            </div>
                          )}
                          {releaseCycle.release_events.length > 0 && (
                            <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2">
                              {releaseCycle.release_events.slice(0, 12).map((event, index) => (
                                <div
                                  key={`${event.album_name}-${event.release_date}`}
                                  className="flex items-center gap-3 rounded-[10px] border border-border/70 p-3"
                                >
                                  <CoverCell index={index} coverUrl={releaseCoverUrl(event)} />
                                  <div className="min-w-0">
                                    <p className="truncate font-sans text-[13px] font-semibold">
                                      {displayName(event.album_name)}
                                    </p>
                                    <p className="mt-0.5 font-sans text-[11px] text-muted-foreground">
                                      {formatDateShort(event.release_date)} · {formatReleaseType(event.album_type)}
                                    </p>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </GlassCard>
                      </div>

                      <div className="mb-8">
                        <h3 className="mb-4 font-serif text-xl font-semibold">发行列表</h3>
                        {albumReleaseCycles.length > 0 && (
                          <ReleaseCycleSection
                            title="专辑"
                            cycles={albumReleaseCycles}
                            artistName={data.artist_name}
                          />
                        )}
                        {singleReleaseCycles.length > 0 && (
                          <ReleaseCycleSection
                            title="单曲"
                            cycles={singleReleaseCycles}
                            artistName={data.artist_name}
                            startIndex={albumReleaseCycles.length}
                          />
                        )}
                      </div>
                    </>
                  ) : (
                    <GlassCard className="p-8 text-center">
                      <p className="font-sans text-[14px] text-muted-foreground">
                        未找到发行周期数据，可能缺少 Spotify 专辑元数据。
                      </p>
                    </GlassCard>
                  )}
                </div>
              )}

              {/* ═══ Tab 4: 艺人生涯 ═══ */}
              {activeTab === 'career' && (
                <div className="mb-8">
                  {/* Wikipedia Bio */}
                  {enrichmentLoading ? (
                    <div className="space-y-4">
                      <Skeleton className="h-[200px] w-full rounded-[16px]" />
                      <Skeleton className="h-[120px] w-full rounded-[16px]" />
                    </div>
                  ) : enrichment?.wiki ? (
                    <>
                      {/* Structured enrichment (LLM) */}
                      {enrichment.wiki.structured ? (
                        <div className="mb-8">
                          <h3 className="mb-4 font-serif text-xl font-semibold">艺人简介</h3>
                          <ArtistEnrichmentView data={enrichment.wiki.structured} />
                          <div className="mt-4">
                            <a
                              href={enrichment.wiki.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                            >
                              <ExternalLink className="h-3 w-3" />
                              Wikipedia
                            </a>
                          </div>
                        </div>
                      ) : (
                        <>
                          {/* Fallback: plain text sections */}
                          <div className="mb-8">
                            <h3 className="mb-4 font-serif text-xl font-semibold">艺人简介</h3>
                            <GlassCard className="p-5">
                              <FormattedText
                                text={enrichment.wiki.summary_zh || enrichment.wiki.summary}
                                className="font-sans text-[14px] leading-relaxed text-foreground/85"
                              />
                              <div className="mt-3">
                                <a
                                  href={enrichment.wiki.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
                                >
                                  <ExternalLink className="h-3 w-3" />
                                  Wikipedia
                                </a>
                              </div>
                            </GlassCard>
                          </div>
                          {(enrichment.wiki.sections_zh?.early_life || enrichment.wiki.sections.early_life) && (
                            <div className="mb-8">
                              <h3 className="mb-4 font-serif text-xl font-semibold">早期生涯</h3>
                              <GlassCard className="p-5">
                                <FormattedText
                                  text={enrichment.wiki.sections_zh?.early_life || enrichment.wiki.sections.early_life}
                                  className="font-sans text-[14px] leading-relaxed text-foreground/85"
                                />
                              </GlassCard>
                            </div>
                          )}
                        </>
                      )}
                    </>
                  ) : (
                    <div className="mb-8">
                      <h3 className="mb-4 font-serif text-xl font-semibold">艺人简介</h3>
                      <GlassCard className="p-5">
                        <p className="font-sans text-[14px] leading-relaxed text-muted-foreground">
                          未找到 Wikipedia 信息
                        </p>
                      </GlassCard>
                    </div>
                  )}

                  {/* Spotify Metadata */}
                  {data.meta && (
                    <div className="mb-8">
                      <h3 className="mb-4 font-serif text-xl font-semibold">Spotify 档案</h3>
                      <GlassCard className="p-5">
                        <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
                          {data.meta.popularity != null && (
                            <div>
                              <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                                流行度
                              </p>
                              <div className="mt-2 flex items-center gap-2">
                                <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                                  <div
                                    className="h-full rounded-full bg-accent-foreground"
                                    style={{ width: `${data.meta.popularity}%` }}
                                  />
                                </div>
                                <span className="font-sans text-[13px] font-semibold tabular-nums">
                                  {data.meta.popularity}
                                </span>
                              </div>
                            </div>
                          )}
                          {data.meta.followers != null && (
                            <div>
                              <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                                粉丝数
                              </p>
                              <p className="mt-1 font-serif text-[28px] font-bold">
                                {formatFollowers(data.meta.followers)}
                              </p>
                            </div>
                          )}
                          {data.meta.genres && data.meta.genres.length > 0 && (
                            <div className="col-span-2">
                              <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                                流派
                              </p>
                              <div className="mt-1 flex flex-wrap gap-1.5">
                                {data.meta.genres.map((g) => (
                                  <span
                                    key={g}
                                    className="rounded-full border border-border px-3 py-1 font-sans text-[12px] text-foreground/75"
                                  >
                                    {g}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </GlassCard>
                    </div>
                  )}
                </div>
              )}

              <p className="mt-6 font-serif text-[13px] italic text-muted-foreground">
                {displayName(data.artist_name)} · 共 {data.info.total_tracks} 首曲目入榜
              </p>
            </>
          )}
        </>
      )}
    </>
  )
}
