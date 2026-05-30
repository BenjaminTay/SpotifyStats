import { AnalysisTrendChart, HorizontalBarChart } from '@/components/charts/AnalysisCharts'
import { MetricToggle, useAnalysisQueryState } from '@/components/shared/AnalysisControls'
import { AnalysisTimeRangeSelector } from '@/components/shared/AnalysisTimeRangeSelector'
import { GlassCard } from '@/components/shared/GlassCard'
import { KpiCard } from '@/components/shared/KpiCard'
import { PersonalRankTable, RecentPlaysTable } from '@/components/shared/StatsTables'
import { Skeleton } from '@/components/ui/skeleton'
import { analysisApi, useAnalysisFilters, useApiData } from '@/hooks/useAnalysis'
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
  const { data, loading } = useApiData<EntityStatsResponse>(() => {
    if (kind === 'track' && trackId != null) return analysisApi.trackStats(filters, trackId, apiParams)
    if (kind === 'album' && albumName) return analysisApi.albumStats(filters, albumName, artistName, apiParams)
    if (kind === 'artist' && artistName) return analysisApi.artistStats(filters, artistName, apiParams)
    return Promise.resolve({ found: false } as EntityStatsResponse)
  }, [filters, apiParams, kind, trackId, albumName, artistName], !filtersLoading)

  if (loading || !data) return <Skeleton className="h-[560px] rounded-[16px]" />
  if (!data.found) return <GlassCard className="p-8 text-muted-foreground">暂无个人播放统计。</GlassCard>

  const metricKey: AnalysisMetric = metric
  const distributionKey = metricKey === 'plays' ? 'plays' : 'hours'

  return (
    <div className="space-y-7">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <AnalysisTimeRangeSelector period={period} periodValue={periodValue} startDate={startDate} endDate={endDate} onChange={setQuery} />
        <MetricToggle metric={metric} onChange={(next) => setQuery({ metric: next })} />
      </div>

      <div className="grid gap-6 border-b border-border pb-7 md:grid-cols-4 xl:grid-cols-6">
        <KpiCard label="播放次数" value={fmt(data.summary.total_plays)} />
        <KpiCard label="播放时间" value={hours(data.summary.total_hours)} />
        <KpiCard label="首次播放" value={dateShort(data.first_played)} />
        <KpiCard label="最近播放" value={dateShort(data.last_played)} />
        <KpiCard label="Lifetime 排名" value={rankLabel(data.ranks?.lifetime)} />
        <KpiCard label="最近 4 周" value={rankLabel(data.ranks?.last_4_weeks)} />
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <GlassCard className="p-5"><KpiCard label="日均播放" value={fmt(data.daily_metrics.avg_daily_plays)} /></GlassCard>
        <GlassCard className="p-5"><KpiCard label="日均时长" value={hours(data.daily_metrics.avg_daily_hours)} /></GlassCard>
        <GlassCard className="p-5"><KpiCard label="最近 6 月排名" value={rankLabel(data.ranks?.last_6_months)} /></GlassCard>
        <GlassCard className="p-5"><KpiCard label="当前区间排名" value={rankLabel(data.ranks?.current_period)} /></GlassCard>
      </div>

      {(data.top250_counts || data.recent_50_count != null) && (
        <div className="grid gap-4 md:grid-cols-4">
          {data.top250_counts && (
            <>
              <GlassCard className="p-5"><KpiCard label="Alltime Top 250" value={fmt(data.top250_counts.lifetime)} /></GlassCard>
              <GlassCard className="p-5"><KpiCard label="最近 6 月 Top 250" value={fmt(data.top250_counts.last_6_months)} /></GlassCard>
              <GlassCard className="p-5"><KpiCard label="最近 4 周 Top 250" value={fmt(data.top250_counts.last_4_weeks)} /></GlassCard>
            </>
          )}
          {data.recent_50_count != null && <GlassCard className="p-5"><KpiCard label="最近 50 次出现" value={fmt(data.recent_50_count)} /></GlassCard>}
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-2xl font-semibold">每日播放</h3>
          <AnalysisTrendChart data={data.daily_trend.map((item) => ({ label: item.date.slice(5), value: item[distributionKey] }))} mode="line" />
        </GlassCard>
        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-2xl font-semibold">听歌时钟</h3>
          <HorizontalBarChart data={data.hourly_distribution.map((item) => ({ name: `${item.hour}:00`, value: item[distributionKey] }))} />
        </GlassCard>
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-xl font-semibold">周几分布</h3>
          <HorizontalBarChart data={data.weekday_distribution.map((item) => ({ name: item.day, value: item[distributionKey] }))} />
        </GlassCard>
        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-xl font-semibold">月份分布</h3>
          <HorizontalBarChart data={data.month_distribution.map((item) => ({ name: `${item.month}月`, value: item[distributionKey] }))} />
        </GlassCard>
        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-xl font-semibold">年份分布</h3>
          <HorizontalBarChart data={data.year_distribution.map((item) => ({ name: String(item.year), value: item[distributionKey] }))} />
        </GlassCard>
      </div>

      {data.track_breakdown && data.track_breakdown.length > 0 && (
        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-2xl font-semibold">专辑内曲目</h3>
          <PersonalRankTable rows={data.track_breakdown} entity="track" metric={metric} />
        </GlassCard>
      )}

      {data.top_tracks && data.top_tracks.length > 0 && (
        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-2xl font-semibold">个人 Top 歌曲</h3>
          <PersonalRankTable rows={data.top_tracks} entity="track" metric={metric} />
        </GlassCard>
      )}

      {data.top_albums && data.top_albums.length > 0 && (
        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-2xl font-semibold">个人 Top 专辑</h3>
          <PersonalRankTable rows={data.top_albums} entity="album" metric={metric} />
        </GlassCard>
      )}

      <GlassCard className="p-6">
        <h3 className="mb-5 font-serif text-2xl font-semibold">最近播放记录</h3>
        <RecentPlaysTable rows={data.recent_plays} />
      </GlassCard>
    </div>
  )
}
