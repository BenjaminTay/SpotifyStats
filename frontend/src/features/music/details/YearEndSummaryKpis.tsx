import type { DetailYearEndFields } from '@/types/billboard'
import { KpiCard } from './MusicDetailPrimitives'

type Props = {
  status: DetailYearEndFields['year_end_status']
  summary: DetailYearEndFields['year_end_summary']
  variant: 'plain' | 'cards'
}

function PlainKpi({
  label,
  value,
  sub,
  accent = false,
}: {
  label: string
  value: string
  sub?: string
  accent?: boolean
}) {
  return (
    <div>
      <p className="mb-1.5 font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
        {label}
      </p>
      <p
        className="font-serif text-[36px] font-bold leading-none tracking-[-0.5px]"
        style={accent ? { color: 'var(--accent-foreground)' } : undefined}
      >
        {value}
      </p>
      {sub && <p className="mt-1.5 font-sans text-[11px] text-muted-foreground">{sub}</p>}
    </div>
  )
}

export function YearEndSummaryKpis({ status, summary, variant }: Props) {
  if (status !== 'ready' || !summary) return null

  const bestYearSub = summary.best_year_is_complete
    ? `${summary.best_year} 年`
    : `${summary.best_year} 年 · 阶段年度`
  const rankedYearsValue = `${summary.ranked_years} 年`

  return (
    <>
      {variant === 'cards' ? (
        <>
          <KpiCard
            label="年榜最佳"
            value={`#${summary.best_rank}`}
            sub={bestYearSub}
            accent
          />
          <KpiCard
            label="年榜入榜"
            value={rankedYearsValue}
          />
        </>
      ) : (
        <>
          <PlainKpi label="年榜最佳" value={`#${summary.best_rank}`} sub={bestYearSub} accent />
          <PlainKpi label="年榜入榜" value={rankedYearsValue} />
        </>
      )}
    </>
  )
}
