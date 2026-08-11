import { useRef, useState, type ReactNode } from 'react'

import { AnalysisTrendChart } from '@/components/charts/AnalysisCharts'
import { ListeningClock } from '@/components/charts/ListeningClock'
import { MobileChartCard, MobileFullscreenChart } from '@/components/mobile'
import { RecentPlaysSection } from '@/components/shared/RecentPlaysSection'
import type {
  AnalysisFilters,
  AnalysisMetric,
  AnalysisPeriod,
  AnalysisStatsResponse,
  EntityPlaysResponse,
} from '@/types/analysis'

function formatNumber(value: number): string {
  return new Intl.NumberFormat('zh-CN').format(value)
}

function formatHours(value: number): string {
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(value)}h`
}

interface MobileAnalysisStatsProps {
  data: AnalysisStatsResponse
  metric: AnalysisMetric
  filters: AnalysisFilters
  apiParams: { period: AnalysisPeriod; start_date?: string; end_date?: string }
  fetchPage: (page: number, limit: number, search?: string, date?: string) => Promise<EntityPlaysResponse>
  fetchPlayDates: () => Promise<Array<{ date: string; count: number }>>
  timeControl?: ReactNode
}

type TrendView = 'daily' | 'cumulative'
type DistributionView = 'weekday' | 'month' | 'year'
type FullscreenChart = 'trend' | 'clock' | 'distribution'

export function MobileAnalysisStats({
  data,
  metric,
  filters,
  apiParams,
  fetchPage,
  fetchPlayDates,
  timeControl,
}: MobileAnalysisStatsProps) {
  const [trendView, setTrendView] = useState<TrendView>('daily')
  const [distributionView, setDistributionView] = useState<DistributionView>('weekday')
  const [fullscreenChart, setFullscreenChart] = useState<FullscreenChart | null>(null)
  const trendFullscreenRef = useRef<HTMLButtonElement>(null)
  const clockFullscreenRef = useRef<HTMLButtonElement>(null)
  const distributionFullscreenRef = useRef<HTMLButtonElement>(null)
  const metricKey = metric === 'plays' ? 'plays' : 'hours'
  const metricLabel = metric === 'plays' ? '次' : '小时'
  const trendData = trendView === 'daily'
    ? data.daily_trend.map((item) => ({ label: item.date.slice(2), value: item[metricKey] }))
    : data.cumulative_trend.map((item) => ({
        label: item.date.slice(2),
        value: metric === 'plays' ? item.cumulative_plays : item.cumulative_hours,
      }))
  const distributionData = distributionView === 'weekday'
    ? data.weekday_distribution.map((item) => ({ label: item.day, value: item[metricKey] }))
    : distributionView === 'month'
      ? data.month_distribution.map((item) => ({ label: `${item.month}月`, value: item[metricKey] }))
      : data.year_distribution.map((item) => ({ label: String(item.year), value: item[metricKey] }))
  const hourlyData = data.hourly_distribution.map((item) => ({
    hour: item.hour,
    plays: item[metricKey],
    hours: item.hours,
  }))
  const trendTitle = trendView === 'daily' ? '每日播放' : '累计播放'
  const distributionTitle = '时间分布'

  const fullscreenContent = fullscreenChart === 'trend'
    ? <AnalysisTrendChart data={trendData} mode="line" />
    : fullscreenChart === 'clock'
      ? <ListeningClock data={hourlyData} metricLabel={metricLabel} />
      : fullscreenChart === 'distribution'
        ? <AnalysisTrendChart data={distributionData} mode="bar" />
        : null
  const fullscreenTitle = fullscreenChart === 'trend'
    ? trendTitle
    : fullscreenChart === 'clock'
      ? '听歌时钟'
      : distributionTitle
  const fullscreenTriggerRef = fullscreenChart === 'trend'
    ? trendFullscreenRef
    : fullscreenChart === 'clock'
      ? clockFullscreenRef
      : distributionFullscreenRef

  return (
    <div className="mobile-m3-page" data-mobile-page="analysis-stats">
      {timeControl && <div className="mobile-analysis-floating-time-control">{timeControl}</div>}

      <section className="mobile-kpi-grid mobile-analysis-kpi-grid" aria-label="播放统计核心数据">
        <article className="mobile-kpi-tile"><p>播放次数</p><strong>{formatNumber(data.summary.total_plays)}</strong></article>
        <article className="mobile-kpi-tile"><p>播放时长</p><strong>{formatHours(data.summary.total_hours)}</strong></article>
        <article className="mobile-kpi-tile"><p>日均播放</p><strong>{formatNumber(Math.round(data.daily_metrics.avg_daily_plays))}</strong></article>
        <article className="mobile-kpi-tile"><p>日均时长</p><strong>{formatHours(data.daily_metrics.avg_daily_hours)}</strong></article>
        <article className="mobile-kpi-tile"><p>已听歌曲</p><strong>{formatNumber(data.summary.unique_tracks)}</strong></article>
        <article className="mobile-kpi-tile"><p>已听专辑</p><strong>{formatNumber(data.summary.unique_albums)}</strong></article>
        <article className="mobile-kpi-tile"><p>已听艺人</p><strong>{formatNumber(data.summary.unique_artists)}</strong></article>
        <article className="mobile-kpi-tile"><p>活跃天数</p><strong>{formatNumber(data.summary.active_days)}</strong></article>
      </section>

      <MobileChartCard
        eyebrow="Daily / Accumulated"
        title={trendTitle}
        description="两个视图复用同一份统计响应"
        chart={<AnalysisTrendChart data={trendData} mode="line" />}
        interactionHint="点击数据点查看日期与数值"
        series={[
          { id: 'daily', label: '每日', active: trendView === 'daily' },
          { id: 'cumulative', label: '累计', active: trendView === 'cumulative' },
        ]}
        onToggleSeries={(id) => setTrendView(id as TrendView)}
        onFullscreen={() => setFullscreenChart('trend')}
        fullscreenTriggerRef={trendFullscreenRef}
      />

      <MobileChartCard
        eyebrow="Listening / Clock"
        title="听歌时钟"
        description="一天 24 小时中的聆听分布"
        chart={(
          <ListeningClock
            data={hourlyData}
            metricLabel={metricLabel}
          />
        )}
        interactionHint="点击时钟区段查看对应时段"
        onFullscreen={() => setFullscreenChart('clock')}
        fullscreenTriggerRef={clockFullscreenRef}
      />

      <MobileChartCard
        eyebrow="Calendar / Pattern"
        title={distributionTitle}
        chart={<AnalysisTrendChart data={distributionData} mode="bar" />}
        series={[
          { id: 'weekday', label: '星期', active: distributionView === 'weekday' },
          { id: 'month', label: '月份', active: distributionView === 'month' },
          { id: 'year', label: '年份', active: distributionView === 'year' },
        ]}
        onToggleSeries={(id) => setDistributionView(id as DistributionView)}
        onFullscreen={() => setFullscreenChart('distribution')}
        fullscreenTriggerRef={distributionFullscreenRef}
      />

      <MobileFullscreenChart
        open={fullscreenChart !== null}
        onOpenChange={(open) => { if (!open) setFullscreenChart(null) }}
        title={fullscreenTitle}
        description={`${data.period.label} · ${metric === 'plays' ? '播放次数' : '播放时长'}`}
        triggerRef={fullscreenTriggerRef}
      >
        <div className="mobile-fullscreen-chart-content">{fullscreenContent}</div>
      </MobileFullscreenChart>

      <section className="mobile-section-card">
        <header className="mobile-section-card-header"><p>Recent / Plays</p><h2>最近播放记录</h2></header>
        <RecentPlaysSection
          mobile
          kind="global"
          filters={filters}
          apiParams={apiParams}
          fetchPage={fetchPage}
          fetchPlayDates={fetchPlayDates}
        />
      </section>
    </div>
  )
}
