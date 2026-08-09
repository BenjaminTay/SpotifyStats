import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AnalysisTrendChart } from '@/components/charts/AnalysisCharts'
import { ListeningClock } from '@/components/charts/ListeningClock'
import { MetricToggle, useAnalysisQueryState } from '@/components/shared/AnalysisControls'
import { AnalysisTimeRangeSelector } from '@/components/shared/AnalysisTimeRangeSelector'
import { GlassCard } from '@/components/shared/GlassCard'
import { KpiCard } from '@/components/shared/KpiCard'
import { PersonalRankTable } from '@/components/shared/StatsTables'
import { RecentPlaysSection } from '@/components/shared/RecentPlaysSection'
import { Skeleton } from '@/components/ui/skeleton'
import { queryKeys } from '@/api/query-keys'
import { analysisApi, useAnalysisFilters } from '@/hooks/useAnalysis'
import { api } from '@/lib/api'
import { getDefaultMergeLevel } from '@/lib/merge-level'
import type { AlbumPersonalRankingResponse, AnalysisMetric, ArtistPersonalRankingResponse, EntityStatsResponse } from '@/types/analysis'
import { useViewportMode } from '@/hooks/useViewportMode'

const ARTIST_RANKING_PAGE_SIZE = 20
const ALBUM_RANKING_PAGE_SIZE = 20

function fmt(n: number | null | undefined): string {
  if (n == null) return '—'
  return new Intl.NumberFormat('zh-CN').format(n)
}

function hours(n: number | undefined): string {
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(n ?? 0)}h`
}

function dateShort(value?: string): string {
  return value ? value.slice(0, 10) : '—'
}

function rankLabel(value: number | null | undefined): string {
  return value ? `#${value}` : '—'
}

export function EntityStatsPanel({
  kind,
  trackId,
  albumName,
  artistName,
  mergeLevel,
  releaseDate,
}: {
  kind: 'track' | 'album' | 'artist'
  trackId?: number | string
  albumName?: string
  artistName?: string
  mergeLevel?: number
  /** ISO date string (e.g. "2023-09-08") — used as the chart origin for album stats. */
  releaseDate?: string
}) {
  const isPhone = useViewportMode() === 'phone'
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const { period, metric, periodValue, startDate, endDate, setQuery, apiParams } = useAnalysisQueryState()
  const entityId = (trackId ?? albumName ?? artistName) != null ? String(trackId ?? albumName ?? artistName) : ''
  const resolvedMergeLevel = mergeLevel ?? getDefaultMergeLevel()
  const statsParams = {
    ...filters,
    ...apiParams,
    ...(kind === 'album' ? { merge_level: resolvedMergeLevel } : {}),
  }
  const { data, isPending, error } = useQuery({
    queryKey: queryKeys.music.entityStats(kind, entityId, statsParams),
    queryFn: () => {
      if (kind === 'track' && trackId != null) {
        return api.get<EntityStatsResponse>(`/music/tracks/${trackId}/stats`, { ...filters, ...apiParams })
      }
      if (kind === 'album' && albumName) {
        return api.get<EntityStatsResponse>(
          `/music/albums/${encodeURIComponent(albumName)}/stats`,
          { ...filters, ...apiParams, ...(artistName ? { artist: artistName } : {}), merge_level: resolvedMergeLevel },
        )
      }
      if (kind === 'artist' && artistName) {
        return api.get<EntityStatsResponse>(`/music/artists/${encodeURIComponent(artistName)}/stats`, { ...filters, ...apiParams })
      }
      return Promise.resolve({ found: false } as EntityStatsResponse)
    },
    enabled: !filtersLoading && entityId !== '',
  })
  const queryError = error instanceof Error ? error.message : error ? String(error) : null

  const [mobileTrendView, setMobileTrendView] = useState<'daily' | 'cumulative'>('daily')
  const [mobileDistributionView, setMobileDistributionView] = useState<'weekday' | 'month' | 'year'>('weekday')
  const [artistRankingKind, setArtistRankingKind] = useState<'track' | 'album'>('track')
  const artistRankingContext = `${period}:${periodValue}:${startDate}:${endDate}:${metric}:${artistName}`
  const [artistRankingPageState, setArtistRankingPageState] = useState({
    context: artistRankingContext,
    track: 1,
    album: 1,
  })
  const artistRankingPages = artistRankingPageState.context === artistRankingContext
    ? artistRankingPageState
    : { context: artistRankingContext, track: 1, album: 1 }
  const artistRankingPage = artistRankingPages[artistRankingKind]
  const artistRankingParams = {
    ...filters,
    ...apiParams,
    entity: artistRankingKind,
    metric,
    limit: ARTIST_RANKING_PAGE_SIZE,
    offset: (artistRankingPage - 1) * ARTIST_RANKING_PAGE_SIZE,
  }
  const { data: artistRanking, isPending: artistRankingPending } = useQuery({
    queryKey: queryKeys.music.artistRankings(artistName ?? '', artistRankingParams),
    queryFn: () => api.get<ArtistPersonalRankingResponse>(
      `/music/artists/${encodeURIComponent(artistName!)}/rankings`, artistRankingParams,
    ),
    enabled: kind === 'artist' && !!artistName && !filtersLoading,
  })

  const albumRankingContext = JSON.stringify({ albumName, artistName, metric, resolvedMergeLevel, ...filters, ...apiParams })
  const [albumRankingPageState, setAlbumRankingPageState] = useState({
    context: albumRankingContext,
    page: 1,
  })
  const albumRankingPage = albumRankingPageState.context === albumRankingContext
    ? albumRankingPageState.page
    : 1
  const albumRankingParams = {
    ...filters,
    ...apiParams,
    ...(artistName ? { artist: artistName } : {}),
    merge_level: resolvedMergeLevel,
    metric,
    limit: ALBUM_RANKING_PAGE_SIZE,
    offset: (albumRankingPage - 1) * ALBUM_RANKING_PAGE_SIZE,
  }
  const { data: albumRanking, isPending: albumRankingPending } = useQuery({
    queryKey: queryKeys.music.albumRankings(albumName ?? '', artistName ?? '', albumRankingParams),
    queryFn: () => api.get<AlbumPersonalRankingResponse>(
      `/music/albums/${encodeURIComponent(albumName!)}/rankings`, albumRankingParams,
    ),
    enabled: kind === 'album' && !!albumName && !filtersLoading,
  })

  const metricKey: AnalysisMetric = metric
  const distributionKey = metricKey === 'plays' ? 'plays' : 'hours'

  // Chart origin = max(release_date, first_play_date).
  // Album released before first listen → start at first play (no useless zero-pad).
  // Album released after earliest plays (advance singles) → start at release date.
  const chartOrigin = useMemo(() => {
    if (!data || data.daily_trend.length === 0) return null
    const firstPlay = data.daily_trend[0].date
    if (!releaseDate) return firstPlay
    return releaseDate > firstPlay ? releaseDate : firstPlay
  }, [releaseDate, data])

  // Pad daily trend with zero-fill from chartOrigin to today.
  // Use UTC noon to avoid local-timezone date shifts.
  const paddedDaily = useMemo(() => {
    if (!data || data.daily_trend.length === 0 || !chartOrigin) return []
    const index = new Map(data.daily_trend.map((d) => [d.date, d]))
    const first = new Date(chartOrigin + 'T12:00:00.000Z')
    const today = new Date()
    today.setUTCHours(12, 0, 0, 0)
    const result: typeof data.daily_trend = []
    const cursor = new Date(first)
    while (cursor <= today) {
      const dateStr = cursor.toISOString().slice(0, 10)
      result.push(index.get(dateStr) ?? { date: dateStr, plays: 0, hours: 0 })
      cursor.setUTCDate(cursor.getUTCDate() + 1)
    }
    return result
  }, [data, chartOrigin])

  // Pad cumulative trend: carry forward last known value from chartOrigin
  const paddedCumulative = useMemo(() => {
    if (!data || data.cumulative_trend.length === 0 || !chartOrigin) return []
    const index = new Map(data.cumulative_trend.map((d) => [d.date, d]))
    const first = new Date(chartOrigin + 'T12:00:00.000Z')
    const today = new Date()
    today.setUTCHours(12, 0, 0, 0)
    const result: typeof data.cumulative_trend = []
    const cursor = new Date(first)
    let lastPlays = 0
    let lastHours = 0
    while (cursor <= today) {
      const dateStr = cursor.toISOString().slice(0, 10)
      const entry = index.get(dateStr)
      if (entry) {
        lastPlays = entry.cumulative_plays
        lastHours = entry.cumulative_hours
        result.push(entry)
      } else {
        result.push({ date: dateStr, cumulative_plays: lastPlays, cumulative_hours: lastHours })
      }
      cursor.setDate(cursor.getDate() + 1)
    }
    return result
  }, [data, chartOrigin])

  if (queryError) return <GlassCard className="p-8 text-center text-destructive">加载失败：{queryError}</GlassCard>
  if (isPending || !data) return <Skeleton className="h-[560px] rounded-[16px]" />
  if (!data.found) return <GlassCard className="p-8 text-muted-foreground">暂无个人播放统计。</GlassCard>

  const metricLabel = metric === 'plays' ? '次' : '小时'
  const dailyChartData = paddedDaily.map((item) => ({ label: item.date.slice(2), value: item[distributionKey] }))
  const cumulativeChartData = paddedCumulative.map((item) => ({
    label: item.date.slice(2),
    value: metric === 'plays' ? item.cumulative_plays : item.cumulative_hours,
  }))
  const mobileTrendData = mobileTrendView === 'daily' ? dailyChartData : cumulativeChartData
  const mobileDistributionData = mobileDistributionView === 'weekday'
    ? data.weekday_distribution.map((item) => ({ label: item.day, value: item[distributionKey] }))
    : mobileDistributionView === 'month'
      ? data.month_distribution.map((item) => ({ label: `${item.month}月`, value: item[distributionKey] }))
      : data.year_distribution.map((item) => ({ label: String(item.year), value: item[distributionKey] }))

  return (
    <div className="entity-stats-panel space-y-8">
      {/* Header */}
      <div className="entity-stats-controls flex flex-wrap items-end justify-between gap-4">
        <AnalysisTimeRangeSelector period={period} periodValue={periodValue} startDate={startDate} endDate={endDate} onChange={setQuery} quickFirst />
        <MetricToggle metric={metric} onChange={(next) => setQuery({ metric: next })} />
      </div>

      {/* KPIs Row 1: 播放概览 — 6 cards */}
      <div className="entity-stats-kpi-grid grid gap-5 md:grid-cols-3 xl:grid-cols-6">
        <KpiCard label="总播放次数" value={fmt(data.summary.total_plays)} />
        <KpiCard label="总播放时长" value={hours(data.summary.total_hours)} />
        <KpiCard label="日均播放" value={fmt(Math.round(data.daily_metrics.avg_daily_plays))} />
        <KpiCard label="日均时长" value={hours(data.daily_metrics.avg_daily_hours)} />
        <KpiCard label="首次播放" value={dateShort(data.first_played)} />
        <KpiCard label="最近播放" value={dateShort(data.last_played)} />
      </div>

      {/* KPIs Row 2: 个人排名 */}
      {data.ranks && (
        <div className="entity-stats-kpi-grid grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          <KpiCard label="全时段排名" value={rankLabel(data.ranks.lifetime)} />
          <KpiCard label="近 6 个月排名" value={rankLabel(data.ranks.last_6_months)} />
          <KpiCard label="近 4 周排名" value={rankLabel(data.ranks.last_4_weeks)} />
          <KpiCard label="当前区间排名" value={rankLabel(data.ranks.current_period)} />
        </div>
      )}

      {/* KPIs Row 3: Top 250 上榜 & 近期活跃 */}
      {(data.top250_counts || data.recent_50_count != null) && (
        <div className="entity-stats-kpi-grid grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {data.top250_counts && (
            <>
              <KpiCard label="全时段 Top 250 上榜" value={fmt(data.top250_counts.lifetime)} />
              <KpiCard label="近 6 个月 Top 250 上榜" value={fmt(data.top250_counts.last_6_months)} />
              <KpiCard label="近 4 周 Top 250 上榜" value={fmt(data.top250_counts.last_4_weeks)} />
            </>
          )}
          {data.recent_50_count != null && (
            <KpiCard label="最近 50 次播放中出现" value={`${data.recent_50_count} 次`} />
          )}
        </div>
      )}

      {isPhone ? (
        <GlassCard className="entity-stats-chart-card p-6">
          <div className="entity-stats-chart-heading">
            <h3 className="font-serif text-2xl font-semibold">
              {mobileTrendView === 'daily' ? '每日播放' : '累计播放'}
            </h3>
            <div className="entity-stats-chart-switcher" role="group" aria-label="播放趋势视图">
              <button type="button" className={mobileTrendView === 'daily' ? 'active' : undefined} aria-pressed={mobileTrendView === 'daily'} onClick={() => setMobileTrendView('daily')}>每日</button>
              <button type="button" className={mobileTrendView === 'cumulative' ? 'active' : undefined} aria-pressed={mobileTrendView === 'cumulative'} onClick={() => setMobileTrendView('cumulative')}>累计</button>
            </div>
          </div>
          <AnalysisTrendChart
            data={mobileTrendData}
            mode="line"
            showZoom
            height={220}
            detailWindowPosition="end"
          />
        </GlassCard>
      ) : (
        <>
          {/* 每日播放 — 全宽，含零值填充 */}
          <GlassCard className="entity-stats-chart-card p-6">
            <h3 className="mb-5 font-serif text-2xl font-semibold">每日播放</h3>
            <AnalysisTrendChart data={dailyChartData} mode="line" showZoom />
          </GlassCard>

          {/* 累计播放 — 全宽，含前值填充 */}
          {data.cumulative_trend.length > 0 && (
            <GlassCard className="entity-stats-chart-card p-6">
              <h3 className="mb-5 font-serif text-2xl font-semibold">累计播放</h3>
              <AnalysisTrendChart data={cumulativeChartData} mode="line" showZoom />
            </GlassCard>
          )}
        </>
      )}

      {/* 听歌时钟 + 分布图；手机端将三种分布收进同一张卡片。 */}
      <div className="entity-stats-distributions grid gap-6 xl:grid-cols-2">
        <GlassCard className="entity-stats-chart-card p-6">
          <h3 className="mb-3 font-serif text-2xl font-semibold">听歌时钟</h3>
          <ListeningClock
            data={data.hourly_distribution.map((item) => ({
              hour: item.hour,
              plays: item[distributionKey],
              hours: item.hours,
            }))}
            metricLabel={metricLabel}
            maxWidth={isPhone ? 216 : 280}
          />
        </GlassCard>

        {isPhone ? (
          <GlassCard className="entity-stats-chart-card p-6">
            <div className="entity-stats-chart-heading">
              <h3 className="font-serif text-xl font-semibold">
                {mobileDistributionView === 'weekday' ? '星期分布' : mobileDistributionView === 'month' ? '月度分布' : '年度分布'}
              </h3>
              <div className="entity-stats-chart-switcher" role="group" aria-label="播放分布视图">
                <button type="button" className={mobileDistributionView === 'weekday' ? 'active' : undefined} aria-pressed={mobileDistributionView === 'weekday'} onClick={() => setMobileDistributionView('weekday')}>星期</button>
                <button type="button" className={mobileDistributionView === 'month' ? 'active' : undefined} aria-pressed={mobileDistributionView === 'month'} onClick={() => setMobileDistributionView('month')}>月度</button>
                <button type="button" className={mobileDistributionView === 'year' ? 'active' : undefined} aria-pressed={mobileDistributionView === 'year'} onClick={() => setMobileDistributionView('year')}>年度</button>
              </div>
            </div>
            <AnalysisTrendChart data={mobileDistributionData} mode="bar" height={216} />
          </GlassCard>
        ) : (
          <>
            <GlassCard className="entity-stats-chart-card p-6">
              <h3 className="mb-5 font-serif text-xl font-semibold">星期分布</h3>
              <AnalysisTrendChart data={data.weekday_distribution.map((item) => ({ label: item.day, value: item[distributionKey] }))} mode="bar" />
            </GlassCard>
            <GlassCard className="entity-stats-chart-card p-6">
              <h3 className="mb-5 font-serif text-xl font-semibold">月度分布</h3>
              <AnalysisTrendChart data={data.month_distribution.map((item) => ({ label: `${item.month}月`, value: item[distributionKey] }))} mode="bar" />
            </GlassCard>
            <GlassCard className="entity-stats-chart-card p-6">
              <h3 className="mb-5 font-serif text-xl font-semibold">年度分布</h3>
              <AnalysisTrendChart data={data.year_distribution.map((item) => ({ label: String(item.year), value: item[distributionKey] }))} mode="bar" />
            </GlassCard>
          </>
        )}
      </div>

      {/* 专辑项目曲目排行：服务端分页，20 首以内保持单页。 */}
      {kind === 'album' && (
        <GlassCard className="entity-stats-ranking-card p-6">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-serif text-2xl font-semibold">播放排行</h3>
            {(albumRanking?.total ?? 0) > ALBUM_RANKING_PAGE_SIZE && (
              <div className="inline-flex items-center gap-1 text-[12px] text-muted-foreground">
                <button
                  type="button"
                  aria-label="上一页"
                  disabled={albumRankingPage <= 1}
                  onClick={() => setAlbumRankingPageState({ context: albumRankingContext, page: Math.max(1, albumRankingPage - 1) })}
                  className="rounded-lg border border-border px-2.5 py-1.5 disabled:opacity-30"
                >
                  上一页
                </button>
                <span className="min-w-14 text-center tabular-nums">
                  {albumRankingPage} / {Math.ceil((albumRanking?.total ?? 0) / ALBUM_RANKING_PAGE_SIZE)}
                </span>
                <button
                  type="button"
                  aria-label="下一页"
                  disabled={albumRankingPage >= Math.ceil((albumRanking?.total ?? 0) / ALBUM_RANKING_PAGE_SIZE)}
                  onClick={() => setAlbumRankingPageState({ context: albumRankingContext, page: albumRankingPage + 1 })}
                  className="rounded-lg border border-border px-2.5 py-1.5 disabled:opacity-30"
                >
                  下一页
                </button>
              </div>
            )}
          </div>
          {albumRankingPending ? (
            <Skeleton className="h-64 rounded-xl" />
          ) : albumRanking?.rows.length ? (
            <PersonalRankTable
              rows={albumRanking.rows}
              entity="track"
              metric={metric}
              pagination={{
                total: albumRanking.total,
                page: albumRankingPage,
                pageSize: ALBUM_RANKING_PAGE_SIZE,
                onPageChange: (page) => setAlbumRankingPageState({ context: albumRankingContext, page }),
              }}
            />
          ) : (
            <p className="py-10 text-center text-sm text-muted-foreground">当前区间暂无曲目播放记录。</p>
          )}
        </GlassCard>
      )}

      {/* 艺人个人排行：歌曲/专辑共享同一服务端分页工作区。 */}
      {kind === 'artist' && (
        <GlassCard className="entity-stats-ranking-card p-6">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-serif text-2xl font-semibold">播放排行</h3>
            <div className="flex flex-wrap items-center justify-end gap-2">
              <div className="inline-flex rounded-full border border-border p-1" aria-label="排行类型">
                {(['track', 'album'] as const).map((value) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={artistRankingKind === value}
                    onClick={() => setArtistRankingKind(value)}
                    className={`rounded-full px-3 py-1.5 text-[12px] font-semibold transition-colors ${artistRankingKind === value ? 'bg-accent-foreground text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}`}
                  >
                    {value === 'track' ? '歌曲' : '专辑'}
                  </button>
                ))}
              </div>
              <div className="inline-flex items-center gap-1 text-[12px] text-muted-foreground">
                <button
                  type="button"
                  aria-label="上一页"
                  disabled={artistRankingPage <= 1}
                  onClick={() => setArtistRankingPageState({ ...artistRankingPages, [artistRankingKind]: Math.max(1, artistRankingPage - 1) })}
                  className="rounded-lg border border-border px-2.5 py-1.5 disabled:opacity-30"
                >
                  上一页
                </button>
                <span className="min-w-14 text-center tabular-nums">
                  {artistRankingPage} / {Math.max(1, Math.ceil((artistRanking?.total ?? 0) / ARTIST_RANKING_PAGE_SIZE))}
                </span>
                <button
                  type="button"
                  aria-label="下一页"
                  disabled={artistRankingPage >= Math.max(1, Math.ceil((artistRanking?.total ?? 0) / ARTIST_RANKING_PAGE_SIZE))}
                  onClick={() => setArtistRankingPageState({ ...artistRankingPages, [artistRankingKind]: artistRankingPage + 1 })}
                  className="rounded-lg border border-border px-2.5 py-1.5 disabled:opacity-30"
                >
                  下一页
                </button>
              </div>
            </div>
          </div>
          {artistRankingPending ? (
            <Skeleton className="h-64 rounded-xl" />
          ) : artistRanking?.rows.length ? (
            <PersonalRankTable
              rows={artistRanking.rows}
              entity={artistRankingKind}
              metric={metric}
              pagination={{
                total: artistRanking.total,
                page: artistRankingPage,
                pageSize: ARTIST_RANKING_PAGE_SIZE,
                onPageChange: (page) => setArtistRankingPageState({ ...artistRankingPages, [artistRankingKind]: page }),
              }}
            />
          ) : (
            <p className="py-10 text-center text-sm text-muted-foreground">
              当前区间暂无{artistRankingKind === 'track' ? '歌曲' : '专辑'}播放记录。
            </p>
          )}
        </GlassCard>
      )}

      {/* 最近播放记录 — 全宽 */}
      <GlassCard className="entity-stats-recent-card p-6">
        <h3 className="mb-5 font-serif text-2xl font-semibold">最近播放记录</h3>
        <RecentPlaysSection
          kind={kind}
          entityId={kind === 'track' ? String(trackId) : (albumName ?? artistName ?? '')}
          artistName={artistName}
          filters={filters}
          apiParams={apiParams}
          mobile={isPhone}
          fetchPage={async (page, limit, search, date) => {
            if (kind === 'track' && trackId != null)
              return analysisApi.entityPlays('track', String(trackId), filters, { ...apiParams, limit, offset: (page - 1) * limit, search, date })
            if (kind === 'album' && albumName)
              return analysisApi.entityPlays('album', albumName, filters, { ...apiParams, limit, offset: (page - 1) * limit, search, date, merge_level: resolvedMergeLevel }, artistName)
            if (kind === 'artist' && artistName)
              return analysisApi.entityPlays('artist', artistName, filters, { ...apiParams, limit, offset: (page - 1) * limit, search, date })
            return { total: 0, limit, offset: 0, rows: [] }
          }}
          fetchPlayDates={async () => {
            if (kind === 'track' && trackId != null)
              return analysisApi.entityPlayDates('track', String(trackId), filters, apiParams)
            if (kind === 'album' && albumName)
              return analysisApi.entityPlayDates('album', albumName, filters, { ...apiParams, merge_level: resolvedMergeLevel }, artistName)
            if (kind === 'artist' && artistName)
              return analysisApi.entityPlayDates('artist', artistName, filters, apiParams)
            return []
          }}
        />
      </GlassCard>
    </div>
  )
}
