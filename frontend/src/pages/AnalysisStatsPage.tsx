import { AnalysisTrendChart, HorizontalBarChart } from '@/components/charts/AnalysisCharts'
import { AnalysisPeriodControl, MetricToggle, useAnalysisQueryState } from '@/components/shared/AnalysisControls'
import { GlassCard } from '@/components/shared/GlassCard'
import { KpiCard } from '@/components/shared/KpiCard'
import { RecentPlaysTable } from '@/components/shared/StatsTables'
import { Skeleton } from '@/components/ui/skeleton'
import { analysisApi, useAnalysisFilters, useApiData } from '@/hooks/useAnalysis'

function fmt(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n)
}

function hours(n: number): string {
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(n)}h`
}

export function AnalysisStatsPage() {
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const { period, metric, startDate, endDate, setQuery, apiParams } = useAnalysisQueryState()
  const { data, loading } = useApiData(() => analysisApi.stats(filters, apiParams), [filters, apiParams], !filtersLoading)

  if (loading || !data) return <Skeleton className="h-[640px] rounded-[16px]" />

  const metricKey = metric === 'plays' ? 'plays' : 'hours'

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-2 font-sans text-[11px] font-bold uppercase tracking-[1.5px] text-accent-foreground">Personal Stats</p>
          <h2 className="font-serif text-[34px] font-bold leading-tight">总体播放统计</h2>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <AnalysisPeriodControl period={period} startDate={startDate} endDate={endDate} onChange={setQuery} />
          <MetricToggle metric={metric} onChange={(next) => setQuery({ metric: next })} />
        </div>
      </div>

      <div className="grid gap-6 border-b border-border pb-8 md:grid-cols-3 xl:grid-cols-6">
        <KpiCard label="播放次数" value={fmt(data.summary.total_plays)} />
        <KpiCard label="播放时间" value={hours(data.summary.total_hours)} />
        <KpiCard label="独特歌曲" value={fmt(data.summary.unique_tracks)} />
        <KpiCard label="独特专辑" value={fmt(data.summary.unique_albums)} />
        <KpiCard label="独特艺人" value={fmt(data.summary.unique_artists)} />
        <KpiCard label="活跃天数" value={fmt(data.summary.active_days)} />
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <GlassCard className="p-5"><KpiCard label="日均播放" value={fmt(data.daily_metrics.avg_daily_plays)} /></GlassCard>
        <GlassCard className="p-5"><KpiCard label="日均时长" value={hours(data.daily_metrics.avg_daily_hours)} /></GlassCard>
        <GlassCard className="p-5"><KpiCard label="快进率" value={`${data.behavior_summary.forward_rate}%`} /></GlassCard>
        <GlassCard className="p-5"><KpiCard label="随机播放" value={`${data.behavior_summary.shuffle_rate}%`} /></GlassCard>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-2xl font-semibold">每日播放轨迹</h3>
          <AnalysisTrendChart
            data={data.daily_trend.map((item) => ({ label: item.date.slice(5), value: item[metricKey] }))}
            mode="line"
          />
        </GlassCard>
        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-2xl font-semibold">听歌时钟</h3>
          <HorizontalBarChart
            data={data.hourly_distribution.map((item) => ({ name: `${item.hour}:00`, value: item[metricKey] }))}
            valueName={metric === 'plays' ? '播放次数' : '播放时长'}
          />
        </GlassCard>
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-xl font-semibold">周几分布</h3>
          <HorizontalBarChart data={data.weekday_distribution.map((item) => ({ name: item.day, value: item[metricKey] }))} />
        </GlassCard>
        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-xl font-semibold">月份分布</h3>
          <HorizontalBarChart data={data.month_distribution.map((item) => ({ name: `${item.month}月`, value: item[metricKey] }))} />
        </GlassCard>
        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-xl font-semibold">年份分布</h3>
          <HorizontalBarChart data={data.year_distribution.map((item) => ({ name: String(item.year), value: item[metricKey] }))} />
        </GlassCard>
      </div>

      <GlassCard className="p-6">
        <h3 className="mb-5 font-serif text-2xl font-semibold">累计播放</h3>
        <AnalysisTrendChart
          data={data.cumulative_trend.map((item) => ({ label: item.date.slice(2), value: metric === 'plays' ? item.cumulative_plays : item.cumulative_hours }))}
          mode="line"
        />
      </GlassCard>

      <GlassCard className="p-6">
        <h3 className="mb-5 font-serif text-2xl font-semibold">最近播放记录</h3>
        <RecentPlaysTable rows={data.recent_plays} />
      </GlassCard>
    </div>
  )
}
