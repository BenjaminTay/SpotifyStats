import { useMemo } from 'react'
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
import type { AnalysisMetric, EntityStatsResponse } from '@/types/analysis'

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
}: {
  kind: 'track' | 'album' | 'artist'
  trackId?: number | string
  albumName?: string
  artistName?: string
}) {
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const { period, metric, periodValue, startDate, endDate, setQuery, apiParams } = useAnalysisQueryState()
  const entityId = (trackId ?? albumName ?? artistName) != null ? String(trackId ?? albumName ?? artistName) : ''
  const { data, isPending, error } = useQuery({
    queryKey: queryKeys.music.entityStats(kind, entityId, { ...filters, ...apiParams }),
    queryFn: () => {
      if (kind === 'track' && trackId != null) {
        return api.get<EntityStatsResponse>(`/music/tracks/${trackId}/stats`, { ...filters, ...apiParams })
      }
      if (kind === 'album' && albumName) {
        return api.get<EntityStatsResponse>(
          `/music/albums/${encodeURIComponent(albumName)}/stats`,
          { ...filters, ...apiParams, ...(artistName ? { artist: artistName } : {}) },
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

  const metricKey: AnalysisMetric = metric
  const distributionKey = metricKey === 'plays' ? 'plays' : 'hours'

  // Pad daily trend with zero-fill for dates with no plays, from first play to today
  const paddedDaily = useMemo(() => {
    if (!data || data.daily_trend.length === 0) return []
    const index = new Map(data.daily_trend.map((d) => [d.date, d]))
    const first = new Date(data.daily_trend[0].date + 'T00:00:00')
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const result: typeof data.daily_trend = []
    const cursor = new Date(first)
    while (cursor <= today) {
      const dateStr = cursor.toISOString().slice(0, 10)
      result.push(index.get(dateStr) ?? { date: dateStr, plays: 0, hours: 0 })
      cursor.setDate(cursor.getDate() + 1)
    }
    return result
  }, [data?.daily_trend])

  // Pad cumulative trend: carry forward last known value for missing dates
  const paddedCumulative = useMemo(() => {
    if (!data || data.cumulative_trend.length === 0) return []
    const index = new Map(data.cumulative_trend.map((d) => [d.date, d]))
    const first = new Date(data.cumulative_trend[0].date + 'T00:00:00')
    const today = new Date()
    today.setHours(0, 0, 0, 0)
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
  }, [data?.cumulative_trend])

  if (queryError) return <GlassCard className="p-8 text-center text-destructive">加载失败：{queryError}</GlassCard>
  if (isPending || !data) return <Skeleton className="h-[560px] rounded-[16px]" />
  if (!data.found) return <GlassCard className="p-8 text-muted-foreground">暂无个人播放统计。</GlassCard>

  const metricLabel = metric === 'plays' ? '次' : '小时'

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <AnalysisTimeRangeSelector period={period} periodValue={periodValue} startDate={startDate} endDate={endDate} onChange={setQuery} quickFirst />
        <MetricToggle metric={metric} onChange={(next) => setQuery({ metric: next })} />
      </div>

      {/* KPIs Row 1: 播放概览 — 6 cards */}
      <div className="grid gap-5 md:grid-cols-3 xl:grid-cols-6">
        <KpiCard label="总播放次数" value={fmt(data.summary.total_plays)} />
        <KpiCard label="总播放时长" value={hours(data.summary.total_hours)} />
        <KpiCard label="日均播放" value={fmt(Math.round(data.daily_metrics.avg_daily_plays))} />
        <KpiCard label="日均时长" value={hours(data.daily_metrics.avg_daily_hours)} />
        <KpiCard label="首次播放" value={dateShort(data.first_played)} />
        <KpiCard label="最近播放" value={dateShort(data.last_played)} />
      </div>

      {/* KPIs Row 2: 个人排名 */}
      {data.ranks && (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          <KpiCard label="全时段排名" value={rankLabel(data.ranks.lifetime)} />
          <KpiCard label="近 6 个月排名" value={rankLabel(data.ranks.last_6_months)} />
          <KpiCard label="近 4 周排名" value={rankLabel(data.ranks.last_4_weeks)} />
          <KpiCard label="当前区间排名" value={rankLabel(data.ranks.current_period)} />
        </div>
      )}

      {/* KPIs Row 3: Top 250 上榜 & 近期活跃 */}
      {(data.top250_counts || data.recent_50_count != null) && (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
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

      {/* 每日播放 — 全宽，含零值填充 */}
      <GlassCard className="p-6">
        <h3 className="mb-5 font-serif text-2xl font-semibold">每日播放</h3>
        <AnalysisTrendChart
          data={paddedDaily.map((item) => ({ label: item.date.slice(2), value: item[distributionKey] }))}
          mode="line"
        />
      </GlassCard>

      {/* 累计播放 — 全宽，含前值填充 */}
      {data.cumulative_trend.length > 0 && (
        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-2xl font-semibold">累计播放</h3>
          <AnalysisTrendChart
            data={paddedCumulative.map((item) => ({
              label: item.date.slice(2),
              value: metric === 'plays' ? item.cumulative_plays : item.cumulative_hours,
            }))}
            mode="line"
          />
        </GlassCard>
      )}

      {/* 听歌时钟 + 三个分布图 — 2×2 */}
      <div className="grid gap-6 xl:grid-cols-2">
        <GlassCard className="p-6">
          <h3 className="mb-3 font-serif text-2xl font-semibold">听歌时钟</h3>
          <ListeningClock
            data={data.hourly_distribution.map((item) => ({
              hour: item.hour,
              plays: item[distributionKey],
              hours: item.hours,
            }))}
            metricLabel={metricLabel}
          />
        </GlassCard>

        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-xl font-semibold">星期分布</h3>
          <AnalysisTrendChart
            data={data.weekday_distribution.map((item) => ({ label: item.day, value: item[distributionKey] }))}
            mode="bar"
          />
        </GlassCard>

        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-xl font-semibold">月度分布</h3>
          <AnalysisTrendChart
            data={data.month_distribution.map((item) => ({ label: `${item.month}月`, value: item[distributionKey] }))}
            mode="bar"
          />
        </GlassCard>

        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-xl font-semibold">年度分布</h3>
          <AnalysisTrendChart
            data={data.year_distribution.map((item) => ({ label: String(item.year), value: item[distributionKey] }))}
            mode="bar"
          />
        </GlassCard>
      </div>

      {/* 专辑内曲目 (仅专辑详情) */}
      {data.track_breakdown && data.track_breakdown.length > 0 && (
        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-2xl font-semibold">专辑内曲目排行</h3>
          <PersonalRankTable rows={data.track_breakdown} entity="track" metric={metric} />
        </GlassCard>
      )}

      {/* 个人 Top 歌曲 */}
      {data.top_tracks && data.top_tracks.length > 0 && (
        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-2xl font-semibold">个人 Top 歌曲</h3>
          <PersonalRankTable rows={data.top_tracks} entity="track" metric={metric} />
        </GlassCard>
      )}

      {/* 个人 Top 专辑 */}
      {data.top_albums && data.top_albums.length > 0 && (
        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-2xl font-semibold">个人 Top 专辑</h3>
          <PersonalRankTable rows={data.top_albums} entity="album" metric={metric} />
        </GlassCard>
      )}

      {/* 最近播放记录 — 全宽 */}
      <GlassCard className="p-6">
        <h3 className="mb-5 font-serif text-2xl font-semibold">最近播放记录</h3>
        <RecentPlaysSection
          kind={kind}
          entityId={kind === 'track' ? String(trackId) : (albumName ?? artistName ?? '')}
          artistName={artistName}
          filters={filters}
          apiParams={apiParams}
          fetchPage={async (page, limit, search, date) => {
            if (kind === 'track' && trackId != null)
              return analysisApi.entityPlays('track', String(trackId), filters, { ...apiParams, limit, offset: (page - 1) * limit, search, date })
            if (kind === 'album' && albumName)
              return analysisApi.entityPlays('album', albumName, filters, { ...apiParams, limit, offset: (page - 1) * limit, search, date }, artistName)
            if (kind === 'artist' && artistName)
              return analysisApi.entityPlays('artist', artistName, filters, { ...apiParams, limit, offset: (page - 1) * limit, search, date })
            return { total: 0, limit, offset: 0, rows: [] }
          }}
          fetchPlayDates={async () => {
            if (kind === 'track' && trackId != null)
              return analysisApi.entityPlayDates('track', String(trackId), filters, apiParams)
            if (kind === 'album' && albumName)
              return analysisApi.entityPlayDates('album', albumName, filters, apiParams, artistName)
            if (kind === 'artist' && artistName)
              return analysisApi.entityPlayDates('artist', artistName, filters, apiParams)
            return []
          }}
        />
      </GlassCard>
    </div>
  )
}
