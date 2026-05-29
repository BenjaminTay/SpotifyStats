import { lazy, Suspense, useMemo } from 'react'
import { useTheme } from '@/hooks/useTheme'
import { buildChartBase } from './EChartsTheme'
import { getChartColors } from '@/lib/theme'

const ReactECharts = lazy(() => import('echarts-for-react'))

interface TrendDatum {
  label: string
  value: number
  secondary?: number
}

interface CategoryDatum {
  name: string
  value: number
}

interface HeatmapDatum {
  x: number[]
  y: string[]
  z: number[][]
}

function ChartShell({ option, height = 280 }: { option: Record<string, unknown>; height?: number }) {
  return (
    <Suspense fallback={<div className="animate-pulse rounded-lg bg-muted/40" style={{ height }} />}>
      <ReactECharts option={option} style={{ height }} notMerge />
    </Suspense>
  )
}

export function AnalysisTrendChart({ data, mode = 'bar' }: { data: TrendDatum[]; mode?: 'bar' | 'line' }) {
  const { isDark } = useTheme()
  const base = buildChartBase(isDark)
  const colors = getChartColors(isDark)
  const option = useMemo(() => ({
    ...base,
    xAxis: { ...base.xAxis, data: data.map((d) => d.label) },
    yAxis: { ...base.yAxis },
    tooltip: { ...base.tooltip, trigger: 'axis' },
    series: [
      {
        type: mode,
        data: data.map((d) => d.value),
        smooth: true,
        barMaxWidth: 34,
        areaStyle: mode === 'line' ? { opacity: 0.08 } : undefined,
        itemStyle: { color: colors[0], borderRadius: [3, 3, 0, 0] },
        lineStyle: { color: colors[0], width: 2 },
      },
      ...(data.some((d) => d.secondary !== undefined)
        ? [{
            type: 'line',
            data: data.map((d) => d.secondary ?? null),
            smooth: true,
            symbolSize: 4,
            itemStyle: { color: colors[4] },
            lineStyle: { color: colors[4], width: 2 },
          }]
        : []),
    ],
  }), [base, colors, data, mode])

  return <ChartShell option={option} />
}

export function HorizontalBarChart({ data, valueName = '播放次数' }: { data: CategoryDatum[]; valueName?: string }) {
  const { isDark } = useTheme()
  const base = buildChartBase(isDark)
  const colors = getChartColors(isDark)
  const reversed = [...data].reverse()
  const option = useMemo(() => ({
    ...base,
    grid: { ...base.grid, left: 12, right: 18, top: 8, bottom: 4, containLabel: true },
    xAxis: { ...base.xAxis, type: 'value' },
    yAxis: { ...base.yAxis, type: 'category', data: reversed.map((d) => d.name), axisLabel: { ...base.yAxis.axisLabel, width: 140, overflow: 'truncate' } },
    tooltip: { ...base.tooltip, trigger: 'axis' },
    series: [{
      type: 'bar',
      name: valueName,
      data: reversed.map((d, i) => ({
        value: d.value,
        itemStyle: { color: colors[i % colors.length], borderRadius: [0, 4, 4, 0] },
      })),
      barMaxWidth: 20,
    }],
  }), [base, colors, reversed, valueName])

  return <ChartShell option={option} height={Math.max(260, data.length * 30)} />
}

export function HeatmapChart({ data, height = 360 }: { data: HeatmapDatum; height?: number }) {
  const { isDark } = useTheme()
  const base = buildChartBase(isDark)
  const cells = data.z.flatMap((row, yIndex) => row.map((value, xIndex) => [xIndex, yIndex, value]))
  const max = Math.max(...cells.map((item) => Number(item[2])), 1)
  const option = useMemo(() => ({
    ...base,
    grid: { left: 48, right: 18, top: 18, bottom: 24 },
    xAxis: { ...base.xAxis, type: 'category', data: data.x.map((h) => `${h}`), splitArea: { show: true } },
    yAxis: { ...base.yAxis, type: 'category', data: data.y, splitArea: { show: true } },
    visualMap: {
      min: 0,
      max,
      show: false,
      inRange: { color: isDark ? ['#262626', '#D4836F'] : ['#F4EEE6', '#C84C3D'] },
    },
    tooltip: {
      ...base.tooltip,
      formatter: (params: { value: [number, number, number] }) => {
        const [x, y, value] = params.value
        return `${data.y[y]} ${data.x[x]}:00<br/>${value} 次`
      },
    },
    series: [{
      type: 'heatmap',
      data: cells,
      emphasis: { itemStyle: { borderColor: isDark ? '#F0EBE3' : '#2D2420', borderWidth: 1 } },
    }],
  }), [base, cells, data, isDark, max])

  return <ChartShell option={option} height={height} />
}

export function DonutChart({ data }: { data: CategoryDatum[] }) {
  const { isDark } = useTheme()
  const base = buildChartBase(isDark)
  const option = useMemo(() => ({
    ...base,
    tooltip: { ...base.tooltip, trigger: 'item' },
    legend: { bottom: 0, textStyle: { color: isDark ? '#A09888' : '#6B5E58', fontSize: 11 } },
    series: [{
      type: 'pie',
      radius: ['48%', '72%'],
      center: ['50%', '43%'],
      avoidLabelOverlap: true,
      label: { show: false },
      data: data.map((d) => ({ name: d.name, value: d.value })),
    }],
  }), [base, data, isDark])

  return <ChartShell option={option} height={280} />
}
