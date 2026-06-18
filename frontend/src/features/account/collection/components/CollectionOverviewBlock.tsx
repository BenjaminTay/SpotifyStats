import { useMemo } from 'react'
import { LazyEChart } from '@/components/charts/LazyEChart'
import { GlassCard } from '@/components/shared/GlassCard'
import { KpiCard } from '@/components/shared/KpiCard'
import { buildChartBase } from '@/components/charts/EChartsTheme'
import { useTheme } from '@/hooks/useTheme'
import type { CollectionInsights, SaveTimelinePoint } from '@/types/account'
import { formatDate } from '@/features/account/collection/utils/formatDate'

function SaveTimelineChart({
  timeline,
}: {
  timeline: SaveTimelinePoint[]
}) {
  const { isDark } = useTheme()
  const base = buildChartBase(isDark)

  const { years, barData, cumData } = useMemo(() => {
    const sorted = [...timeline].sort((a, b) => a.year - b.year)
    const bar: number[] = []
    const cum: number[] = []
    let running = 0
    for (const p of sorted) {
      bar.push(p.count)
      running += p.count
      cum.push(running)
    }
    return {
      years: sorted.map(p => String(p.year)),
      barData: bar,
      cumData: cum,
    }
  }, [timeline])

  const option = useMemo(() => ({
    ...base,
    grid: { ...base.grid, left: 8, right: 8 },
    xAxis: {
      ...base.xAxis,
      data: years,
      axisLabel: { ...base.xAxis.axisLabel, interval: 0 },
    },
    yAxis: [
      {
        ...base.yAxis,
        name: '年度收藏',
        nameTextStyle: { fontSize: 10, color: base.textStyle.color },
        splitLine: { ...base.yAxis.splitLine },
      },
      {
        ...base.yAxis,
        name: '累计总量',
        nameTextStyle: { fontSize: 10, color: base.textStyle.color },
        splitLine: { show: false },
      },
    ],
    tooltip: { ...base.tooltip, trigger: 'axis' },
    series: [
      {
        name: '年度收藏量',
        type: 'bar',
        data: barData,
        yAxisIndex: 0,
        barMaxWidth: 34,
        itemStyle: {
          color: base.color?.[0],
          borderRadius: [3, 3, 0, 0],
        },
      },
      {
        name: '累计总量',
        type: 'line',
        data: cumData,
        yAxisIndex: 1,
        smooth: true,
        symbolSize: 6,
        showSymbol: true,
        lineStyle: { width: 2.5, color: '#e11d48' },
        itemStyle: { color: '#e11d48' },
      },
    ],
  }), [base, years, barData, cumData])

  return <LazyEChart option={option} style={{ height: 240 }} notMerge />
}

export function CollectionOverviewBlock({
  insights,
}: {
  insights: CollectionInsights
}) {
  const { overview } = insights

  return (
    <section className="space-y-4">
      <h2 className="mb-5 font-serif text-xl font-semibold">
        收藏纵览
      </h2>

      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <KpiCard
            label="收藏曲目"
            value={overview.saved_tracks.toLocaleString()}
          />
          <KpiCard
            label="收藏专辑"
            value={overview.saved_albums.toLocaleString()}
          />
          <KpiCard
            label="收藏艺人"
            value={overview.saved_artists.toLocaleString()}
          />
          <KpiCard
            label="播放列表"
            value={overview.playlists.toLocaleString()}
          />
        </div>

        <GlassCard className="p-6">
          <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
            年度收藏量
          </p>
          <SaveTimelineChart timeline={overview.save_timeline} />

          {overview.biggest_save_day && (
            <div className="mt-4 flex items-center gap-2 rounded-lg bg-accent-foreground/5 px-4 py-2.5">
              <span className="font-sans text-xs text-muted-foreground">
                最大收藏日
              </span>
              <span className="font-serif text-sm font-semibold tabular-nums">
                {formatDate(overview.biggest_save_day.date)}
              </span>
              <span className="font-sans text-xs text-muted-foreground">
                一口气收藏
              </span>
              <span className="font-serif text-sm font-bold text-accent-foreground">
                {overview.biggest_save_day.count}
              </span>
              <span className="font-sans text-xs text-muted-foreground">首</span>
            </div>
          )}
        </GlassCard>
      </div>
    </section>
  )
}
