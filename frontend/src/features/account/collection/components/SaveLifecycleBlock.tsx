import { useMemo } from 'react'
import { LazyEChart } from '@/components/charts/LazyEChart'
import { GlassCard } from '@/components/shared/GlassCard'
import { cn } from '@/lib/utils'
import { displayName } from '@/lib/chinese'
import { buildChartBase } from '@/components/charts/EChartsTheme'
import { useTheme } from '@/hooks/useTheme'
import type { CollectionInsights, LifecycleExample, LifecycleTrendPoint, TopTrackTrend } from '@/types/account'

function FateBar({
  label,
  pct,
  color,
}: {
  label: string
  pct: number
  color: string
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-8 font-sans text-[11px] font-medium">{label}</span>
      <div className="h-3 flex-1 overflow-hidden rounded-full bg-muted">
        <div
          className={cn('h-full rounded-full transition-all', color)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-10 text-right font-sans text-[11px] tabular-nums text-muted-foreground">
        {pct.toFixed(0)}%
      </span>
    </div>
  )
}

const TREND_COLORS = ['#e11d48', '#d97706', '#0284c7']

function LifecycleTrendChart({
  trend,
  topTracks,
}: {
  trend: LifecycleTrendPoint[]
  topTracks?: TopTrackTrend[]
}) {
  const { isDark } = useTheme()
  const base = buildChartBase(isDark)

  const { xLabels, avgData, trackSeries } = useMemo(() => {
    const xLabels = Array.from({ length: 52 }, (_, i) => `W${i}`)
    const avgRaw: (number | null)[] = Array(52).fill(null)
    trend.forEach(p => { if (p.week >= 0 && p.week < 52) avgRaw[p.week] = p.avg_plays })

    const trackRaw: { name: string; data: (number | null)[]; color: string }[] = []
    if (topTracks) {
      for (let ti = 0; ti < topTracks.length; ti++) {
        const t = topTracks[ti]
        const data: (number | null)[] = Array(52).fill(null)
        t.data.forEach(pt => { if (pt.week >= 0 && pt.week < 52) data[pt.week] = pt.plays })
        trackRaw.push({
          name: (() => { const c = displayName(t.track_name); return c.length > 10 ? c.slice(0, 10) + '…' : c; })(),
          data,
          color: TREND_COLORS[ti],
        })
      }
    }

    function normalize(arr: (number | null)[]): (number | null)[] {
      const peak = Math.max(...arr.filter(v => v != null) as number[], 1)
      return arr.map(v => v != null ? +(v / peak * 100).toFixed(1) : null)
    }

    const avgData = normalize(avgRaw)
    const trackSeries = trackRaw.map(s => ({ ...s, data: normalize(s.data) }))

    return { xLabels, avgData, trackSeries }
  }, [trend, topTracks])

  const option = useMemo(() => ({
    ...base,
    grid: { ...base.grid, top: 8, bottom: 32, left: 8, right: 12 },
    xAxis: {
      ...base.xAxis,
      data: xLabels,
      axisLabel: { ...base.xAxis.axisLabel, interval: 13 },
    },
    yAxis: {
      ...base.yAxis,
      name: undefined,
      max: 100,
    },
    tooltip: { ...base.tooltip, trigger: 'axis' },
    legend: {
      show: true,
      bottom: 0,
      textStyle: { ...base.textStyle, fontSize: 10 },
      itemWidth: 14,
      itemHeight: 8,
    },
    series: [
      {
        name: '全部平均',
        type: 'line',
        data: avgData,
        smooth: true,
        symbol: 'none',
        connectNulls: true,
        lineStyle: { width: 2.5, type: 'dashed' },
      },
      ...trackSeries.map(s => ({
        name: s.name,
        type: 'line',
        data: s.data,
        smooth: true,
        symbol: 'none',
        connectNulls: true,
        lineStyle: { width: 2, color: s.color },
        itemStyle: { color: s.color },
      })),
    ],
  }), [base, xLabels, avgData, trackSeries])

  return (
    <GlassCard className="mt-6 p-5">
      <p className="mb-3 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">
        收藏后周均播放趋势（52 周）
      </p>
      <LazyEChart option={option} style={{ height: 280 }} fallbackHeight={260} notMerge />
    </GlassCard>
  )
}

export function SaveLifecycleBlock({
  insights,
}: {
  insights: CollectionInsights
}) {
  const { lifecycle } = insights

  const stages = [
    { key: 'honeymoon', data: lifecycle.honeymoon, color: 'bg-rose-500/70', label: '蜜月期最高播放曲目' },
    { key: 'cooling', data: lifecycle.cooling, color: 'bg-amber-500/70', label: '冷却期最高播放曲目' },
    { key: 'settling', data: lifecycle.settling, color: 'bg-sky-500/70', label: '沉淀期最高播放曲目' },
  ] as const

  const stageExamples: Record<string, LifecycleExample[]> = {
    honeymoon: lifecycle.honeymoon_examples || [],
    cooling: lifecycle.cooling_examples || [],
    settling: lifecycle.settling_examples || [],
  }

  return (
    <section className="space-y-4">
      <h2 className="mb-5 font-serif text-xl font-semibold">
        收藏生命周期
      </h2>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        {stages.map(({ key, data, color }) => (
          <GlassCard key={key} className="flex flex-col p-6">
            <div className={cn('mb-3 h-1.5 w-10 rounded-full', color)} />
            <p className="font-serif text-lg font-semibold">{data.label}</p>
            <p className="mt-0.5 font-sans text-xs text-muted-foreground">
              {data.weeks}
            </p>
            <p className="mt-3 font-serif text-3xl font-bold leading-none tabular-nums">
              {data.avg_per_week.toFixed(1)}
            </p>
            <p className="mt-0.5 font-sans text-[11px] text-muted-foreground">
              周均播放
            </p>
          </GlassCard>
        ))}

        <GlassCard className="flex flex-col p-6">
          <div className="mb-3 h-1.5 w-10 rounded-full bg-emerald-500/70" />
          <p className="font-serif text-lg font-semibold">一年后</p>
          <p className="mt-0.5 font-sans text-xs text-muted-foreground">
            收藏分化结果
          </p>

          <div className="mt-4 space-y-2.5">
            <FateBar
              label="常青"
              pct={lifecycle.fate.evergreen_pct}
              color="bg-emerald-500"
            />
            <FateBar
              label="偶尔"
              pct={lifecycle.fate.occasional_pct}
              color="bg-amber-500"
            />
            <FateBar
              label="遗忘"
              pct={lifecycle.fate.forgotten_pct}
              color="bg-muted-foreground/30"
            />
          </div>
        </GlassCard>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {stages.map(({ key, label, color }) => {
          const examples = stageExamples[key]
          if (!examples.length) return null
          return (
            <div key={key} className="space-y-2">
              <div className="flex items-center gap-2">
                <div className={cn('h-2 w-2 rounded-full', color)} />
                <p className="font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">
                  {label}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {examples.map((ex) => (
                  <div key={`${ex.track_name}-${ex.artist_name}`}
                    className="flex items-center gap-2 rounded-full border border-border bg-muted/30 px-3 py-1.5">
                    {ex.cover_url && (
                      <img src={ex.cover_url} alt={ex.track_name}
                        className="h-6 w-6 rounded-full object-cover"
                        loading="lazy"
                        decoding="async" />
                    )}
                    <span className="font-sans text-xs font-medium">{displayName(ex.track_name)}</span>
                    <span className="font-sans text-[10px] text-muted-foreground">{displayName(ex.artist_name)}</span>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {insights.lifecycle_trend && insights.lifecycle_trend.length > 0 && (
        <LifecycleTrendChart
          trend={insights.lifecycle_trend}
          topTracks={insights.lifecycle_top_tracks}
        />
      )}
    </section>
  )
}
