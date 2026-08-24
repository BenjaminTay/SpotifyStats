import { GlassCard } from '@/components/shared/GlassCard'
import { cn } from '@/lib/utils'
import type { DetailYearEndFields, DetailYearEndHistoryEntry } from '@/types/billboard'
import { formatNumber } from './MusicDetailPrimitives'

const PARTIAL_COVERAGE_LABELS: Partial<Record<DetailYearEndHistoryEntry['coverage_status'], string>> = {
  incomplete: '数据缺口',
  partial_start: '起始不完整',
  year_to_date: '进行中',
  partial_range: '阶段数据',
}

function rankColorClass(rank: number) {
  if (rank === 1) return 'text-accent-foreground'
  if (rank === 2) return 'text-muted-foreground'
  if (rank === 3) return 'text-[#C17A4E] dark:text-[#C97B6B]'
  return 'text-foreground'
}

function Rank({ value, compact = false }: { value: number; compact?: boolean }) {
  return (
    <span
      aria-label={`第 ${value} 名`}
      data-year-end-rank
      className={cn(
        'font-serif font-semibold leading-none tabular-nums',
        compact ? 'text-[20px]' : 'text-[22px]',
        rankColorClass(value),
      )}
    >
      {String(value).padStart(2, '0')}
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
        'inline-flex items-center gap-1.5 rounded-full px-2 py-1 font-sans text-[9px] font-bold leading-none tracking-[0.5px]',
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
  unit: string
  accent?: boolean
}) {
  return (
    <span className={cn('inline-flex items-baseline justify-end gap-1', accent && value > 0 && 'text-accent-foreground')}>
      <span className="font-sans text-[14px] font-semibold tabular-nums">{formatNumber(value)}</span>
      <span className="font-sans text-[9px] font-medium text-muted-foreground">{unit}</span>
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

export function YearEndHistorySection({
  status,
  history,
}: {
  status: DetailYearEndFields['year_end_status']
  history: DetailYearEndHistoryEntry[]
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

  const maxChartPlays = Math.max(...history.map((row) => row.chart_plays), 1)

  return (
    <section className="mb-8" data-year-end-history="ready">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <h3 className="font-serif text-xl font-semibold">年榜历史</h3>
        <p className="font-sans text-[11px] text-muted-foreground">每年最终名次与入榜表现</p>
      </div>

      <div className="space-y-3 md:hidden">
        {history.map((row) => (
          <GlassCard
            key={row.year}
            className={cn(
              'overflow-hidden p-0',
              row.coverage_status === 'year_to_date' && 'border-accent-foreground/20',
            )}
          >
            <div className="flex items-center justify-between gap-3 px-4 pb-3 pt-4">
              <div className="flex min-w-0 items-center gap-2.5">
                <p className="font-serif text-[22px] font-semibold leading-none tracking-[-0.25px] tabular-nums">
                  {row.year}<span className="ml-1 font-sans text-[11px] font-medium tracking-normal text-muted-foreground">年</span>
                </p>
                <CoverageBadge row={row} />
              </div>
              <div className="flex shrink-0 items-baseline gap-2">
                <span className="font-sans text-[9px] font-bold uppercase tracking-[1px] text-muted-foreground">年榜</span>
                <Rank value={row.year_end_rank} />
              </div>
            </div>

            <div className="grid grid-cols-2 border-y border-border/70">
              <div className="border-r border-border/70 px-4 py-3">
                <p className="font-sans text-[9px] font-bold uppercase tracking-[1px] text-muted-foreground">年度积分</p>
                <div className="mt-1"><Metric value={row.year_end_score} unit="分" /></div>
              </div>
              <div className="px-4 py-3">
                <p className="font-sans text-[9px] font-bold uppercase tracking-[1px] text-muted-foreground">上榜播放</p>
                <div className="mt-1.5"><PlaysWithBar value={row.chart_plays} max={maxChartPlays} mobile /></div>
              </div>
            </div>

            <dl className="grid grid-cols-4 px-2 py-3 text-center">
              <div className="border-r border-border/60 px-1">
                <dt className="font-sans text-[9px] text-muted-foreground">周榜峰值</dt>
                <dd className="mt-1"><Rank value={row.peak_position} compact /></dd>
              </div>
              <div className="border-r border-border/60 px-1">
                <dt className="font-sans text-[9px] text-muted-foreground">在榜周数</dt>
                <dd className="mt-1"><Metric value={row.weeks_on_chart} unit="周" /></dd>
              </div>
              <div className="border-r border-border/60 px-1">
                <dt className="font-sans text-[9px] text-muted-foreground">冠军周</dt>
                <dd className="mt-1"><Metric value={row.weeks_at_no1} unit="周" accent /></dd>
              </div>
              <div className="px-1">
                <dt className="font-sans text-[9px] text-muted-foreground">前十周</dt>
                <dd className="mt-1"><Metric value={row.weeks_top10} unit="周" /></dd>
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
              <col className="w-[150px]" />
              <col className="w-[82px]" />
              <col className="w-[112px]" />
              <col className="w-[92px]" />
              <col className="w-[92px]" />
              <col className="w-[88px]" />
              <col className="w-[88px]" />
              <col className="w-[164px]" />
            </colgroup>
            <thead>
              <tr>
                <th className={cn(HEADER_CLASS, 'text-left')}>年度</th>
                <th className={cn(HEADER_CLASS, 'text-right')}>年榜排名</th>
                <th className={cn(HEADER_CLASS, 'text-right')}>年度积分</th>
                <th className={cn(HEADER_CLASS, 'text-right')}>周榜峰值</th>
                <th className={cn(HEADER_CLASS, 'text-right')}>在榜周数</th>
                <th className={cn(HEADER_CLASS, 'text-right')}>冠军周</th>
                <th className={cn(HEADER_CLASS, 'text-right')}>前十周</th>
                <th className={cn(HEADER_CLASS, 'text-right')}>上榜播放</th>
              </tr>
            </thead>
            <tbody>
              {history.map((row) => (
                <tr
                  key={row.year}
                  className={cn(
                    'transition-colors hover:bg-muted/50',
                    row.coverage_status === 'year_to_date' && 'bg-accent-foreground/[0.025]',
                  )}
                >
                  <td className="py-3.5">
                    <div className="flex items-center gap-2.5">
                      <span className="font-serif text-[20px] font-semibold leading-none tracking-[-0.2px] tabular-nums">
                        {row.year}<span className="ml-1 font-sans text-[10px] font-medium tracking-normal text-muted-foreground">年</span>
                      </span>
                      <CoverageBadge row={row} />
                    </div>
                  </td>
                  <td className="py-3.5 text-right"><Rank value={row.year_end_rank} /></td>
                  <td className="py-3.5 text-right"><Metric value={row.year_end_score} unit="分" /></td>
                  <td className="py-3.5 text-right"><Rank value={row.peak_position} compact /></td>
                  <td className="py-3.5 text-right"><Metric value={row.weeks_on_chart} unit="周" /></td>
                  <td className="py-3.5 text-right"><Metric value={row.weeks_at_no1} unit="周" accent /></td>
                  <td className="py-3.5 text-right"><Metric value={row.weeks_top10} unit="周" /></td>
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
