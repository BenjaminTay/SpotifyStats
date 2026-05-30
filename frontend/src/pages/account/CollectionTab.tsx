import { useState, useEffect, useCallback, useRef, lazy, Suspense, useMemo } from 'react'
import { Link } from 'react-router-dom'
import type {
  CollectionInsights,
  ChemistryType,
  LifecycleExample,
  LifecycleTrendPoint,
  TopTrackTrend,
  SaveTimelinePoint,
  TopSavedArtist,
} from '@/types/account'
import { GlassCard } from '@/components/shared/GlassCard'
import { KpiCard } from '@/components/shared/KpiCard'
import { buildChartBase } from '@/components/charts/EChartsTheme'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { useTheme } from '@/hooks/useTheme'
import { displayName, useChineseTextVersion } from '@/lib/chinese'

const ReactECharts = lazy(() => import('echarts-for-react'))

/* ------------------------------------------------------------------ */
/*  Helpers                                                             */
/* ------------------------------------------------------------------ */

function formatDate(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso + (iso.includes('T') ? '' : 'T00:00:00'))
  if (isNaN(d.getTime())) return iso
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

/* ------------------------------------------------------------------ */
/*  1. Collection Personality Hero                                     */
/* ------------------------------------------------------------------ */

function PersonalityHero({ insights }: { insights: CollectionInsights }) {
  const { personality } = insights
  const { metrics } = personality
  const { isDark } = useTheme()

  return (
    <GlassCard className="overflow-hidden p-0">
      <div className={cn(
        'flex flex-col gap-0 bg-gradient-to-br',
        'from-[#f5f0eb] via-[#ede4db] to-[#e8d5c4] text-foreground',
        'dark:from-[#1a1a2e] dark:via-[#16213e] dark:to-[#0f3460] dark:text-white',
      )}>
        {/* Top: icon + name / description vs metrics */}
        <div className="flex flex-col gap-6 p-8 lg:flex-row lg:items-start lg:justify-between">
          {/* Left */}
          <div className="flex-1 space-y-3">
            <span className="text-5xl">{personality.icon}</span>
            <h2 className="font-serif text-4xl font-bold tracking-[-0.5px]">
              {personality.type}
            </h2>
            <p className="max-w-lg font-sans text-sm leading-relaxed text-muted-foreground dark:text-white/70">
              {personality.description}
            </p>
          </div>

          {/* Right: 3 ring metrics */}
          <div className="flex gap-8 lg:gap-12">
            <RingMetric
              label="慢热指数"
              value={metrics.avg_plays_before_save}
              max={20}
              unit="次"
              isDark={isDark}
            />
            <RingMetric
              label="留存率"
              value={metrics.retention_pct}
              max={100}
              unit="%"
              isDark={isDark}
            />
            <RingMetric
              label="冲动收藏"
              value={metrics.impulsive_pct}
              max={100}
              unit="%"
              isDark={isDark}
            />
          </div>
        </div>

        {/* Bottom: 3 key numbers */}
        <div className="grid grid-cols-3 border-t border-black/10 dark:border-white/10">
          <div className="px-8 py-4 text-center">
            <p className="font-serif text-2xl font-bold">
              {metrics.avg_plays_before_save.toFixed(1)}
            </p>
            <p className="font-sans text-xs text-muted-foreground dark:text-white/50">收藏前平均播放</p>
          </div>
          <div className="border-x border-black/10 px-8 py-4 text-center dark:border-white/10">
            <p className="font-serif text-2xl font-bold">
              {metrics.retention_pct.toFixed(0)}%
            </p>
            <p className="font-sans text-xs text-muted-foreground dark:text-white/50">长期留存率</p>
          </div>
          <div className="px-8 py-4 text-center">
            <p className="font-serif text-2xl font-bold">
              {metrics.impulsive_pct.toFixed(0)}%
            </p>
            <p className="font-sans text-xs text-muted-foreground dark:text-white/50">冲动收藏比例</p>
          </div>
        </div>
      </div>
    </GlassCard>
  )
}

/** Pure-CSS ring progress indicator */
function RingMetric({
  label,
  value,
  max,
  unit,
  isDark,
}: {
  label: string
  value: number
  max: number
  unit: string
  isDark: boolean
}) {
  const pct = Math.min((value / max) * 100, 100)

  const fgColor = isDark ? 'rgba(255,255,255,0.85)' : 'rgba(0,0,0,0.55)'
  const bgColor = isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.08)'

  return (
    <div className="flex flex-col items-center gap-1.5">
      {/* Ring */}
      <div
        className="relative flex h-20 w-20 items-center justify-center rounded-full"
        style={{
          background: `conic-gradient(${fgColor} ${pct * 3.6}deg, ${bgColor} ${pct * 3.6}deg)`,
        }}
      >
        <div className={cn(
          'absolute inset-[6px] flex flex-col items-center justify-center rounded-full',
          'bg-[#e8d5c4] dark:bg-[#0f3460]',
        )}>
          <span className="font-serif text-lg font-bold leading-none">
            {value.toFixed(0)}
          </span>
          <span className="-mt-0.5 font-sans text-[10px] text-muted-foreground dark:text-white/60">
            {unit}
          </span>
        </div>
      </div>
      <p className="font-sans text-[11px] font-medium text-muted-foreground dark:text-white/70">{label}</p>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  2. Collection Overview                                             */
/* ------------------------------------------------------------------ */

function CollectionOverviewBlock({
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
        {/* 4 KPI cards - full width row */}
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

        {/* Bar chart + biggest save day */}
        <GlassCard className="p-6">
          <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
            年度收藏量
          </p>
          <SaveTimelineChart timeline={overview.save_timeline} />

          {/* Biggest save day */}
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

/** ECharts dual-axis chart: bars = annual save count, line = cumulative total */
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

  return (
    <Suspense fallback={<div className="animate-pulse rounded-lg bg-muted/40" style={{ height: 240 }} />}>
      <ReactECharts option={option} style={{ height: 240 }} notMerge />
    </Suspense>
  )
}

/* ------------------------------------------------------------------ */
/*  3. First Save Story + Archive Facts                                 */
/* ------------------------------------------------------------------ */

function FirstSaveStoryBlock({
  insights,
}: {
  insights: CollectionInsights
}) {
  const { first_save_story, archive_facts } = insights

  return (
    <section className="space-y-4">
      <h2 className="mb-5 font-serif text-xl font-semibold">
        第一首收藏的故事
      </h2>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Story card */}
        <GlassCard className="border-l-2 border-accent-foreground p-8">
          {first_save_story ? (
            <div className="flex h-full flex-col justify-between space-y-6">
              <div className="space-y-3">
                <div className="flex items-start gap-4">
                  {first_save_story.cover_url && (
                    <img src={first_save_story.cover_url} alt={first_save_story.track_name}
                      className="h-16 w-16 flex-shrink-0 rounded-lg object-cover shadow-sm" />
                  )}
                  <div>
                    <p className="font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
                      {formatDate(first_save_story.save_date)}
                    </p>
                    <p className="font-serif text-lg leading-relaxed mt-1">
                      你收藏了{' '}
                      <span className="font-semibold">
                        {first_save_story.artist_name}
                      </span>{' '}
                      的《
                      <span className="font-semibold">
                        {first_save_story.track_name}
                      </span>
                  》，从此<span className="font-semibold">收藏夹</span>
                      的故事开始了。从那天算起，你一共播放了这首歌{' '}
                      <span className="font-semibold">
                        {first_save_story.total_plays}
                      </span>{' '}
                      次，平均每{' '}
                      <span className="font-semibold">
                        {first_save_story.avg_interval_days.toFixed(1)}
                      </span>{' '}
                      天就回来听一次。
                    </p>
                  </div>
                </div>
              </div>

              {/* Bottom metrics */}
              <div className="grid grid-cols-3 gap-4 rounded-lg bg-muted/40 p-4">
                <div className="text-center">
                  <p className="font-serif text-2xl font-bold tabular-nums">
                    {first_save_story.days_since.toLocaleString()}
                  </p>
                  <p className="font-sans text-[11px] text-muted-foreground">
                    陪伴天数
                  </p>
                </div>
                <div className="text-center">
                  <p className="font-serif text-2xl font-bold tabular-nums">
                    {first_save_story.total_plays.toLocaleString()}
                  </p>
                  <p className="font-sans text-[11px] text-muted-foreground">
                    累计播放
                  </p>
                </div>
                <div className="text-center">
                  <p className="font-serif text-2xl font-bold tabular-nums">
                    {first_save_story.avg_interval_days.toFixed(1)}
                  </p>
                  <p className="font-sans text-[11px] text-muted-foreground">
                    平均间隔 (天)
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center py-12">
              <p className="font-sans text-sm text-muted-foreground">
                暂无第一首收藏的记录
              </p>
            </div>
          )}
        </GlassCard>

        {/* Archive facts */}
        <GlassCard className="p-8">
          <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
            收藏夹档案
          </p>
          <div className="space-y-6">
            <div>
              <p className="font-serif text-4xl font-bold leading-none tabular-nums">
                {archive_facts.total_duration_hrs.toLocaleString()}
              </p>
              <p className="mt-1 font-sans text-sm text-muted-foreground">
                总时长（小时）
              </p>
            </div>
            <div>
              <p className="font-serif text-4xl font-bold leading-none">
                {archive_facts.year_span ?? '--'}
              </p>
              <p className="mt-1 font-sans text-sm text-muted-foreground">
                年代跨度
              </p>
            </div>
            <div>
              {archive_facts.oldest_track ? (
                <>
                  <p className="font-serif text-xl font-semibold leading-tight">
                    {archive_facts.oldest_track.track_name}
                  </p>
                  <p className="mt-0.5 font-sans text-sm text-muted-foreground">
                    {archive_facts.oldest_track.artist_name} &middot;{' '}
                    {archive_facts.oldest_track.year}
                  </p>
                </>
              ) : (
                <p className="font-serif text-xl font-semibold leading-tight text-muted-foreground">
                  无
                </p>
              )}
              <p className="mt-0.5 font-sans text-xs text-muted-foreground">
                最老曲目
              </p>
            </div>
          </div>
        </GlassCard>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  4. Save Lifecycle                                                  */
/* ------------------------------------------------------------------ */

function SaveLifecycleBlock({
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

        {/* Fate card (one year later) */}
        <GlassCard className="flex flex-col p-6">
          <div className="mb-3 h-1.5 w-10 rounded-full bg-emerald-500/70" />
          <p className="font-serif text-lg font-semibold">一年后</p>
          <p className="mt-0.5 font-sans text-xs text-muted-foreground">
            收藏分化结果
          </p>

          {/* Stacked horizontal bar */}
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

      {/* Stage examples */}
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
                        className="h-6 w-6 rounded-full object-cover" />
                    )}
                    <span className="font-sans text-xs font-medium">{ex.track_name}</span>
                    <span className="font-sans text-[10px] text-muted-foreground">{ex.artist_name}</span>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {/* Lifecycle trend chart */}
      {insights.lifecycle_trend && insights.lifecycle_trend.length > 0 && (
        <LifecycleTrendChart
          trend={insights.lifecycle_trend}
          topTracks={insights.lifecycle_top_tracks}
        />
      )}
    </section>
  )
}

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

/* --- Lifecycle trend chart (ECharts) --- */

const TREND_COLORS = ['#e11d48', '#d97706', '#0284c7'] // rose, amber, sky

function LifecycleTrendChart({
  trend,
  topTracks,
}: {
  trend: LifecycleTrendPoint[]
  topTracks?: TopTrackTrend[]
}) {
  const { isDark } = useTheme()
  const base = buildChartBase(isDark)

  // Build week → value maps, then normalize each series to its own peak
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
          name: t.track_name.length > 10 ? t.track_name.slice(0, 10) + '…' : t.track_name,
          data,
          color: TREND_COLORS[ti],
        })
      }
    }

    // Normalize each series to its own peak → 0–100%
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
      <Suspense fallback={<div className="animate-pulse rounded-lg bg-muted/40" style={{ height: 260 }} />}>
        <ReactECharts option={option} style={{ height: 280 }} notMerge />
      </Suspense>
    </GlassCard>
  )
}

/* ------------------------------------------------------------------ */
/*  5. Chemistry (3x2 grid)                                            */
/* ------------------------------------------------------------------ */

function ChemistryBlock({ insights }: { insights: CollectionInsights }) {
  const { chemistry } = insights

  const types: ChemistryType[] = [
    chemistry.love_at_first_listen,
    chemistry.slow_burn,
    chemistry.flash_in_the_pan,
    chemistry.late_bloomer,
    chemistry.steady_favorite,
    chemistry.shelf_sitter,
  ]

  return (
    <section className="space-y-4">
      <h2 className="mb-5 font-serif text-xl font-semibold">
        收藏化学反应
      </h2>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {types.map((chem) => (
          <ChemistryCard
            key={chem.label}
            chem={chem}
            total={chemistry.total_with_dates}
          />
        ))}
      </div>
    </section>
  )
}

function ChemistryCard({
  chem,
  total,
}: {
  chem: ChemistryType
  total: number
}) {
  const examples = chem.examples || []
  const pct = total > 0 ? (chem.count / total) * 100 : 0
  const ITEM_H = 44 // px per row
  const VISIBLE_H = ITEM_H * 2 // 2 songs visible
  const listH = examples.length * ITEM_H

  const scrollKeyframes = `
    @keyframes chem-scroll-${chem.label.replace(/\s/g, '')} {
      0%   { transform: translateY(0); }
      100% { transform: translateY(-${listH}px); }
    }
  `

  return (
    <GlassCard className="flex flex-col p-5">
      <div className="mb-2 flex items-start justify-between">
        <span className="text-3xl">{chem.icon}</span>
        <span className="font-serif text-sm font-bold tabular-nums">
          {chem.count} 首
        </span>
      </div>

      <p className="font-serif text-base font-semibold">{chem.label}</p>
      <p className="mt-0.5 font-sans text-xs leading-relaxed text-muted-foreground">
        {chem.description}
      </p>

      {/* Percentage bar */}
      <div className="mt-3 flex items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-accent-foreground/60"
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="font-sans text-[11px] tabular-nums text-muted-foreground">
          {pct.toFixed(0)}%
        </span>
      </div>

      {/* Vertical scrolling carousel */}
      {examples.length > 0 && (
        <>
          <style>{scrollKeyframes}</style>
          <div className="mt-3 relative overflow-hidden rounded-md bg-muted/30"
               style={{ height: VISIBLE_H }}>
            <div
              className="flex flex-col"
              style={{
                animation: `chem-scroll-${chem.label.replace(/\s/g, '')} ${examples.length * 3}s linear infinite`,
                width: '100%',
              }}
            >
              {/* Render list twice for seamless looping */}
              {[...examples, ...examples].map((ex, i) => (
                <div
                  key={`${ex.track_name}-${ex.artist_name}-${i}`}
                  className="flex items-center gap-2.5 shrink-0"
                  style={{ height: ITEM_H }}
                >
                  {ex.cover_url ? (
                    <img src={ex.cover_url} alt={ex.track_name}
                      className="h-8 w-8 flex-shrink-0 rounded object-cover" />
                  ) : (
                    <div className="h-8 w-8 flex-shrink-0 rounded bg-muted" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="font-sans text-xs font-medium truncate">
                      {ex.track_name}
                    </p>
                    <p className="font-sans text-[11px] text-muted-foreground truncate">
                      {ex.artist_name}
                    </p>
                  </div>
                  {ex.total_plays != null && (
                    <span className="font-sans text-[10px] text-muted-foreground tabular-nums shrink-0">
                      {ex.total_plays}次
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </GlassCard>
  )
}

/* ------------------------------------------------------------------ */
/*  6. Flip Side + Taste Migration                                     */
/* ------------------------------------------------------------------ */

function FlipSideAndMigrationBlock({
  insights,
}: {
  insights: CollectionInsights
}) {
  const { flip_side, keyword_migration, co_saved_artists } = insights
  useChineseTextVersion() // 监听简繁体切换，触发重渲染
  const [page, setPage] = useState(0)
  const perPage = 5
  const totalPages = Math.ceil(flip_side.length / perPage)
  const displayed = flip_side.slice(page * perPage, (page + 1) * perPage)

  return (
    <section className="space-y-4">
      <h2 className="mb-5 font-serif text-xl font-semibold">
        另一面 &middot; 品味迁徙
      </h2>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left: Flip Side */}
        <GlassCard className="p-6">
          <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
            播放最多却没收藏的歌
          </p>

          {displayed.length === 0 ? (
            <p className="py-8 text-center font-sans text-sm text-muted-foreground">
              没有漏网的鱼
            </p>
          ) : (
            <div className="divide-y divide-border">
              {displayed.map((track) => (
                <div
                  key={`${track.track_name}-${track.artist_name}`}
                  className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"
                >
                  {track.cover_url && (
                    <img src={track.cover_url} alt={track.track_name}
                      className="h-9 w-9 flex-shrink-0 rounded object-cover" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="font-sans text-sm font-medium truncate">
                      {track.track_name}
                    </p>
                    <p className="font-sans text-xs text-muted-foreground truncate">
                      {track.artist_name}
                    </p>
                  </div>
                  <span className="ml-3 shrink-0 font-serif text-sm font-bold tabular-nums text-muted-foreground">
                    {track.play_count} 次
                  </span>
                </div>
              ))}
              {totalPages > 1 && (
                <div className="flex items-center justify-between pt-3">
                  <button
                    onClick={() => setPage(p => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="rounded-md px-2 py-0.5 font-sans text-[11px] text-muted-foreground hover:text-foreground transition-colors disabled:opacity-30"
                  >
                    上一页
                  </button>
                  <span className="font-sans text-[11px] text-muted-foreground tabular-nums">
                    {page + 1} / {totalPages}
                  </span>
                  <button
                    onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                    disabled={page >= totalPages - 1}
                    className="rounded-md px-2 py-0.5 font-sans text-[11px] text-muted-foreground hover:text-foreground transition-colors disabled:opacity-30"
                  >
                    下一页
                  </button>
                </div>
              )}
            </div>
          )}
        </GlassCard>

        {/* Right: Taste Migration */}
        <GlassCard className="p-6">
          <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
            品味迁徙
          </p>

          {/* Keyword cloud by year */}
          {Object.keys(keyword_migration).length === 0 ? (
            <p className="py-8 text-center font-sans text-sm text-muted-foreground">
              暂无数据
            </p>
          ) : (
            <div className="mb-5 space-y-3">
              {Object.entries(keyword_migration).map(([year, keywords]) => (
                <div key={year} className="flex items-start gap-3">
                  <span className="shrink-0 font-serif text-sm font-bold">
                    {year}
                  </span>
                  <div className="flex flex-wrap gap-1.5 items-center">
                    {keywords.map((item) => (
                      <span
                        key={item.word}
                        className="rounded-full border border-border bg-muted/40 px-2.5 py-0.5 font-sans text-[12px] leading-relaxed"
                      >
                        {displayName(item.word)}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Co-saved artists (Double Chef Moments) */}
          {co_saved_artists.length > 0 && (
            <>
              <p className="mb-2 font-sans text-[11px] font-semibold uppercase text-muted-foreground">
                双厨时刻
              </p>
              <div className="space-y-1.5">
                {co_saved_artists.slice(0, 5).map((pair) => (
                  <p
                    key={`${pair.artist_a}-${pair.artist_b}`}
                    className="font-sans text-xs text-muted-foreground"
                  >
                    <span className="font-medium text-foreground">
                      {pair.artist_a}
                    </span>{' '}
                    &times;{' '}
                    <span className="font-medium text-foreground">
                      {pair.artist_b}
                    </span>
                    ：{pair.count} 首
                  </p>
                ))}
              </div>
            </>
          )}
        </GlassCard>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/*  7. Leaderboards (Top 10 + Mismatch)                                 */
/* ------------------------------------------------------------------ */

function LeaderboardBlock({ insights }: { insights: CollectionInsights }) {
  const { top_saved_artists, top_saved_albums } = insights

  return (
    <section className="space-y-4">
      <h2 className="mb-5 font-serif text-xl font-semibold">
        排行榜
      </h2>

      <div className="grid grid-cols-1 gap-6">
        {/* Top saved artists */}
        <GlassCard className="p-6">
          <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
            收藏曲目最多的艺人
          </p>

          {top_saved_artists.length === 0 ? (
            <p className="py-8 text-center font-sans text-sm text-muted-foreground">
              暂无数据
            </p>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="pb-2 text-left font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    #
                  </th>
                  <th className="pb-2 text-left font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    艺人
                  </th>
                  <th className="pb-2 text-right font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    收藏
                  </th>
                  <th className="pb-2 text-right font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    播放
                  </th>
                </tr>
              </thead>
              <tbody>
                {top_saved_artists.slice(0, 10).map((artist, idx) => (
                  <tr
                    key={artist.artist_name}
                    className="border-b border-border/50 last:border-0"
                  >
                    <td className="py-2.5 font-serif text-sm font-bold tabular-nums text-muted-foreground">
                      {idx + 1}
                    </td>
                    <td className="py-2.5 flex items-center gap-2.5 min-w-0">
                      {artist.cover_url && (
                        <img src={artist.cover_url} alt={artist.artist_name}
                          className="h-8 w-8 flex-shrink-0 rounded-full object-cover" />
                      )}
                      <span className="font-sans text-sm font-medium truncate">{artist.artist_name}</span>
                    </td>
                    <td className="py-2.5 text-right font-sans text-sm tabular-nums">
                      {artist.saved_count}
                    </td>
                    <td className="py-2.5 text-right font-sans text-sm tabular-nums text-muted-foreground">
                      {artist.total_plays.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </GlassCard>

        {/* Top saved albums */}
        <GlassCard className="p-6">
          <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
            收藏曲目最多的专辑
          </p>

          {top_saved_albums.length === 0 ? (
            <p className="py-8 text-center font-sans text-sm text-muted-foreground">
              暂无数据
            </p>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="pb-2 text-left font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    #
                  </th>
                  <th className="pb-2 text-left font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    专辑
                  </th>
                  <th className="pb-2 text-right font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    收藏
                  </th>
                  <th className="pb-2 text-right font-sans text-[10px] font-semibold uppercase text-muted-foreground">
                    播放
                  </th>
                </tr>
              </thead>
              <tbody>
                {top_saved_albums.slice(0, 10).map((album, idx) => (
                  <tr key={`${album.album_name}-${album.artist_name}`}
                    className="border-b border-border/50 last:border-0">
                    <td className="py-2.5 font-serif text-sm font-bold tabular-nums text-muted-foreground">
                      {idx + 1}
                    </td>
                    <td className="py-2.5 flex items-center gap-2.5 min-w-0">
                      {album.cover_url && (
                        <img src={album.cover_url} alt={album.album_name}
                          className="h-8 w-8 flex-shrink-0 rounded object-cover" />
                      )}
                      <div className="min-w-0">
                        <span className="font-sans text-sm font-medium">{album.album_name}</span>
                        <span className="font-sans text-[11px] text-muted-foreground block">{album.artist_name}</span>
                      </div>
                    </td>
                    <td className="py-2.5 text-right font-sans text-sm tabular-nums">
                      {album.saved_count}
                    </td>
                    <td className="py-2.5 text-right font-sans text-sm tabular-nums text-muted-foreground">
                      {album.total_plays.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </GlassCard>
      </div>
    </section>
  )
}

function _Unused_MismatchTable({ artists }: { artists: TopSavedArtist[] }) {
  return (
    <table className="w-full">
      <thead>
        <tr className="border-b border-border">
          <th className="pb-1.5 text-left font-sans text-[10px] font-semibold uppercase text-muted-foreground">
            艺人
          </th>
          <th className="pb-1.5 text-right font-sans text-[10px] font-semibold uppercase text-muted-foreground">
            收藏
          </th>
          <th className="pb-1.5 text-right font-sans text-[10px] font-semibold uppercase text-muted-foreground">
            播放
          </th>
        </tr>
      </thead>
      <tbody>
        {artists.slice(0, 5).map((artist) => (
          <tr
            key={artist.artist_name}
            className="border-b border-border/50 last:border-0"
          >
            <td className="py-1.5 font-sans text-xs font-medium truncate max-w-[130px]">
              {artist.artist_name}
            </td>
            <td className="py-1.5 text-right font-sans text-xs tabular-nums">
              {artist.saved_count}
            </td>
            <td className="py-1.5 text-right font-sans text-xs tabular-nums text-muted-foreground">
              {artist.total_plays.toLocaleString()}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/* ------------------------------------------------------------------ */
/*  8. Browser (placeholder)                                           */
/* ------------------------------------------------------------------ */

interface SavedTrackRow {
  track_uri: string
  track_name: string
  artist_name: string
  album_name: string
  added_date: string | null
  cover_url?: string | null
}

interface SavedTracksPage {
  page: number
  limit: number
  total: number
  total_pages: number
  tracks: SavedTrackRow[]
}

function SavedTracksBrowser() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [data, setData] = useState<SavedTracksPage | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  // Debounce search
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search)
      setPage(1)
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [search])

  const fetchPage = useCallback(async (p: number, q: string) => {
    setLoading(true)
    setError('')
    try {
      const result = await api.get<SavedTracksPage>(
        `/library/saved-tracks?page=${p}&limit=20&search=${encodeURIComponent(q)}`
      )
      setData(result)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPage(page, debouncedSearch)
  }, [page, debouncedSearch, fetchPage])

  const totalPages = data?.total_pages || 0
  const hasNext = page < totalPages
  const hasPrev = page > 1

  return (
    <GlassCard className="p-4">
        <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
          收藏曲目
        </p>
        {/* Search bar */}
        <div className="mb-4 flex items-center gap-3">
          <div className="relative flex-1">
            <svg
              className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
              fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
            </svg>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索曲目或艺人..."
              className="w-full rounded-lg border border-border bg-background py-1.5 pl-9 pr-3 font-sans text-[13px] placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-accent-foreground"
            />
          </div>
          {data && (
            <span className="font-sans text-[12px] text-muted-foreground">
              {data.total} 首
            </span>
          )}
        </div>

        {/* Table */}
        {loading && (
          <div className="space-y-2 py-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-8 animate-pulse rounded bg-muted" />
            ))}
          </div>
        )}

        {error && (
          <div className="py-8 text-center text-[13px] text-red-500">{error}</div>
        )}

        {!loading && !error && data && (
          <>
            {data.tracks.length === 0 ? (
              <div className="py-8 text-center text-[13px] text-muted-foreground">
                {debouncedSearch ? '没有匹配的曲目' : '暂无收藏曲目'}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full font-sans text-[13px]">
                  <thead>
                    <tr className="border-b border-border text-left text-[11px] font-semibold uppercase tracking-[0.5px] text-muted-foreground">
                      <th className="pb-2 pr-4 w-8"></th>
                      <th className="pb-2 pr-4">曲目</th>
                      <th className="pb-2 pr-4">艺人</th>
                      <th className="pb-2 pr-4 hidden md:table-cell">专辑</th>
                      <th className="pb-2 text-right">收藏日期</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.tracks.map((t) => (
                      <tr key={t.track_uri} className="border-b border-border/50 last:border-b-0">
                        <td className="py-2 pr-1">
                          {t.cover_url ? (
                            <img src={t.cover_url} alt={t.track_name}
                              className="h-8 w-8 rounded object-cover" />
                          ) : (
                            <div className="h-8 w-8 rounded bg-muted" />
                          )}
                        </td>
                        <td className="py-2 pr-4 font-medium">
                          <Link
                            to={`/music/tracks/${t.track_uri.replace('spotify:track:', '')}`}
                            className="hover:text-accent-foreground hover:underline transition-colors"
                          >
                            {t.track_name}
                          </Link>
                        </td>
                        <td className="py-2 pr-4 text-muted-foreground">{t.artist_name}</td>
                        <td className="py-2 pr-4 text-muted-foreground hidden md:table-cell">
                          {t.album_name}
                        </td>
                        <td className="py-2 text-right text-muted-foreground whitespace-nowrap">
                          {t.added_date
                            ? new Date(t.added_date).toLocaleDateString('zh-CN')
                            : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={!hasPrev}
                  className="rounded-md px-3 py-1 font-sans text-[12px] text-muted-foreground transition hover:text-foreground disabled:opacity-30"
                >
                  上一页
                </button>
                <span className="font-sans text-[12px] text-muted-foreground">
                  第 {page} / {totalPages} 页
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={!hasNext}
                  className="rounded-md px-3 py-1 font-sans text-[12px] text-muted-foreground transition hover:text-foreground disabled:opacity-30"
                >
                  下一页
                </button>
              </div>
            )}
          </>
        )}
      </GlassCard>
  )
}

/* ------------------------------------------------------------------ */
/*  9. Playlists Browser                                                */
/* ------------------------------------------------------------------ */

interface PlaylistRow {
  id: number
  name: string
  last_modified: string
  track_count: number
}

interface PlaylistTrackRow {
  track_uri: string
  track_name: string
  artist_name: string
  album_name: string
  added_date: string
  cover_url?: string | null
}

function PlaylistsBrowser() {
  const [playlists, setPlaylists] = useState<PlaylistRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState<number | null>(null)
  const [tracks, setTracks] = useState<PlaylistTrackRow[]>([])
  const [tracksLoading, setTracksLoading] = useState(false)
  const [plPage, setPlPage] = useState(0)
  const PL_PER_PAGE = 10
  const plTotalPages = Math.ceil(playlists.length / PL_PER_PAGE)
  const pagedPlaylists = playlists.slice(plPage * PL_PER_PAGE, (plPage + 1) * PL_PER_PAGE)

  useEffect(() => {
    setLoading(true)
    api.get<PlaylistRow[]>('/library/playlists')
      .then((data) => { setPlaylists(data); setPlPage(0); setLoading(false) })
      .catch((e: unknown) => { setError(e instanceof Error ? e.message : '加载失败'); setLoading(false) })
  }, [])

  const loadTracks = useCallback(async (id: number) => {
    if (expanded === id) {
      setExpanded(null)
      return
    }
    setExpanded(id)
    setTracksLoading(true)
    try {
      const data = await api.get<PlaylistTrackRow[]>(`/library/playlists/${id}/tracks`)
      setTracks(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setTracksLoading(false)
    }
  }, [expanded])

  return (
    <GlassCard className="p-4">
      <p className="mb-4 font-sans text-xs font-semibold uppercase tracking-[1px] text-muted-foreground">
        播放列表
      </p>

      {loading && (
        <div className="space-y-2 py-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-8 animate-pulse rounded bg-muted" />
          ))}
        </div>
      )}

      {error && (
        <div className="py-8 text-center text-[13px] text-red-500">{error}</div>
      )}

      {!loading && !error && playlists.length === 0 && (
        <div className="py-8 text-center text-[13px] text-muted-foreground">
          暂无播放列表
        </div>
      )}

      {!loading && !error && playlists.length > 0 && (
        <>
        <div className="space-y-1">
          {pagedPlaylists.map((pl) => (
            <div key={pl.id}>
              <button
                onClick={() => loadTracks(pl.id)}
                className="w-full flex items-center justify-between rounded-md px-3 py-2 text-left transition hover:bg-muted/50"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-sans text-[13px] font-medium truncate">{pl.name}</p>
                  <p className="font-sans text-[11px] text-muted-foreground">
                    {pl.track_count} 首{pl.last_modified ? ` · ${formatDate(pl.last_modified)}` : ''}
                  </p>
                </div>
                <span className="ml-2 font-sans text-[11px] text-muted-foreground shrink-0">
                  {expanded === pl.id ? '收起' : '展开'}
                </span>
              </button>

              {expanded === pl.id && (
                <div className="ml-3 border-l-2 border-border pl-4 mt-1 mb-2">
                  {tracksLoading ? (
                    <div className="space-y-1 py-2">
                      {[1, 2, 3].map((i) => (
                        <div key={i} className="h-6 animate-pulse rounded bg-muted" />
                      ))}
                    </div>
                  ) : tracks.length === 0 ? (
                    <p className="py-3 text-center font-sans text-[12px] text-muted-foreground">
                      该列表暂无曲目
                    </p>
                  ) : (
                    <div className="max-h-[360px] overflow-y-auto">
                      <table className="w-full font-sans text-[12px]">
                        <thead>
                          <tr className="border-b border-border/50 text-left text-[10px] font-semibold uppercase tracking-[0.5px] text-muted-foreground">
                            <th className="pb-1.5 pr-2 w-7"></th>
                            <th className="pb-1.5 pr-2">曲目</th>
                            <th className="pb-1.5 pr-2">艺人</th>
                            <th className="pb-1.5 pr-2 hidden md:table-cell">专辑</th>
                            <th className="pb-1.5 text-right">加入日期</th>
                          </tr>
                        </thead>
                        <tbody>
                          {tracks.map((t) => (
                            <tr key={t.track_uri} className="border-b border-border/30 last:border-b-0">
                              <td className="py-1 pr-1">
                                {t.cover_url ? (
                                  <img src={t.cover_url} alt={t.track_name}
                                    className="h-7 w-7 rounded object-cover" />
                                ) : (
                                  <div className="h-7 w-7 rounded bg-muted" />
                                )}
                              </td>
                              <td className="py-1 pr-2 font-medium">
                                <Link
                                  to={`/music/tracks/${t.track_uri.replace('spotify:track:', '')}`}
                                  className="hover:text-accent-foreground hover:underline transition-colors"
                                >
                                  {t.track_name}
                                </Link>
                              </td>
                              <td className="py-1 pr-2 text-muted-foreground">{t.artist_name}</td>
                              <td className="py-1 pr-2 text-muted-foreground hidden md:table-cell">
                                {t.album_name}
                              </td>
                              <td className="py-1 text-right text-muted-foreground whitespace-nowrap">
                                {t.added_date
                                  ? formatDate(t.added_date)
                                  : '—'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
        {plTotalPages > 1 && (
          <div className="flex items-center justify-between pt-3 mt-3 border-t border-border/50">
            <button
              onClick={() => setPlPage(p => Math.max(0, p - 1))}
              disabled={plPage === 0}
              className="rounded-md px-2 py-0.5 font-sans text-[11px] text-muted-foreground hover:text-foreground transition-colors disabled:opacity-30"
            >
              上一页
            </button>
            <span className="font-sans text-[11px] text-muted-foreground tabular-nums">
              {plPage + 1} / {plTotalPages}
            </span>
            <button
              onClick={() => setPlPage(p => Math.min(plTotalPages - 1, p + 1))}
              disabled={plPage >= plTotalPages - 1}
              className="rounded-md px-2 py-0.5 font-sans text-[11px] text-muted-foreground hover:text-foreground transition-colors disabled:opacity-30"
            >
              下一页
            </button>
          </div>
        )}
        </>
      )}
    </GlassCard>
  )
}

/* ------------------------------------------------------------------ */
/*  Not Available / Empty states                                       */
/* ------------------------------------------------------------------ */

function NotAvailable() {
  return (
    <GlassCard className="p-12">
      <div className="flex flex-col items-center justify-center space-y-3 text-center">
        <p className="font-serif text-xl font-semibold">暂无收藏数据</p>
        <p className="font-sans text-sm text-muted-foreground">
          你的 Spotify 账号数据中尚未包含收藏记录。请导入账号数据包后查看收藏分析。
        </p>
      </div>
    </GlassCard>
  )
}

/* ------------------------------------------------------------------ */
/*  Main export                                                        */
/* ------------------------------------------------------------------ */

export function CollectionTab({ insights }: { insights: CollectionInsights }) {
  if (!insights.available || insights.empty) {
    return (
      <div className="space-y-6">
        <h2 className="font-serif text-3xl font-bold tracking-tight">
          你的收藏
        </h2>
        <NotAvailable />
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <h2 className="font-serif text-3xl font-bold tracking-tight">
        你的收藏
      </h2>

      {/* 1. Personality Hero */}
      <PersonalityHero insights={insights} />

      {/* 2. Collection Overview */}
      <CollectionOverviewBlock insights={insights} />

      {/* 3. First Save Story + Archive Facts */}
      <FirstSaveStoryBlock insights={insights} />

      {/* 4. Save Lifecycle */}
      <SaveLifecycleBlock insights={insights} />

      {/* 5. Chemistry */}
      <ChemistryBlock insights={insights} />

      {/* 6. Flip Side + Taste Migration */}
      <FlipSideAndMigrationBlock insights={insights} />

      {/* 7. Leaderboards */}
      <LeaderboardBlock insights={insights} />

      {/* 8. Browser: saved tracks + playlists */}
      <section className="space-y-4">
        <h2 className="mb-5 font-serif text-xl font-semibold">浏览器</h2>
        <div className="grid grid-cols-1 gap-6">
          <SavedTracksBrowser />
          <PlaylistsBrowser />
        </div>
      </section>
    </div>
  )
}
