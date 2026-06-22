import { useMemo, useState, type CSSProperties } from 'react'
import { useTheme } from '@/hooks/useTheme'
import { buildChartBase } from './EChartsTheme'
import { LazyEChart } from './LazyEChart'
import { getChartColors } from '@/lib/theme'

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
  return <LazyEChart option={option} style={{ height, isolation: 'isolate' } as CSSProperties} notMerge />
}

export function AnalysisTrendChart({
  data,
  mode = 'bar',
  showZoom = false,
}: {
  data: TrendDatum[]
  mode?: 'bar' | 'line'
  showZoom?: boolean
}) {
  const { isDark } = useTheme()
  const base = useMemo(() => buildChartBase(isDark), [isDark])
  const colors = useMemo(() => getChartColors(isDark), [isDark])

  // ── Zoom toggle: 全貌 / 细节（默认展示最近 365 天，从最左边开始）──
  const WINDOW_SIZE = 365
  const [viewMode, setViewMode] = useState<'overview' | 'detail'>('overview')
  const showZoomToggle = showZoom && data.length > WINDOW_SIZE
  const textColor = isDark ? '#A09888' : '#6B5E58'

  const option = useMemo(() => ({
    ...base,
    grid: {
      ...base.grid,
      bottom: showZoomToggle && viewMode === 'detail' ? 60 : base.grid?.bottom ?? 8,
    },
    xAxis: { ...base.xAxis, data: data.map((d) => d.label) },
    yAxis: { ...base.yAxis },
    tooltip: {
      ...base.tooltip,
      trigger: 'axis' as const,
      axisPointer: {
        type: 'line' as const,
        lineStyle: {
          color: isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.08)',
          width: 1,
          type: 'dashed' as const,
        },
      },
    },
    dataZoom: showZoomToggle && viewMode === 'detail'
      ? [
          {
            type: 'slider' as const,
            start: 0,
            end: Math.min((WINDOW_SIZE / data.length) * 100, 100),
            zoomLock: true,
            handleSize: '80%',
            showDetail: false,
            backgroundColor: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)',
            dataBackground: {
              lineStyle: { color: textColor, opacity: 0.15 },
              areaStyle: { color: textColor, opacity: 0.04 },
            },
            selectedDataBackground: {
              lineStyle: { color: colors[0], opacity: 0.35 },
              areaStyle: { color: colors[0], opacity: 0.08 },
            },
            handleStyle: { color: colors[0], opacity: 0.7 },
            moveHandleStyle: { color: colors[0] },
            textStyle: { color: textColor, fontSize: 10 },
            borderColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
          },
          {
            type: 'inside' as const,
            zoomOnMouseWheel: false,
            moveOnMouseMove: true,
            moveOnMouseWheel: true,
          },
        ]
      : undefined,
    series: [
      {
        type: mode,
        data: data.map((d) => d.value),
        smooth: true,
        barMaxWidth: 34,
        areaStyle: mode === 'line' ? { color: colors[0], opacity: 0.08 } : undefined,
        itemStyle: { color: colors[0], borderRadius: [3, 3, 0, 0] },
        lineStyle: { color: colors[0], width: 2 },
        emphasis: {
          focus: 'none' as const,
          itemStyle: { color: colors[0] },
          lineStyle: mode === 'line' ? { color: colors[0], width: 2 } : undefined,
          areaStyle: mode === 'line' ? { color: colors[0], opacity: 0.14 } : undefined,
        },
      },
      ...(data.some((d) => d.secondary !== undefined)
        ? [{
            type: 'line' as const,
            data: data.map((d) => d.secondary ?? null),
            smooth: true,
            symbolSize: 4,
            itemStyle: { color: colors[4] },
            lineStyle: { color: colors[4], width: 2 },
            emphasis: {
              focus: 'none' as const,
              itemStyle: { color: colors[4] },
              lineStyle: { color: colors[4], width: 3 },
            },
          }]
        : []),
    ],
  }), [base, colors, data, mode, isDark, showZoomToggle, viewMode, textColor, WINDOW_SIZE])

  return (
    <div>
      {showZoomToggle && (
        <div className="flex items-center justify-end mb-1">
          <div
            className="inline-flex rounded-md border text-xs font-medium overflow-hidden"
            style={{
              borderColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
            }}
          >
            <button
              type="button"
              onClick={() => setViewMode('overview')}
              className="px-2.5 py-1 transition-colors cursor-pointer"
              style={{
                backgroundColor: viewMode === 'overview'
                  ? (isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)')
                  : 'transparent',
                color: viewMode === 'overview' ? textColor : (isDark ? '#78716C' : '#9B8E85'),
              }}
            >
              全貌
            </button>
            <button
              type="button"
              onClick={() => setViewMode('detail')}
              className="px-2.5 py-1 transition-colors cursor-pointer"
              style={{
                backgroundColor: viewMode === 'detail'
                  ? (isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)')
                  : 'transparent',
                color: viewMode === 'detail' ? textColor : (isDark ? '#78716C' : '#9B8E85'),
              }}
            >
              细节
            </button>
          </div>
        </div>
      )}
      <ChartShell option={option} />
    </div>
  )
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
