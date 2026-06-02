import { lazy, Suspense, useMemo } from 'react'
import { useTheme } from '@/hooks/useTheme'
import { buildChartBase } from './EChartsTheme'
import type { AdvanceSingleRank, ReleaseCycleRankEntry, ReleaseCycleTimelineEntry, WikiSingle } from '@/types/billboard'

const ReactECharts = lazy(() => import('echarts-for-react'))

interface AlbumHistoryEntry {
  week?: string
  week_offset?: number
  rank: number
  play_count?: number
}

interface ReleaseTimelineChartProps {
  albumHistory: AlbumHistoryEntry[]
  singlesOverlay?: { week?: string; week_offset?: number; rank: number }[]
  wikiSingles?: WikiSingle[]
  albumReleaseDate?: string
  albumTimeline?: ReleaseCycleTimelineEntry[]
  advanceSingleRanks?: AdvanceSingleRank[]
  bestTrackRanks?: { name: string; ranks: ReleaseCycleRankEntry[] } | null
}

type MarkLineItem = {
  name: string
  xAxis: number
  lineStyle: {
    color: string
    type: string
    width: number
    opacity: number
  }
  label: {
    formatter: string
    position: string
    fontSize: number
    color: string
  }
}

type ChartSeries = {
  name: string
  type: string
  yAxisIndex?: number
  data: (number | null)[]
  connectNulls?: boolean
  symbol?: string
  symbolSize?: number
  lineStyle?: Record<string, unknown>
  itemStyle?: Record<string, unknown>
  markLine?: Record<string, unknown>
  barWidth?: string
  z?: number
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

function formatDateDisplay(date: Date): string {
  return `${date.getFullYear()}/${date.getMonth() + 1}/${date.getDate()}`
}

function parseWikiDate(dateStr: string | null): Date | null {
  if (!dateStr) return null
  const cleaned = dateStr.replace(/(\d+)(st|nd|rd|th)/g, '$1')
  const d = new Date(cleaned)
  return isNaN(d.getTime()) ? null : d
}

function dateOffset(baseDate: string | undefined, dateStr: string | null): number | null {
  if (!baseDate || !dateStr) return null
  const base = new Date(baseDate + 'T00:00:00')
  const date = parseWikiDate(dateStr) ?? new Date(dateStr + 'T00:00:00')
  if (isNaN(base.getTime()) || isNaN(date.getTime())) return null
  return Math.round((date.getTime() - base.getTime()) / (7 * 24 * 60 * 60 * 1000))
}

function nearestLabelIndex(labels: string[], target: Date): number {
  let idx = -1
  let minDiff = Infinity
  for (let i = 0; i < labels.length; i++) {
    const parts = labels[i].split('/')
    const labelDate = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]))
    const diff = Math.abs(labelDate.getTime() - target.getTime())
    if (diff < minDiff) {
      minDiff = diff
      idx = i
    }
  }
  return idx
}

export function ReleaseTimelineChart({
  albumHistory,
  singlesOverlay = [],
  wikiSingles = [],
  albumReleaseDate = '',
  albumTimeline = [],
  advanceSingleRanks = [],
  bestTrackRanks = null,
}: ReleaseTimelineChartProps) {
  const { isDark } = useTheme()
  const base = useMemo(() => buildChartBase(isDark), [isDark])
  const offsetMode = albumHistory.some((e) => typeof e.week_offset === 'number')

  const labels: string[] = []
  const albumRanks: (number | null)[] = []
  const albumPlays: (number | null)[] = []
  const singlesRanks: (number | null)[] = []
  const offsetLabels: number[] = []

  if (offsetMode) {
    const offsets = [
      ...albumHistory.map((e) => e.week_offset).filter((v): v is number => typeof v === 'number'),
      ...albumTimeline.map((e) => e.week_offset),
      ...singlesOverlay.map((e) => e.week_offset).filter((v): v is number => typeof v === 'number'),
      ...advanceSingleRanks.flatMap((s) => s.ranks.map((r) => r.week_offset)),
      ...(bestTrackRanks?.ranks.map((r) => r.week_offset) ?? []),
      0,
    ]
    if (albumReleaseDate) {
      for (const single of wikiSingles) {
        const off = dateOffset(albumReleaseDate, single.date)
        if (off !== null) offsets.push(off)
      }
    }

    if (offsets.length === 0) return null
    const minOffset = Math.min(...offsets)
    const maxOffset = Math.max(...offsets)
    const rankByOffset = new Map(albumHistory.map((e) => [e.week_offset!, e.rank]))
    const playsByOffset = new Map(albumTimeline.map((e) => [e.week_offset, e.play_count]))
    const bestSingleByOffset = new Map(singlesOverlay.map((e) => [e.week_offset!, e.rank]))

    for (let offset = minOffset; offset <= maxOffset; offset++) {
      const historyPoint = albumHistory.find((e) => e.week_offset === offset)
      offsetLabels.push(offset)
      labels.push(offset === 0 ? '发行周' : offset > 0 ? `W+${offset}` : `W${offset}`)
      albumRanks.push(rankByOffset.get(offset) ?? null)
      albumPlays.push(playsByOffset.get(offset) ?? historyPoint?.play_count ?? null)
      singlesRanks.push(bestSingleByOffset.get(offset) ?? null)
    }
  } else {
    const dates = albumHistory
      .map((e) => e.week ? parseWeek(e.week) : null)
      .filter((d): d is Date => d !== null)
      .sort((a, b) => a.getTime() - b.getTime())

    if (dates.length === 0) return null

    const minDate = new Date(dates[0])
    const maxDate = new Date(dates[dates.length - 1])
    const releaseDate = albumReleaseDate ? new Date(albumReleaseDate + 'T00:00:00') : null

    for (const single of wikiSingles) {
      const d = parseWikiDate(single.date)
      if (d && d < minDate) minDate.setTime(d.getTime())
      if (d && d > maxDate) maxDate.setTime(d.getTime())
    }
    if (releaseDate && !isNaN(releaseDate.getTime())) {
      if (releaseDate < minDate) minDate.setTime(releaseDate.getTime())
      if (releaseDate > maxDate) maxDate.setTime(releaseDate.getTime())
    }

    const rankByWeek = new Map(albumHistory.map((e) => [e.week, e.rank]))
    const playsByWeek = new Map(albumHistory.map((e) => [e.week, e.play_count]))
    const singlesByWeek = new Map(singlesOverlay.map((e) => [e.week, e.rank]))
    const current = new Date(minDate)

    while (current <= maxDate) {
      const weekStr = formatWeekISO(current)
      labels.push(formatDateDisplay(current))
      albumRanks.push(rankByWeek.has(weekStr) ? rankByWeek.get(weekStr)! : null)
      albumPlays.push(playsByWeek.has(weekStr) ? playsByWeek.get(weekStr) ?? null : null)
      singlesRanks.push(singlesByWeek.get(weekStr) ?? null)
      current.setDate(current.getDate() + 7)
    }
  }

  const textColor = isDark ? '#A09888' : '#6B5E58'
  const albumRankColor = isDark ? '#D4A84B' : '#B8860B'
  const playColor = isDark ? 'rgba(212, 168, 75, 0.18)' : 'rgba(184, 134, 11, 0.12)'
  const singleLineColor = isDark ? '#7BA587' : '#4A7C59'
  const secondarySingleColor = isDark ? '#D4836F' : '#C84C3D'

  const markLines: MarkLineItem[] = []

  if (offsetMode) {
    const zeroIndex = offsetLabels.indexOf(0)
    if (zeroIndex >= 0) {
      markLines.push({
        name: '专辑发行',
        xAxis: zeroIndex,
        lineStyle: { color: albumRankColor, type: 'solid', width: 1.5, opacity: 0.7 },
        label: { formatter: '专辑发行', position: 'start', fontSize: 10, color: albumRankColor },
      })
    }
    for (const single of wikiSingles) {
      const off = dateOffset(albumReleaseDate, single.date)
      if (off === null) continue
      const idx = offsetLabels.indexOf(off)
      if (idx >= 0) {
        markLines.push({
          name: single.name,
          xAxis: idx,
          lineStyle: { color: singleLineColor, type: 'dotted', width: 1, opacity: 0.5 },
          label: { formatter: single.name, position: 'insideEndTop', fontSize: 9, color: singleLineColor },
        })
      }
    }
  } else {
    const releaseDate = albumReleaseDate ? new Date(albumReleaseDate + 'T00:00:00') : null
    if (releaseDate && !isNaN(releaseDate.getTime())) {
      const idx = nearestLabelIndex(labels, releaseDate)
      if (idx >= 0) {
        markLines.push({
          name: '专辑发行',
          xAxis: idx,
          lineStyle: { color: albumRankColor, type: 'solid', width: 1.5, opacity: 0.7 },
          label: { formatter: '专辑发行', position: 'start', fontSize: 10, color: albumRankColor },
        })
      }
    }
    for (const single of wikiSingles) {
      const d = parseWikiDate(single.date)
      if (!d) continue
      const idx = nearestLabelIndex(labels, d)
      if (idx >= 0) {
        markLines.push({
          name: single.name,
          xAxis: idx,
          lineStyle: { color: singleLineColor, type: 'dotted', width: 1, opacity: 0.5 },
          label: { formatter: single.name, position: 'insideEndTop', fontSize: 9, color: singleLineColor },
        })
      }
    }
  }

  const advanceSeries: ChartSeries[] = offsetMode
    ? advanceSingleRanks.map((single, i) => {
        const byOffset = new Map(single.ranks.map((rank) => [rank.week_offset, rank.rank]))
        return {
          name: `先行曲: ${single.name}`,
          type: 'line',
          yAxisIndex: 0,
          data: offsetLabels.map((offset) => byOffset.get(offset) ?? null),
          connectNulls: false,
          symbol: 'diamond',
          symbolSize: 5,
          lineStyle: { width: 1.3, color: i % 2 === 0 ? singleLineColor : secondarySingleColor, type: 'dotted' },
          itemStyle: { color: i % 2 === 0 ? singleLineColor : secondarySingleColor },
          z: 6,
        }
      })
    : []

  const bestTrackSeries: ChartSeries[] = offsetMode && bestTrackRanks
    ? [{
        name: `最佳走势: ${bestTrackRanks.name}`,
        type: 'line',
        yAxisIndex: 0,
        data: offsetLabels.map((offset) => {
          const match = bestTrackRanks.ranks.find((rank) => rank.week_offset === offset)
          return match?.rank ?? null
        }),
        connectNulls: false,
        symbol: 'triangle',
        symbolSize: 5,
        lineStyle: { width: 1.4, color: secondarySingleColor, type: 'dashed' },
        itemStyle: { color: secondarySingleColor },
        z: 7,
      }]
    : []

  const legendData = ['专辑排名', '最佳单曲排名', '播放量', ...advanceSeries.map((s) => s.name), ...bestTrackSeries.map((s) => s.name)]

  const chartSeries: ChartSeries[] = [
    {
      name: '专辑排名',
      type: 'line',
      yAxisIndex: 0,
      data: albumRanks,
      connectNulls: false,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { width: 2, color: albumRankColor },
      itemStyle: { color: albumRankColor },
      markLine: markLines.length > 0 ? {
        silent: true,
        symbol: 'none',
        animation: false,
        data: markLines,
      } : undefined,
      z: 10,
    },
    {
      name: '最佳单曲排名',
      type: 'line',
      yAxisIndex: 0,
      data: singlesRanks,
      connectNulls: false,
      symbol: 'diamond',
      symbolSize: 6,
      lineStyle: { width: 1.5, color: singleLineColor, type: 'dashed' },
      itemStyle: { color: singleLineColor },
      z: 5,
    },
    ...advanceSeries,
    ...bestTrackSeries,
    {
      name: '播放量',
      type: 'bar',
      yAxisIndex: 1,
      data: albumPlays,
      itemStyle: { color: playColor, borderRadius: [2, 2, 0, 0] },
      barWidth: '70%',
      z: 1,
    },
  ]

  const option: Record<string, unknown> = {
    ...base,
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
    legend: {
      show: true,
      bottom: 0,
      textStyle: { color: textColor, fontSize: 11 },
      data: legendData,
    },
    grid: {
      left: 50,
      right: 55,
      top: 12,
      bottom: legendData.length > 3 ? 64 : markLines.length > 0 ? 44 : 32,
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: textColor } },
      axisLabel: {
        color: textColor,
        fontSize: 10,
        interval: labels.length > 52 ? Math.floor(labels.length / 8) : labels.length > 26 ? Math.floor(labels.length / 6) : 0,
        rotate: labels.length > 26 ? 45 : 0,
      },
    },
    yAxis: [
      {
        type: 'value',
        name: '排名',
        inverse: true,
        min: 1,
        nameTextStyle: { color: textColor, fontSize: 10 },
        axisLabel: { color: textColor, fontSize: 10 },
        axisLine: { show: false },
        splitLine: { show: false },
      },
      {
        type: 'value',
        name: '播放',
        nameTextStyle: { color: textColor, fontSize: 10 },
        axisLabel: { color: textColor, fontSize: 10, formatter: (v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v) },
        axisLine: { show: false },
        splitLine: { show: false },
      },
    ],
    series: chartSeries,
  }

  return (
    <Suspense fallback={<div className="h-[380px] animate-pulse rounded-lg bg-muted/40" />}>
      <ReactECharts option={option} style={{ height: 380, isolation: 'isolate' } as React.CSSProperties} />
    </Suspense>
  )
}
