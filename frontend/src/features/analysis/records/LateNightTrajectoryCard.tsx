import { useMemo, useState } from 'react'
import { LazyEChart } from '@/components/charts/LazyEChart'
import { buildChartBase } from '@/components/charts/EChartsTheme'
import { useTheme } from '@/hooks/useTheme'
import type { PlaybackTimePatternRecords } from '@/types/analysis'
import { RecordCard } from './PlaybackRecordsPrimitives'

type Granularity = 'monthly' | 'quarterly'
type Trajectory = NonNullable<PlaybackTimePatternRecords['late_night_trajectory']>

export function LateNightTrajectoryCard({ trajectory }: { trajectory?: Trajectory }) {
  const [granularity, setGranularity] = useState<Granularity>('monthly')
  const { isDark } = useTheme()
  const base = buildChartBase(isDark)
  const rows = useMemo(() => trajectory?.[granularity] ?? [], [granularity, trajectory])
  const threshold = granularity === 'monthly'
    ? (trajectory?.monthly_min_plays ?? 500)
    : (trajectory?.quarterly_min_plays ?? 1500)
  const qualified = rows.filter((row) => row.qualified !== false && (row.total_plays ?? 0) >= threshold)
  const best = [...qualified].sort((a, b) => b.value - a.value)[0]
  const label = granularity === 'monthly' ? '月' : '季度'

  const option = useMemo(() => {
    const zoomStart = rows.length > 18 ? Math.max(0, (rows.length - 18) / rows.length * 100) : 0
    const accent = base.color?.[0] ?? '#b5443c'
    return {
      ...base,
      grid: { ...base.grid, left: 8, right: 8, bottom: rows.length > 18 ? 52 : 28 },
      xAxis: {
        ...base.xAxis,
        type: 'category',
        data: rows.map((row) => row.name),
        axisLabel: { ...base.xAxis.axisLabel, interval: granularity === 'monthly' ? 2 : 0, rotate: granularity === 'monthly' ? 35 : 0 },
      },
      yAxis: {
        ...base.yAxis,
        type: 'value',
        min: 0,
        axisLabel: { ...base.yAxis.axisLabel, formatter: '{value}%' },
      },
      tooltip: { ...base.tooltip, trigger: 'axis', valueFormatter: (value: number) => `${value}%` },
      dataZoom: rows.length > 18 ? [
        { type: 'inside', start: zoomStart, end: 100 },
        { type: 'slider', start: zoomStart, end: 100, height: 16, bottom: 4, borderColor: 'transparent' },
      ] : undefined,
      series: [{
        name: '深夜占比',
        type: 'bar',
        barMaxWidth: 24,
        data: rows.map((row) => ({
          value: row.value,
          itemStyle: {
            color: accent,
            borderRadius: [3, 3, 0, 0],
          },
        })),
      }],
    }
  }, [base, granularity, rows])

  const toggle = (
    <div className="flex rounded-[6px] border border-border bg-muted/30 p-0.5" aria-label="深夜轨迹聚合方式">
      {(['monthly', 'quarterly'] as Granularity[]).map((key) => (
        <button key={key} type="button" aria-pressed={granularity === key} onClick={() => setGranularity(key)} className={`rounded-[4px] px-3 py-1 font-sans text-[11px] font-medium transition-colors ${granularity === key ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}>
          {key === 'monthly' ? '按月' : '按季度'}
        </button>
      ))}
    </div>
  )

  return (
    <RecordCard title="深夜聆听轨迹 · Late-night Listening" subtitle="0:00–4:59 的有效播放占比，趋势保留全部时间点" toggle={toggle}>
      {rows.length === 0 ? (
        <div className="rounded-[12px] border border-dashed border-border px-4 py-10 text-center">
          <p className="font-serif text-[16px] font-semibold">暂无深夜轨迹</p>
          <p className="mt-1 font-sans text-[11px] text-muted-foreground">当前筛选范围没有可聚合的有效播放。</p>
        </div>
      ) : (
        <>
          <div className="mb-4 flex flex-col gap-2 rounded-[12px] border border-border/70 bg-muted/15 px-4 py-3 sm:flex-row sm:items-end sm:justify-between">
            {best ? (
              <div>
                <p className="font-sans text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">最高{label}</p>
                <p className="mt-0.5 font-serif text-[24px] font-semibold tabular-nums">{best.name} · {best.value}%</p>
                <p className="font-sans text-[11px] text-muted-foreground">{Number(best.secondary_value ?? 0).toLocaleString('zh-CN')} 次深夜播放 / {Number(best.total_plays ?? 0).toLocaleString('zh-CN')} 次有效播放</p>
              </div>
            ) : (
              <div>
                <p className="font-serif text-[16px] font-semibold">暂无可比较的{label}</p>
                <p className="mt-1 font-sans text-[11px] text-muted-foreground">下方仍展示所有时间点的实际深夜占比。</p>
              </div>
            )}
          </div>
          <LazyEChart option={option} style={{ height: 300 }} fallbackHeight={300} notMerge />
        </>
      )}
    </RecordCard>
  )
}
