import { AnalysisTrendChart } from '@/components/charts/AnalysisCharts'
import { ListeningClock } from '@/components/charts/ListeningClock'
import { MetricToggle, useAnalysisQueryState } from '@/components/shared/AnalysisControls'
import { GlassCard } from '@/components/shared/GlassCard'
import { KpiCard } from '@/components/shared/KpiCard'
import { RecentPlaysSection } from '@/components/shared/RecentPlaysSection'
import { Skeleton } from '@/components/ui/skeleton'
import { analysisApi, useAnalysisFilters, useApiData } from '@/hooks/useAnalysis'
import { MobileAnalysisStats } from '@/features/mobile/analysis/MobileAnalysisStats'
import { MobileStatePanel } from '@/components/mobile'
import { useViewportMode } from '@/hooks/useViewportMode'

function fmt(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n)
}

function fmtHours(n: number): string {
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 0 }).format(n)}h`
}

export function AnalysisStatsPage() {
  const isPhone = useViewportMode() === 'phone'
  const { filters, loading: filtersLoading } = useAnalysisFilters()
  const { metric, setQuery, apiParams } = useAnalysisQueryState()
  const { data, loading } = useApiData(() => analysisApi.stats(filters, apiParams), [filters, apiParams], !filtersLoading)

  if (loading || !data) return isPhone ? <MobileStatePanel variant="loading" /> : <Skeleton className="h-[640px] rounded-[16px]" />

  const metricKey = metric === 'plays' ? 'plays' : 'hours'
  const metricLabel = metric === 'plays' ? '次' : '小时'

  if (isPhone) {
    return (
      <MobileAnalysisStats
        data={data}
        metric={metric}
        onMetricChange={(next) => setQuery({ metric: next })}
        filters={filters}
        apiParams={apiParams}
        fetchPage={(page, limit, search, date) =>
          analysisApi.plays(filters, { ...apiParams, limit, offset: (page - 1) * limit, search, date })
        }
        fetchPlayDates={() => analysisApi.playDates(filters, apiParams)}
      />
    )
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-2 font-sans text-[11px] font-bold uppercase tracking-[1.5px] text-accent-foreground">Playback Stats</p>
          <h2 className="font-serif text-[34px] font-bold leading-tight">播放统计</h2>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <MetricToggle metric={metric} onChange={(next) => setQuery({ metric: next })} />
        </div>
      </div>

      {/* KPIs: 2 rows × 4 cols */}
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="播放次数" value={fmt(data.summary.total_plays)} />
        <KpiCard label="播放时间" value={fmtHours(data.summary.total_hours)} />
        <KpiCard label="日均播放" value={fmt(Math.round(data.daily_metrics.avg_daily_plays))} />
        <KpiCard label="日均时长" value={fmtHours(data.daily_metrics.avg_daily_hours)} />
        <KpiCard label="独特歌曲" value={fmt(data.summary.unique_tracks)} />
        <KpiCard label="独特专辑" value={fmt(data.summary.unique_albums)} />
        <KpiCard label="独特艺人" value={fmt(data.summary.unique_artists)} />
        <KpiCard label="活跃天数" value={fmt(data.summary.active_days)} />
      </div>

      {/* 每日播放 + 累计播放 整页宽度 */}
      <GlassCard className="p-6">
        <h3 className="mb-5 font-serif text-2xl font-semibold">每日播放</h3>
        <AnalysisTrendChart
          data={data.daily_trend.map((item) => ({ label: item.date.slice(2), value: item[metricKey] }))}
          mode="line"
        />
      </GlassCard>
      <GlassCard className="p-6">
        <h3 className="mb-5 font-serif text-2xl font-semibold">累计播放</h3>
        <AnalysisTrendChart
          data={data.cumulative_trend.map((item) => ({ label: item.date.slice(2), value: metric === 'plays' ? item.cumulative_plays : item.cumulative_hours }))}
          mode="line"
        />
      </GlassCard>

      {/* 听歌时钟 + 三个分布图 2x2 */}
      <div className="grid gap-6 xl:grid-cols-2">
        <GlassCard className="p-6">
          <h3 className="mb-3 font-serif text-2xl font-semibold">听歌时钟</h3>
          <ListeningClock
            data={data.hourly_distribution.map((item) => ({
              hour: item.hour,
              plays: item[metricKey],
              hours: item.hours,
            }))}
            metricLabel={metricLabel}
          />
        </GlassCard>

        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-xl font-semibold">星期分布</h3>
          <AnalysisTrendChart
            data={data.weekday_distribution.map((item) => ({ label: item.day, value: item[metricKey] }))}
            mode="bar"
          />
        </GlassCard>

        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-xl font-semibold">月度分布</h3>
          <AnalysisTrendChart
            data={data.month_distribution.map((item) => ({ label: `${item.month}月`, value: item[metricKey] }))}
            mode="bar"
          />
        </GlassCard>

        <GlassCard className="p-6">
          <h3 className="mb-5 font-serif text-xl font-semibold">年度分布</h3>
          <AnalysisTrendChart
            data={data.year_distribution.map((item) => ({ label: String(item.year), value: item[metricKey] }))}
            mode="bar"
          />
        </GlassCard>
      </div>

      <GlassCard className="p-6">
        <h3 className="mb-5 font-serif text-2xl font-semibold">最近播放记录</h3>
        <RecentPlaysSection
          kind="global"
          filters={filters}
          apiParams={apiParams}
          fetchPage={async (page, limit, search, date) =>
            analysisApi.plays(filters, { ...apiParams, limit, offset: (page - 1) * limit, search, date })
          }
          fetchPlayDates={async () =>
            analysisApi.playDates(filters, apiParams)
          }
        />
      </GlassCard>
    </div>
  )
}
