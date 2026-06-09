import { lazy, Suspense, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertCircle } from 'lucide-react'

import { buildChartBase } from '@/components/charts/EChartsTheme'
import { ArtistLinks } from '@/components/shared/ArtistLinks'
import { GlassCard } from '@/components/shared/GlassCard'
import { Skeleton } from '@/components/ui/skeleton'
import { useTheme } from '@/hooks/useTheme'
import { displayName } from '@/lib/chinese'
import { getChartColors } from '@/lib/theme'
import { billboardDetailLink } from '@/lib/navigation'
import { formatNumber } from './numberOnesData'

const ReactECharts = lazy(() => import('echarts-for-react'))

export function CoverImg({ url }: { url?: string | null }) {
  const [imgError, setImgError] = useState(false)
  useEffect(() => { setImgError(false) }, [url])

  if (url && !imgError) {
    return (
      <img
        src={url}
        alt=""
        className="h-10 w-10 shrink-0 rounded-[8px] object-cover"
        onError={() => setImgError(true)}
        loading="lazy"
      />
    )
  }

  return (
    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[8px] bg-muted text-base">
      🎵
    </div>
  )
}

export function PlayCountCell({ value, max }: { value: number; max: number }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="inline-block w-[52px] text-right font-sans text-[15px] font-semibold tabular-nums">
        {formatNumber(value)}
      </span>
      <span className="inline-block h-[3px] w-[56px] rounded-[2px] bg-muted">
        <span
          className="block h-full rounded-[2px] bg-accent-foreground transition-[width] duration-300"
          style={{ width: `${Math.round((value / (max || 1)) * 100)}%` }}
        />
      </span>
    </span>
  )
}

export function No1BarChart({
  data,
  label,
}: {
  data: { name: string; value: number; subtitle?: string }[]
  label: string
}) {
  const { isDark } = useTheme()
  const base = buildChartBase(isDark)
  const colors = getChartColors(isDark)

  const chartData = [...data].reverse()
  const labels = chartData.map((item) => displayName(item.name))
  const values = chartData.map((item) => item.value)
  const subtitles = chartData.map((item) => (item.subtitle ? displayName(item.subtitle) : ''))

  const option = {
    ...base,
    tooltip: {
      ...base.tooltip,
      formatter: (params: { name: string; value: number; dataIndex: number }) =>
        `<b>${displayName(params.name)}</b><br/>${subtitles[params.dataIndex] ? subtitles[params.dataIndex] + '<br/>' : ''}${label}: ${params.value} 周`,
    },
    xAxis: { type: 'value' as const, ...base.xAxis, axisLabel: { ...base.xAxis.axisLabel } },
    yAxis: {
      type: 'category' as const,
      data: labels,
      ...base.yAxis,
      axisLabel: { ...base.yAxis.axisLabel, width: 160, overflow: 'truncate' },
      splitLine: { show: false },
    },
    series: [
      {
        type: 'bar',
        data: values.map((value) => ({
          value,
          itemStyle: { color: colors[0], borderRadius: [0, 4, 4, 0] },
        })),
        barMaxWidth: 24,
        label: {
          show: true,
          position: 'right',
          color: isDark ? '#A09888' : '#6B5E58',
          fontSize: 11,
          formatter: (params: { value: number }) => `${params.value} 周`,
        },
      },
    ],
    grid: { left: 8, right: 56, top: 8, bottom: 8, containLabel: true },
  }

  return (
    <Suspense fallback={<div className="h-[460px] animate-pulse rounded-lg bg-muted/40" />}>
      <ReactECharts option={option} style={{ height: 460 }} notMerge />
    </Suspense>
  )
}

export function SkeletonBlock() {
  return (
    <>
      <Skeleton className="mb-3 h-3 w-32" />
      <Skeleton className="mb-2 h-[44px] w-72" />
      <Skeleton className="mb-8 h-5 w-48" />
      <div className="mb-8 grid grid-cols-3 gap-6">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index}>
            <Skeleton className="mb-2 h-10 w-20" />
            <Skeleton className="h-4 w-32" />
          </div>
        ))}
      </div>
      <Skeleton className="mb-6 h-[400px] w-full rounded-[16px]" />
      <Skeleton className="mb-6 h-[300px] w-full rounded-[16px]" />
    </>
  )
}

export function ErrorState({ error }: { error: string }) {
  return (
    <div className="flex flex-col items-center gap-4 py-20 text-center">
      <AlertCircle className="h-8 w-8 text-accent-foreground" />
      <p className="font-sans text-[13px] text-muted-foreground">{error}</p>
    </div>
  )
}

export function NameWithCover({
  coverUrl,
  name,
  artistName,
  artistNames,
  nameLink,
  artistLink,
  badge,
}: {
  coverUrl?: string | null
  name: string
  artistName?: string
  artistNames?: string[]
  nameLink: string
  artistLink?: string
  badge?: string
}) {
  return (
    <div className="flex items-center gap-3">
      <CoverImg url={coverUrl} />
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <Link
            to={nameLink}
            className="truncate font-sans text-sm font-semibold transition-colors hover:text-accent-foreground"
          >
            {displayName(name)}
          </Link>
          {badge && (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 font-sans text-[10px] font-semibold uppercase tracking-[0.6px] text-amber-600 dark:text-amber-400">
              {badge}
            </span>
          )}
        </div>
        {artistName &&
          (artistNames && artistNames.length > 1 ? (
            <ArtistLinks
              artistName={artistName}
              artistNames={artistNames}
              className="mt-0.5 block font-sans text-[12px] italic text-muted-foreground"
            />
          ) : artistLink ? (
            <Link
              to={artistLink}
              className="mt-0.5 block font-sans text-[12px] italic text-muted-foreground transition-colors hover:text-accent-foreground"
            >
              {displayName(artistName)}
            </Link>
          ) : (
            <span className="mt-0.5 block font-sans text-[12px] italic text-muted-foreground">
              {displayName(artistName)}
            </span>
          ))}
      </div>
    </div>
  )
}

export function ArtistWithCover({
  coverUrl,
  artistName,
  badge,
}: {
  coverUrl?: string | null
  artistName: string
  badge?: string
}) {
  return (
    <div className="flex items-center gap-3">
      <CoverImg url={coverUrl} />
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <Link
            to={billboardDetailLink(`/music/artists/${encodeURIComponent(artistName)}`)}
            className="block truncate font-sans text-sm font-semibold transition-colors hover:text-accent-foreground"
          >
            {displayName(artistName)}
          </Link>
          {badge && (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 font-sans text-[10px] font-semibold uppercase tracking-[0.6px] text-amber-600 dark:text-amber-400">
              {badge}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

export function AnnualSection({
  title,
  items,
  unit = '首',
}: {
  title: string
  items: { year: number; count: number; songs?: string; albums?: string }[]
  unit?: string
}) {
  if (items.length === 0) return null
  const maxCount = Math.max(...items.map((row) => row.count), 1)
  return (
    <GlassCard className="p-6">
      <h2 className="mb-6 font-serif text-[22px] font-bold tracking-[-0.3px]">{title}</h2>
      <div className="space-y-1">
        {items.map((row) => (
          <div
            key={row.year}
            className="group flex items-start gap-5 rounded-[10px] px-4 py-3.5 transition-colors hover:bg-muted/30"
          >
            <span className="w-[52px] shrink-0 pt-0.5 font-serif text-[28px] font-bold leading-none tracking-[-0.5px]">
              {row.year}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-3">
                <span className="font-sans text-[18px] font-semibold tabular-nums">
                  {row.count} {unit}
                </span>
                <span className="h-[4px] flex-1 rounded-[2px] bg-muted">
                  <span
                    className="block h-full rounded-[2px] bg-accent-foreground/50 transition-[width] duration-500"
                    style={{ width: `${Math.round((row.count / maxCount) * 100)}%` }}
                  />
                </span>
              </div>
              <p className="mt-1.5 font-sans text-[13px] leading-relaxed text-muted-foreground">
                {displayName(row.songs ?? row.albums ?? '')}
              </p>
            </div>
          </div>
        ))}
      </div>
    </GlassCard>
  )
}

export function YearSwitcher({
  availableYears,
  selectedYear,
  uniqueCount,
  unit,
  onYearChange,
}: {
  availableYears: number[]
  selectedYear: number
  uniqueCount: number
  unit: string
  onYearChange: (year: number) => void
}) {
  const index = availableYears.indexOf(selectedYear)
  const prevYear = index < availableYears.length - 1 ? availableYears[index + 1] : null
  const nextYear = index > 0 ? availableYears[index - 1] : null

  return (
    <div className="flex items-center gap-2.5">
      <span className="font-sans text-[12px] text-muted-foreground">
        {uniqueCount} {unit}
      </span>
      <div className="flex items-center gap-0.5 rounded-[8px] border border-border bg-muted/30 p-0.5">
        <button
          onClick={() => prevYear != null && onYearChange(prevYear)}
          disabled={prevYear == null}
          className="inline-flex h-7 w-7 items-center justify-center rounded-[6px] text-[13px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-30"
        >
          ◀
        </button>
        <span className="inline-flex min-w-[48px] items-center justify-center font-serif text-[18px] font-bold tabular-nums">
          {selectedYear}
        </span>
        <button
          onClick={() => nextYear != null && onYearChange(nextYear)}
          disabled={nextYear == null}
          className="inline-flex h-7 w-7 items-center justify-center rounded-[6px] text-[13px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-30"
        >
          ▶
        </button>
      </div>
    </div>
  )
}
