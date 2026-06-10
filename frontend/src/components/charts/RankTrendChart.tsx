import { lazy, Suspense, useState, useMemo } from 'react'
import { useTheme } from '@/hooks/useTheme'
import { buildChartBase } from './EChartsTheme'

const ReactECharts = lazy(() => import('echarts-for-react'))

interface RankDataPoint {
  week: string
  rank: number | null
  label?: string
}

interface OverlaySeries {
  data: RankDataPoint[]
  name: string
}

const OVERLAY_COLORS = [
  { light: '#4A7C59', dark: '#7BA587' },  // green
  { light: '#5B6EAD', dark: '#8B9FD4' },  // blue
]

interface RankTrendChartProps {
  data: RankDataPoint[]
  topN: number
  peakPosition?: number
  overlays?: OverlaySeries[]
}

function parseWeek(str: string): Date | null {
  const parts = str.split('-')
  if (parts.length !== 3) return null
  const [y, m, d] = parts.map(Number)
  if (isNaN(y) || isNaN(m) || isNaN(d)) return null
  return new Date(y, m - 1, d)
}

function formatWeekISO(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function formatWeekDisplay(iso: string): string {
  const parts = iso.split('-')
  if (parts.length >= 3) return `${parts[0]}/${parts[1]}/${parts[2]}`
  return iso
}

interface PeakRun {
  start: number
  end: number
  length: number
}

/** Fill every 7-day interval between the first and last charting week with null for off-chart weeks. */
function buildTimeline(data: RankDataPoint[]): { labels: string[]; values: (number | null)[] } {
  const rankByWeek = new Map<string, number | null>()
  const dates: Date[] = []

  for (const d of data) {
    if (!d.week) continue
    rankByWeek.set(d.week, d.rank)
    const dt = parseWeek(d.week)
    if (dt) dates.push(dt)
  }

  if (dates.length === 0) return { labels: [], values: [] }

  dates.sort((a, b) => a.getTime() - b.getTime())
  const minDate = dates[0]
  const maxDate = dates[dates.length - 1]

  const labels: string[] = []
  const values: (number | null)[] = []
  const current = new Date(minDate)

  while (current <= maxDate) {
    const weekStr = formatWeekISO(current)
    labels.push(weekStr)
    values.push(rankByWeek.has(weekStr) ? rankByWeek.get(weekStr)! : null)
    current.setDate(current.getDate() + 7)
  }

  return { labels, values }
}

/** Split rank values into runs of consecutive peak positions. */
function findPeakRuns(values: (number | null)[], peakRank: number): PeakRun[] {
  const runs: PeakRun[] = []
  let runStart = -1

  for (let i = 0; i < values.length; i++) {
    if (values[i] === peakRank) {
      if (runStart === -1) runStart = i
    } else {
      if (runStart !== -1) {
        runs.push({ start: runStart, end: i - 1, length: i - runStart })
        runStart = -1
      }
    }
  }
  if (runStart !== -1) {
    runs.push({ start: runStart, end: values.length - 1, length: values.length - runStart })
  }

  return runs
}

export function RankTrendChart({
  data,
  topN,
  peakPosition,
  overlays,
}: RankTrendChartProps) {
  const { isDark } = useTheme()
  const base = useMemo(() => buildChartBase(isDark), [isDark])

  const { labels: rawLabels, values } = buildTimeline(data)

  const labels = rawLabels.map(formatWeekDisplay)
  const totalPoints = values.length

  // ── Zoom: overview vs detail (50-week window) ──
  const WINDOW_SIZE = 50
  const [viewMode, setViewMode] = useState<'overview' | 'detail'>('overview')
  const showZoomToggle = totalPoints > WINDOW_SIZE
  const effectiveTotal = viewMode === 'detail' && showZoomToggle
    ? Math.min(totalPoints, WINDOW_SIZE)
    : totalPoints

  // Show sparse x-axis labels — only major time boundaries, not every data point
  const labelInterval =
    effectiveTotal > 52 ? Math.floor(effectiveTotal / 8)
    : effectiveTotal > 26 ? Math.floor(effectiveTotal / 6)
    : effectiveTotal > 12 ? Math.floor(effectiveTotal / 4)
    : 0

  const textColor = isDark ? '#A09888' : '#6B5E58'
  const rankColor = isDark ? '#D4836F' : '#C84C3D'

  // ── Peak annotation ──
  const validRanks = values.filter((v): v is number => v !== null)
  const peakRank = validRanks.length > 0 ? Math.min(...validRanks) : null
  const peakRuns = peakRank !== null ? findPeakRuns(values, peakRank) : []
  const multiWeekPeaks = peakRuns.filter((r) => r.length > 1)

  const series: any[] = [
    {
      name: '排名',
      type: 'line',
      data: values,
      connectNulls: false,
      smooth: false,
      symbol: 'circle',
      symbolSize: 7,
      showSymbol: true,
      showAllSymbol: true,
      z: 10,
      emphasis: {
        focus: 'none' as const,
        symbolSize: 13,
        itemStyle: {
          borderColor: rankColor,
          borderWidth: 2,
        },
      },
      blur: {
        itemStyle: { opacity: 1 },
        lineStyle: { opacity: 1 },
      },
      lineStyle: {
        width: 2,
        color: rankColor,
        cap: 'round',
      },
      itemStyle: {
        color: rankColor,
        borderColor: isDark ? '#1C1C20' : '#FFFFFF',
        borderWidth: 2,
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: isDark ? 'rgba(212,131,111,0.15)' : 'rgba(200,76,61,0.10)' },
            { offset: 1, color: 'transparent' },
          ],
        },
      },
      markLine: peakPosition
        ? {
            silent: true,
            symbol: 'none',
            animation: false,
            lineStyle: {
              color: rankColor,
              type: 'dashed',
              width: 1,
              opacity: 0.35,
            },
            label: {
              formatter: `峰值 #${peakPosition}`,
              position: 'insideEndTop',
              fontSize: 11,
              fontWeight: 500,
              color: textColor,
              distance: [0, 6],
            },
            data: [{ yAxis: peakPosition }],
          }
        : undefined,
      // Pin markers for ALL peaks (pin at first peak week)
      markPoint: peakRuns.length > 0
        ? {
            silent: true,
            symbol: 'pin',
            symbolSize: 24,
            animation: false,
            label: { fontSize: 9, color: '#fff' },
            data: peakRuns.map((r) => ({
              coord: [r.start, peakRank!] as [number, number],
              value: `#${peakRank}`,
            })),
          }
        : undefined,
      // Shaded band behind consecutive multi-week peak runs (visual only, no labels)
      markArea: multiWeekPeaks.length > 0
        ? {
            silent: true,
            animation: false,
            itemStyle: {
              color: isDark ? 'rgba(212,131,111,0.20)' : 'rgba(200,76,61,0.10)',
              borderColor: rankColor,
              borderWidth: 2,
              borderType: 'solid',
              borderRadius: 8,
            },
            data: multiWeekPeaks.map((run) => [
              { xAxis: run.start, yAxis: peakRank! - 0.45 },
              { xAxis: run.end, yAxis: peakRank! + 0.45 },
            ]),
          }
        : undefined,
    },
  ]

  if (overlays && overlays.length > 0) {
    overlays.forEach((overlay, idx) => {
      const color = OVERLAY_COLORS[idx % OVERLAY_COLORS.length]
      const seriesColor = isDark ? color.dark : color.light

      const rankMap = new Map(overlay.data.map((d) => [d.week, d.rank]))
      const labelMap = new Map(
        overlay.data.filter((d) => d.label).map((d) => [d.week, d.label!])
      )
      const overlayValues = rawLabels.map((week) => {
        const rank = rankMap.get(week)
        if (rank === undefined) return null
        const lbl = labelMap.get(week)
        return lbl ? { value: rank, label: lbl } : rank
      })

      series.push({
        name: overlay.name,
        type: 'line',
        data: overlayValues,
        connectNulls: false,
        smooth: false,
        symbol: 'diamond',
        symbolSize: 7,
        showSymbol: true,
        showAllSymbol: true,
        z: 1,
        emphasis: {
          focus: 'none' as const,
          symbolSize: 13,
          itemStyle: {
            borderColor: seriesColor,
            borderWidth: 2,
          },
        },
        blur: {
          itemStyle: { opacity: 1 },
          lineStyle: { opacity: 1 },
        },
        lineStyle: {
          width: 1.5,
          color: seriesColor,
          type: 'dashed',
          dashOffset: 2,
        },
        itemStyle: {
          color: seriesColor,
          borderColor: isDark ? '#1C1C20' : '#FFFFFF',
          borderWidth: 2,
        },
        tooltip: {
          formatter: (p: any) => {
            const val = p.value
            const lbl = p.data?.label
            const display = val === null || val === undefined
              ? '<span style="opacity:0.4">—</span>'
              : `<span style="font-weight:600">#${val}</span>`
            const labelPart = lbl ? ` <span style="opacity:0.6;font-size:10px">${lbl}</span>` : ''
            return `${p.marker} ${p.seriesName}: ${display}${labelPart}`
          },
        },
      })
    })
  }

  const option = {
    ...base,
    animation: true,
    animationDuration: 600,
    animationEasing: 'cubicOut',
    grid: {
      ...base.grid,
      left: 8,
      right: 20,
      top: 32,
      bottom: showZoomToggle && viewMode === 'detail'
        ? 60
        : labels.length > 20 ? 40 : 8,
    },
    xAxis: {
      ...base.xAxis,
      data: labels,
      axisLabel: {
        ...base.xAxis.axisLabel,
        interval: labelInterval,
        rotate: labels.length > 30 ? 45 : labels.length > 20 ? 30 : 0,
        fontSize: 10,
      },
    },
    yAxis: {
      ...base.yAxis,
      inverse: true,
      min: 1,
      max: topN,
      interval: undefined,
      axisLabel: {
        color: textColor,
        fontSize: 11,
        formatter: (v: number) => (v === 1 ? '#1' : `#${v}`),
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)',
          type: 'dashed',
        },
      },
    },
    series,
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
      padding: [10, 14],
      extraCssText: 'border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.12);',
      formatter: (params: any) => {
        const items = Array.isArray(params) ? params : [params]
        if (!items.length) return ''
        const week = items[0].axisValue
        let html = `<div style="font-weight:600;font-size:13px;margin-bottom:6px;font-family:'Inter Variable',sans-serif">${week}</div>`
        items.forEach((p: any) => {
          const val = p.value
          const lbl = p.data?.label
          const display = val === null || val === undefined
            ? '<span style="opacity:0.4">—</span>'
            : `<span style="font-weight:600">#${val}</span>`
          const labelPart = lbl ? ` <span style="opacity:0.6;font-size:10px">${lbl}</span>` : ''
          html += `<div style="font-size:11px;line-height:1.7;font-family:'Inter Variable',sans-serif">${p.marker} ${p.seriesName}: ${display}${labelPart}</div>`
        })
        return html
      },
    },
    legend: overlays && overlays.length > 0
      ? {
          show: true,
          bottom: showZoomToggle && viewMode === 'detail' ? 24 : 0,
          left: 'center',
          textStyle: { color: textColor, fontSize: 11 },
          itemWidth: 16,
          itemHeight: 2,
          icon: 'roundRect',
        }
      : undefined,
    dataZoom: showZoomToggle && viewMode === 'detail'
      ? [
          {
            type: 'slider' as const,
            start: 0,
            end: (WINDOW_SIZE / totalPoints) * 100,
            zoomLock: true,
            handleSize: '80%',
            showDetail: false,
            backgroundColor: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)',
            dataBackground: {
              lineStyle: { color: textColor, opacity: 0.15 },
              areaStyle: { color: textColor, opacity: 0.04 },
            },
            selectedDataBackground: {
              lineStyle: { color: rankColor, opacity: 0.35 },
              areaStyle: { color: rankColor, opacity: 0.08 },
            },
            handleStyle: { color: rankColor, opacity: 0.7 },
            moveHandleStyle: { color: rankColor },
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
  }

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
      <Suspense fallback={<div className="h-[360px] animate-pulse rounded-lg bg-muted/40" />}>
        <ReactECharts option={option} style={{ height: 360, isolation: 'isolate' } as React.CSSProperties} notMerge />
      </Suspense>
    </div>
  )
}
