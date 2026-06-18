import { useState, useMemo, type CSSProperties } from 'react'
import { useTheme } from '@/hooks/useTheme'
import { buildChartBase } from './EChartsTheme'
import { LazyEChart } from './LazyEChart'
import { ENTITY_COLORS } from '@/features/billboard/versus/versusData'

interface VersusRankDataPoint {
  week: string
  rank: number | null
}

interface VersusRankSeries {
  name: string
  data: VersusRankDataPoint[]
}

/** Fill every 7-day interval between the first and last charting week with null for off-chart weeks. */
function buildTimeline(data: VersusRankDataPoint[]): { labels: string[]; values: (number | null)[] } {
  const rankByWeek = new Map<string, number | null>()
  const dates: Date[] = []

  for (const d of data) {
    if (!d.week) continue
    rankByWeek.set(d.week, d.rank)
    const [y, m, day] = d.week.split('-').map(Number)
    if (!isNaN(y) && !isNaN(m) && !isNaN(day)) dates.push(new Date(y, m - 1, day))
  }

  if (dates.length === 0) return { labels: [], values: [] }

  dates.sort((a, b) => a.getTime() - b.getTime())
  const minDate = dates[0]
  const maxDate = dates[dates.length - 1]

  const labels: string[] = []
  const values: (number | null)[] = []
  const current = new Date(minDate)

  while (current <= maxDate) {
    const weekStr = `${current.getFullYear()}-${String(current.getMonth() + 1).padStart(2, '0')}-${String(current.getDate()).padStart(2, '0')}`
    labels.push(weekStr)
    values.push(rankByWeek.has(weekStr) ? rankByWeek.get(weekStr)! : null)
    current.setDate(current.getDate() + 7)
  }

  return { labels, values }
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

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

interface VersusRankChartProps {
  series: VersusRankSeries[]
  topN: number
}

export function VersusRankChart({ series: inputSeries, topN }: VersusRankChartProps) {
  const { isDark } = useTheme()
  const base = useMemo(() => buildChartBase(isDark), [isDark])

  // Build unified timeline from all series (calendar mode)
  const timelines = inputSeries.map((s) => buildTimeline(s.data))
  const allWeeks = Array.from(new Set(timelines.flatMap((t) => t.labels))).sort()
  const calendarLabels = allWeeks.map(formatWeekDisplay)

  const calendarSeries = timelines.map((tl) => {
    const weekIndex = new Map(tl.labels.map((w, i) => [w, i]))
    return allWeeks.map((w) => {
      const idx = weekIndex.get(w)
      return idx !== undefined ? tl.values[idx] : null
    })
  })

  // Aligned mode: trim leading nulls, align at W1, pad shorter to the longest
  const alignedRaw = timelines.map((tl) => {
    const start = tl.values.findIndex((v) => v !== null)
    if (start === -1) return [] as (number | null)[]
    return tl.values.slice(start)
  })
  const maxAlignedLen = Math.max(...alignedRaw.map((s) => s.length), 0)
  const alignedSeries = alignedRaw.map((s) => {
    const padded = [...s]
    while (padded.length < maxAlignedLen) padded.push(null)
    return padded
  })
  const alignedLabels = Array.from({ length: maxAlignedLen }, (_, i) => `W${i + 1}`)

  // ── Mode toggles ──
  const [alignMode, setAlignMode] = useState<'timeline' | 'aligned'>('timeline')
  const isAligned = alignMode === 'aligned'

  const labels = isAligned ? alignedLabels : calendarLabels
  const unifiedSeries = isAligned ? alignedSeries : calendarSeries

  const totalPoints = labels.length

  // Zoom: overview vs detail
  const WINDOW_SIZE = 50
  const [viewMode, setViewMode] = useState<'overview' | 'detail'>('overview')
  const showZoomToggle = totalPoints > WINDOW_SIZE
  const effectiveTotal = viewMode === 'detail' && showZoomToggle
    ? Math.min(totalPoints, WINDOW_SIZE)
    : totalPoints

  const labelInterval =
    effectiveTotal > 52 ? Math.floor(effectiveTotal / 8)
    : effectiveTotal > 26 ? Math.floor(effectiveTotal / 6)
    : effectiveTotal > 12 ? Math.floor(effectiveTotal / 4)
    : 0

  const textColor = isDark ? '#A09888' : '#6B5E58'

  // Pre-compute peaks and group series by peak value for consolidated markLine labels
  const seriesPeaks = unifiedSeries.map((values) => {
    const validValues = values.filter((v): v is number => v !== null)
    return validValues.length > 0 ? Math.min(...validValues) : null
  })

  const peakToIndices = new Map<number, number[]>()
  seriesPeaks.forEach((peak, si) => {
    if (peak != null) {
      if (!peakToIndices.has(peak)) peakToIndices.set(peak, [])
      peakToIndices.get(peak)!.push(si)
    }
  })

  // Build ECharts series
  const echartsSeries = unifiedSeries.map((values, si) => {
    const color = ENTITY_COLORS[si % ENTITY_COLORS.length]
    const peak = seriesPeaks[si] ?? 1
    const name = inputSeries[si]?.name ?? `Entity ${si + 1}`
    const peakRuns = findPeakRuns(values, peak)
    const multiWeekPeaks = peakRuns.filter((r) => r.length > 1)

    // Only the first series in each peak group carries the label;
    // always use colored dots — single or shared peak alike.
    const peakSiblings = peak != null ? (peakToIndices.get(peak) || []) : []
    const isLabelOwner = peakSiblings.length > 0 && peakSiblings[0] === si

    const markLineLabel = isLabelOwner
      ? (() => {
          const rich: Record<string, object> = {}
          let fmt = ''
          peakSiblings.forEach((idx, i) => {
            const c = ENTITY_COLORS[idx % ENTITY_COLORS.length]
            rich[`d${i}`] = { color: c, fontSize: 14, padding: [0, 1, 0, 1] }
            fmt += `{d${i}|●}`
          })
          fmt += ` 峰值 #${peak}`
          return {
            formatter: fmt,
            rich,
            position: 'insideEndTop' as const,
            fontSize: 11,
            fontWeight: 500,
            color: textColor,
          }
        })()
      : undefined

    return {
      name,
      type: 'line' as const,
      data: values,
      connectNulls: false,
      smooth: false,
      symbol: 'circle',
      symbolSize: 7,
      showSymbol: true,
      showAllSymbol: true,
      z: 2,
      emphasis: {
        focus: 'none' as const,
        symbolSize: 13,
        itemStyle: {
          borderColor: color,
          borderWidth: 2,
        },
      },
      blur: {
        itemStyle: { opacity: 1 },
        lineStyle: { opacity: 1 },
      },
      lineStyle: { width: 2, color, cap: 'round' as const },
      itemStyle: {
        color,
        borderColor: isDark ? '#1C1C20' : '#FFFFFF',
        borderWidth: 2,
      },
      areaStyle: {
        color: {
          type: 'linear' as const,
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: hexToRgba(color, isDark ? 0.15 : 0.10) },
            { offset: 1, color: 'transparent' },
          ],
        },
      },
      markLine: {
        silent: true,
        symbol: 'none',
        animation: false,
        lineStyle: { color, type: 'dashed' as const, width: 1, opacity: 0.35 },
        label: markLineLabel,
        data: [{ yAxis: peak }],
      },
      markPoint: peakRuns.length > 0
        ? {
            silent: true,
            symbol: 'pin',
            symbolSize: 24,
            animation: false,
            label: { fontSize: 9, color: '#fff' },
            data: peakRuns.map((r) => ({
              coord: [r.start, peak] as [number, number],
              value: `#${peak}`,
            })),
          }
        : undefined,
      markArea: multiWeekPeaks.length > 0
        ? {
            silent: true,
            animation: false,
            itemStyle: {
              color: hexToRgba(color, isDark ? 0.20 : 0.10),
              borderColor: color,
              borderWidth: 2,
              borderType: 'solid' as const,
              borderRadius: 8,
            },
            data: multiWeekPeaks.map((run) => [
              { xAxis: run.start, yAxis: peak - 0.45 },
              { xAxis: run.end, yAxis: peak + 0.45 },
            ]),
          }
        : undefined,
    }
  })

  const option = {
    ...base,
    animation: true,
    animationDuration: 600,
    animationEasing: 'cubicOut' as const,
    grid: {
      ...base.grid,
      left: 8,
      right: 20,
      top: 32,
      bottom: showZoomToggle && viewMode === 'detail' ? 60 : labels.length > 20 ? 40 : 8,
    },
    xAxis: {
      ...base.xAxis,
      data: labels,
      axisLabel: {
        ...base.xAxis.axisLabel,
        interval: labelInterval,
        rotate: isAligned ? 0 : labels.length > 30 ? 45 : labels.length > 20 ? 30 : 0,
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
          type: 'dashed' as const,
        },
      },
    },
    series: echartsSeries,
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
          const display = val === null || val === undefined
            ? '<span style="opacity:0.4">—</span>'
            : `<span style="font-weight:600">#${val}</span>`
          html += `<div style="font-size:11px;line-height:1.7;font-family:'Inter Variable',sans-serif">${p.marker} ${p.seriesName}: ${display}</div>`
        })
        return html
      },
    },
    legend: {
      show: true,
      bottom: showZoomToggle && viewMode === 'detail' ? 24 : 0,
      left: 'center' as const,
      textStyle: { color: textColor, fontSize: 11 },
      itemWidth: 16,
      itemHeight: 2,
      icon: 'roundRect' as const,
    },
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
              lineStyle: { color: ENTITY_COLORS[0], opacity: 0.35 },
              areaStyle: { color: ENTITY_COLORS[0], opacity: 0.08 },
            },
            handleStyle: { color: ENTITY_COLORS[0], opacity: 0.7 },
            moveHandleStyle: { color: ENTITY_COLORS[0] },
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
      <div className="flex items-center justify-between mb-1 gap-2">
        {/* Align mode toggle — always visible */}
        <div
          className="inline-flex rounded-md border text-xs font-medium overflow-hidden"
          style={{
            borderColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
          }}
        >
          <button
            onClick={() => setAlignMode('timeline')}
            className="px-2.5 py-1 transition-colors cursor-pointer"
            style={{
              backgroundColor: alignMode === 'timeline'
                ? (isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)')
                : 'transparent',
              color: alignMode === 'timeline' ? textColor : (isDark ? '#78716C' : '#9B8E85'),
            }}
          >
            时间线
          </button>
          <button
            onClick={() => setAlignMode('aligned')}
            className="px-2.5 py-1 transition-colors cursor-pointer"
            style={{
              backgroundColor: alignMode === 'aligned'
                ? (isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)')
                : 'transparent',
              color: alignMode === 'aligned' ? textColor : (isDark ? '#78716C' : '#9B8E85'),
            }}
          >
            同期对比
          </button>
        </div>

        {/* Zoom toggle — only when enough data points */}
        {showZoomToggle && (
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
        )}
      </div>
      <LazyEChart option={option} style={{ height: 360, isolation: 'isolate' } as CSSProperties} notMerge />
    </div>
  )
}
