import { Link } from 'react-router-dom'

import { GlassCard } from '@/components/shared/GlassCard'
import { CHART_MOVEMENT_LABEL_CLASS } from '@/components/shared/ChangeCell'
import { cn } from '@/lib/utils'
import type { DetailYearEndFields, DetailYearEndHistoryEntry } from '@/types/billboard'
import { formatNumber } from './MusicDetailPrimitives'

const PARTIAL_COVERAGE_LABELS: Partial<Record<DetailYearEndHistoryEntry['coverage_status'], string>> = {
  incomplete: '数据缺口',
  partial_start: '不完整',
  year_to_date: '进行中',
  partial_range: '阶段数据',
}

function rankColorClass(rank: number) {
  if (rank === 1) return 'text-accent-foreground'
  if (rank === 2) return 'text-muted-foreground'
  if (rank === 3) return 'text-[#C17A4E] dark:text-[#C97B6B]'
  return 'text-foreground'
}

function Rank({
  value,
  compact = false,
}: {
  value: number
  compact?: boolean
}) {
  return (
    <span
      aria-label={`第 ${value} 名`}
      data-year-end-rank
      className={cn(
        'inline-flex font-serif font-semibold leading-none tabular-nums',
        compact ? 'text-[20px]' : 'text-[22px]',
        rankColorClass(value),
      )}
    >
      {String(value).padStart(2, '0')}
    </span>
  )
}

function PeakLabel() {
  return (
    <span
      data-year-end-peak-label
      className={cn(CHART_MOVEMENT_LABEL_CLASS, 'relative top-[3px] whitespace-nowrap text-accent-foreground')}
    >
      PEAK
    </span>
  )
}

function AlignedAnnualRank({ value, isPeak }: { value: number; isPeak: boolean }) {
  return (
    <span
      data-year-end-rank-anchor
      className="relative inline-flex w-7 items-center justify-center"
    >
      <Rank value={value} />
      {isPeak && (
        <span className="absolute left-full top-1/2 ml-1.5 inline-flex -translate-y-1/2 items-center">
          <PeakLabel />
        </span>
      )}
    </span>
  )
}

function CoverageBadge({ row }: { row: DetailYearEndHistoryEntry }) {
  if (row.is_complete_year || row.coverage_status === 'complete') return null
  const label = PARTIAL_COVERAGE_LABELS[row.coverage_status]
  if (!label) return null
  const isOngoing = row.coverage_status === 'year_to_date'
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-1 font-sans text-[9px] font-bold leading-none tracking-[0.5px]',
        isOngoing
          ? 'bg-accent-foreground/10 text-accent-foreground'
          : 'bg-muted text-muted-foreground',
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          'size-1.5 rounded-full',
          isOngoing ? 'bg-accent-foreground' : 'bg-muted-foreground/60',
        )}
      />
      {label}
    </span>
  )
}

function Metric({
  value,
  unit,
  accent = false,
}: {
  value: number
  unit?: string
  accent?: boolean
}) {
  return (
    <span className={cn('inline-flex items-baseline justify-end gap-1', accent && value > 0 && 'text-accent-foreground')}>
      <span className="font-sans text-[14px] font-semibold tabular-nums">{formatNumber(value)}</span>
      {unit && <span className="font-sans text-[9px] font-medium text-muted-foreground">{unit}</span>}
    </span>
  )
}

function PlaysWithBar({ value, max, mobile = false }: { value: number; max: number; mobile?: boolean }) {
  const width = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <span className={cn('inline-flex items-center justify-end gap-2', mobile ? 'w-full' : 'min-w-[136px]')}>
      <span className="font-sans text-[15px] font-semibold tabular-nums">{formatNumber(value)}</span>
      <span
        data-year-end-play-bar
        className={cn('inline-block h-[3px] rounded-[2px] bg-muted align-middle', mobile ? 'min-w-0 flex-1' : 'w-[70px]')}
      >
        <span
          className="block h-full rounded-[2px] bg-accent-foreground transition-[width] duration-300"
          style={{ width: `${width}%` }}
        />
      </span>
    </span>
  )
}

const HEADER_CLASS = 'pb-3.5 pt-4 font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground'
const MOBILE_SCORE_VALUE_CLASS = 'mt-1 flex h-6 items-center justify-center'
const YEAR_END_TAB_BY_KIND = {
  track: { tab: 'tracks', label: '单曲榜' },
  album: { tab: 'albums', label: '专辑榜' },
  artist: { tab: 'artists', label: '艺人榜' },
} as const

type DetailEntityKind = keyof typeof YEAR_END_TAB_BY_KIND

function yearEndHref(year: number, kind: DetailEntityKind) {
  return `/billboard/year-end?year=${year}&tab=${YEAR_END_TAB_BY_KIND[kind].tab}`
}

function yearEndLinkLabel(year: number, kind: DetailEntityKind) {
  return `查看 ${year} 年${YEAR_END_TAB_BY_KIND[kind].label}`
}

export function YearEndHistorySection({
  status,
  history,
  kind,
  bestYear = null,
}: {
  status: DetailYearEndFields['year_end_status']
  history: DetailYearEndHistoryEntry[]
  kind: DetailEntityKind
  bestYear?: number | null
}) {
  if (status === 'unavailable') return null
  if (status === 'warming') {
    return (
      <div className="mb-8" data-year-end-history="warming">
        <h3 className="mb-4 font-serif text-xl font-semibold">年榜历史</h3>
        <GlassCard className="px-5 py-4 text-[13px] text-muted-foreground">
          年榜资料正在后台整理，周榜成绩不受影响。
        </GlassCard>
      </div>
    )
  }
  if (history.length === 0) return null

  const chronologicalHistory = [...history].sort((left, right) => left.year - right.year)
  const maxChartPlays = Math.max(...chronologicalHistory.map((row) => row.chart_plays), 1)

  return (
    <section className="mb-8" data-year-end-history="ready">
      <h3 className="mb-4 font-serif text-xl font-semibold">年榜历史</h3>

      <div className="space-y-3 md:hidden">
        {chronologicalHistory.map((row) => (
          <GlassCard
            key={row.year}
            className={cn(
              'overflow-hidden p-0',
              row.coverage_status === 'year_to_date' && 'border-accent-foreground/20',
            )}
          >
            <div
              data-year-end-card-year={row.year}
              className="flex items-center justify-between gap-3 px-4 pb-3 pt-4"
            >
              <div className="flex min-w-0 items-center gap-2.5">
                <Link
                  to={yearEndHref(row.year, kind)}
                  aria-label={yearEndLinkLabel(row.year, kind)}
                  data-year-end-year
                  className="-my-[11px] inline-flex min-h-11 min-w-11 items-center font-serif text-[22px] font-semibold leading-none tracking-[-0.25px] tabular-nums transition-colors hover:text-accent-foreground focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  {row.year}<span className="ml-1 font-sans text-[11px] font-medium tracking-normal text-muted-foreground">年</span>
                </Link>
                <CoverageBadge row={row} />
              </div>
              <div className="grid shrink-0 grid-cols-[auto_28px_36px] items-center gap-x-1.5">
                <span className="font-sans text-[9px] font-bold uppercase tracking-[1px] text-muted-foreground">年榜</span>
                <span className="inline-flex justify-center">
                  <Rank value={row.year_end_rank} />
                </span>
                <span data-year-end-peak-slot className="inline-flex min-w-9 items-center justify-start self-stretch">
                  {row.year === bestYear && <PeakLabel />}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 border-y border-border/70">
              <div className="border-r border-border/70 px-4 py-3">
                <p className="font-sans text-[9px] font-bold uppercase tracking-[1px] text-muted-foreground">年度积分</p>
                <div className="mt-1"><Metric value={row.year_end_score} unit="分" /></div>
              </div>
              <div className="px-4 py-3">
                <p className="font-sans text-[9px] font-bold uppercase tracking-[1px] text-muted-foreground">年度上榜播放</p>
                <div className="mt-1.5"><PlaysWithBar value={row.chart_plays} max={maxChartPlays} mobile /></div>
              </div>
            </div>

            <dl className="grid grid-cols-4 px-2 py-3 text-center">
              <div className="border-r border-border/60 px-1">
                <dt className="font-sans text-[9px] text-muted-foreground">周榜峰值</dt>
                <dd data-year-end-mobile-score-value className={MOBILE_SCORE_VALUE_CLASS}><Rank value={row.peak_position} compact /></dd>
              </div>
              <div className="border-r border-border/60 px-1">
                <dt className="font-sans text-[9px] text-muted-foreground">在榜周数</dt>
                <dd data-year-end-mobile-score-value className={MOBILE_SCORE_VALUE_CLASS}><Metric value={row.weeks_on_chart} unit="周" /></dd>
              </div>
              <div className="border-r border-border/60 px-1">
                <dt className="font-sans text-[9px] text-muted-foreground">冠军周数</dt>
                <dd data-year-end-mobile-score-value className={MOBILE_SCORE_VALUE_CLASS}><Metric value={row.weeks_at_no1} unit="周" accent /></dd>
              </div>
              <div className="px-1">
                <dt className="font-sans text-[9px] text-muted-foreground">前五周数</dt>
                <dd data-year-end-mobile-score-value className={MOBILE_SCORE_VALUE_CLASS}><Metric value={row.weeks_top5} unit="周" /></dd>
              </div>
            </dl>
          </GlassCard>
        ))}
      </div>

      <GlassCard className="hidden overflow-hidden p-0 md:block">
        <div className="overflow-x-auto">
          <table
            aria-label="年榜历史"
            className="mx-7 my-0 w-[calc(100%-56px)] min-w-[820px] table-fixed border-collapse"
          >
            <colgroup>
              <col className="w-[104px]" />
              <col className="w-[74px]" />
              <col className="w-[126px]" />
              <col className="w-[106px]" />
              <col className="w-[106px]" />
              <col className="w-[100px]" />
              <col className="w-[100px]" />
              <col className="w-[152px]" />
            </colgroup>
            <thead>
              <tr>
                <th className={cn(HEADER_CLASS, 'text-left')}>年度</th>
                <th className={cn(HEADER_CLASS, 'text-center')}>年榜排名</th>
                <th className={cn(HEADER_CLASS, 'text-right')}>年度积分</th>
                <th className={cn(HEADER_CLASS, 'text-right')}>周榜峰值</th>
                <th className={cn(HEADER_CLASS, 'text-right')}>在榜周数</th>
                <th className={cn(HEADER_CLASS, 'text-right')}>冠军周数</th>
                <th className={cn(HEADER_CLASS, 'text-right')}>前五周数</th>
                <th className={cn(HEADER_CLASS, 'text-right')}>年度上榜播放</th>
              </tr>
            </thead>
            <tbody>
              {chronologicalHistory.map((row) => (
                <tr
                  key={row.year}
                  className={cn(
                    'transition-colors hover:bg-muted/50',
                    row.coverage_status === 'year_to_date' && 'bg-accent-foreground/[0.025]',
                  )}
                >
                  <td className="py-3.5">
                    <div className="flex items-center gap-2.5">
                      <Link
                        to={yearEndHref(row.year, kind)}
                        aria-label={yearEndLinkLabel(row.year, kind)}
                        data-year-end-year
                        className="font-sans text-[15px] font-semibold leading-none tabular-nums transition-colors hover:text-accent-foreground focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                      >
                        {row.year}
                      </Link>
                      <CoverageBadge row={row} />
                    </div>
                  </td>
                  <td className="py-3.5 text-center">
                    <AlignedAnnualRank value={row.year_end_rank} isPeak={row.year === bestYear} />
                  </td>
                  <td className="py-3.5 text-right"><Metric value={row.year_end_score} /></td>
                  <td className="py-3.5 text-right"><Rank value={row.peak_position} compact /></td>
                  <td className="py-3.5 text-right"><Metric value={row.weeks_on_chart} /></td>
                  <td className="py-3.5 text-right"><Metric value={row.weeks_at_no1} accent /></td>
                  <td className="py-3.5 text-right"><Metric value={row.weeks_top5} /></td>
                  <td className="py-3.5 text-right">
                    <PlaysWithBar value={row.chart_plays} max={maxChartPlays} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>
    </section>
  )
}
