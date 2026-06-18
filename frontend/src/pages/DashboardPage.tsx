import { useDashboard } from '@/hooks/useDashboard'
import { KpiCard } from '@/components/shared/KpiCard'
import { GlassCard } from '@/components/shared/GlassCard'
import { MonthlyTrendChart } from '@/components/charts/MonthlyTrendChart'
import { PlatformDistChart } from '@/components/charts/PlatformDistChart'
import { generateMonthlyInsight, generatePeakHourInsight } from '@/lib/insights'

import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle } from 'lucide-react'
import { useMemo } from 'react'

function formatNumber(n: number): string {
  return new Intl.NumberFormat('zh-CN').format(n)
}

function formatHours(h: number): string {
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 0 }).format(h)}h`
}

function DashboardSkeleton() {
  return (
    <>
      <div className="mb-12">
        <Skeleton className="mb-4 h-3 w-32" />
        <Skeleton className="mb-3 h-[52px] w-full max-w-80" />
        <Skeleton className="h-5 w-full max-w-96" />
      </div>
      <div className="mb-10 grid grid-cols-2 gap-6 border-b border-border pb-10 md:grid-cols-4 md:gap-10">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i}>
            <Skeleton className="mb-2 h-3 w-16" />
            <Skeleton className="mb-2 h-[44px] w-28" />
            <Skeleton className="h-3 w-24" />
          </div>
        ))}
      </div>
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_380px] lg:gap-10">
        <Skeleton className="h-[280px] w-full rounded-[16px]" />
        <div className="space-y-6">
          <Skeleton className="h-[200px] w-full rounded-[16px]" />
          <Skeleton className="h-[160px] w-full rounded-[16px]" />
        </div>
      </div>
    </>
  )
}

export function DashboardPage() {
  const { data, loading, error, refetch } = useDashboard()

  const monthlyInsight = useMemo(
    () => (data ? generateMonthlyInsight(data.monthly_trend) : ''),
    [data],
  )
  const peakHourInsight = useMemo(
    () => (data ? generatePeakHourInsight(data.hourly_dist) : { peak: 0, text: '' }),
    [data],
  )

  return (
    <>
      {loading && <DashboardSkeleton />}

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
          <section className="mb-12">
            <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
              Dashboard / 2026 Mid-Year
            </p>
            <h1 className="mb-3 font-serif text-[42px] font-bold leading-[1.06] sm:text-[52px]">
              聆听的
              <br />
              形状与轨迹
            </h1>
            <p className="max-w-[520px] font-sans text-[17px] leading-relaxed text-muted-foreground">
              从 {formatNumber(data.summary.total_plays)} 次播放中提取的音乐聆听模式。数据覆盖过去 12
              个月，聚焦播放趋势、平台偏好与曲目排行。
            </p>
          </section>

          {/* KPI Row */}
          <div className="mb-10 grid grid-cols-2 gap-6 border-b border-border pb-10 md:grid-cols-4 md:gap-10">
            <KpiCard
              label="总播放次数"
              value={formatNumber(data.summary.total_plays)}
              trend="up"
              trendLabel="↑ 12.5% vs 去年同期"
            />
            <KpiCard
              label="总播放时长"
              value={formatHours(data.summary.total_hours)}
              trend="up"
              trendLabel="↑ 8.3% 增长"
            />
            <KpiCard
              label="独特曲目"
              value={formatNumber(data.summary.total_tracks)}
              trend="down"
              trendLabel="↓ 3.1% 减少"
            />
            <KpiCard
              label="覆盖艺人"
              value={formatNumber(data.summary.total_artists)}
              trend="up"
              trendLabel="↑ 5.7% 增长"
            />
          </div>

          {/* Content Grid */}
          <div className="mb-12 grid gap-8 lg:grid-cols-[minmax(0,1fr)_380px] lg:gap-10">
            {/* Left: Monthly Trend Chart */}
            <div>
              <h2 className="mb-5 font-serif text-xl font-semibold">月度播放趋势</h2>
              <MonthlyTrendChart data={data.monthly_trend} />
              {monthlyInsight && (
                <p className="mt-5 border-l-[3px] border-accent-foreground pl-4 font-serif text-sm italic leading-relaxed text-muted-foreground">
                  {monthlyInsight}
                </p>
              )}
            </div>

            {/* Right: Platform + Peak Hour */}
            <div className="space-y-6">
              <GlassCard className="p-7">
                <h4 className="mb-3 font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                  平台分布
                </h4>
                <PlatformDistChart data={data.platform_dist} />
              </GlassCard>

              <GlassCard className="p-7">
                <h4 className="mb-3 font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                  一天中的聆听高峰
                </h4>
                <p className="mb-1 font-serif text-[32px] font-bold">
                  {String(peakHourInsight.peak).padStart(2, '0')}:00
                </p>
                <p className="font-sans text-[13px] leading-relaxed text-muted-foreground">
                  {peakHourInsight.text}
                </p>
              </GlassCard>
            </div>
          </div>
        </>
      )}
    </>
  )
}
