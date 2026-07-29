import { CoverCell } from '@/components/shared/CoverCell'
import { displayName } from '@/lib/chinese'
import type { BillboardYearEndHonors } from '@/types/billboard'
import {
  entityNameForRow,
  formatYearEndNumber,
  type YearEndRow,
  type YearEndTab,
} from './yearEndData'

type HonorKey = keyof BillboardYearEndHonors

const HONORS: { key: HonorKey; label: string; partialLabel: string; tab: YearEndTab }[] = [
  { key: 'year_end_no1_track', label: '年度冠军单曲', partialLabel: '阶段领先单曲', tab: 'tracks' },
  { key: 'year_end_no1_album', label: '年度冠军专辑', partialLabel: '阶段领先专辑', tab: 'albums' },
  { key: 'year_end_no1_artist', label: '年度艺人', partialLabel: '阶段领先艺人', tab: 'artists' },
  { key: 'longest_charting_track', label: '最长在榜单曲', partialLabel: '当前最长在榜单曲', tab: 'tracks' },
  { key: 'biggest_no1_run_track', label: '冠军统治单曲', partialLabel: '当前冠军统治单曲', tab: 'tracks' },
  { key: 'breakthrough_artist', label: '突破艺人', partialLabel: '阶段突破艺人', tab: 'artists' },
]

function rankLabel(rank: number): string {
  return `#${rank}`
}

function detailForHonor(key: string, row: YearEndRow, isCompleteYear: boolean): string {
  const score = `${formatYearEndNumber(row.year_end_score)} pts`
  const peak = `最高 ${rankLabel(row.peak_position)}`
  const weeks = `${formatYearEndNumber(row.weeks_on_chart)} 周`

  if (key === 'year_end_no1_track') {
    return `${score} · ${peak} · Top10 ${formatYearEndNumber(row.weeks_top10)} 周`
  }

  if (key === 'year_end_no1_album' || key === 'year_end_no1_artist') {
    return `${score} · ${peak} · 在榜 ${weeks}`
  }

  if (key === 'longest_charting_track') {
    return `${weeks}在榜 · ${peak} · ${score}`
  }

  if (key === 'biggest_no1_run_track') {
    return `#1 共 ${formatYearEndNumber(row.weeks_at_no1)} 周 · ${score} · 在榜 ${weeks}`
  }

  if (key === 'breakthrough_artist') {
    const debutLabel = isCompleteYear ? '年度首次入榜' : '本阶段首次入榜'
    return `${debutLabel} · ${rankLabel(row.year_end_rank)} · ${score}`
  }

  return `${rankLabel(row.year_end_rank)} · ${score} · 在榜 ${weeks}`
}

export function YearEndHonors({
  honors,
  isCompleteYear = true,
}: {
  honors: BillboardYearEndHonors
  isCompleteYear?: boolean
}) {
  return (
    <section
      className="mb-6 grid gap-3 border-b border-border pb-5 sm:grid-cols-2 lg:grid-cols-3"
      aria-label="Year-End Summary"
    >
      {HONORS.map((honor, index) => {
        const row = honors[honor.key] as YearEndRow | null
        const title = row ? displayName(entityNameForRow(honor.tab, row)) : '无数据'
        return (
          <article
            key={honor.key}
            className="flex min-w-0 items-center gap-3 rounded-[12px] border border-border bg-muted/20 p-3.5 transition-colors hover:bg-muted/40"
          >
            <CoverCell
              index={index}
              coverUrl={row?.cover_url}
              label={title}
            />
            <div className="min-w-0">
              <p className="truncate font-serif text-[18px] font-semibold leading-tight">
                {title}
              </p>
              <p className="mt-1 font-sans text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">
                {isCompleteYear ? honor.label : honor.partialLabel}
              </p>
              {row && (
                <p className="mt-1 truncate font-sans text-[12px] text-muted-foreground">
                  {detailForHonor(honor.key, row, isCompleteYear)}
                </p>
              )}
            </div>
          </article>
        )
      })}
    </section>
  )
}
