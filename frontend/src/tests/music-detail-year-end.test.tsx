import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { YearEndHistorySection } from '@/features/music/details/YearEndHistorySection'
import { YearEndSummaryKpis } from '@/features/music/details/YearEndSummaryKpis'
import type { DetailYearEndHistoryEntry } from '@/types/billboard'

const history: DetailYearEndHistoryEntry[] = [
  {
    year: 2026,
    year_end_rank: 4,
    year_end_score: 1820,
    peak_position: 1,
    weeks_on_chart: 18,
    weeks_at_peak: 2,
    weeks_at_no1: 2,
    weeks_top5: 7,
    weeks_top10: 13,
    chart_plays: 456,
    first_week: '2026-01-02T00:00:00',
    last_week: '2026-08-21T00:00:00',
    coverage_status: 'year_to_date',
    is_complete_year: false,
  },
  {
    year: 2025,
    year_end_rank: 1,
    year_end_score: 4200,
    peak_position: 1,
    weeks_on_chart: 40,
    weeks_at_peak: 8,
    weeks_at_no1: 8,
    weeks_top5: 20,
    weeks_top10: 32,
    chart_plays: 1200,
    first_week: '2025-01-03T00:00:00',
    last_week: '2025-12-19T00:00:00',
    coverage_status: 'complete',
    is_complete_year: true,
  },
]

describe('music detail Year-End surfaces', () => {
  it('renders the annual archive as desktop table and phone cards without a trend chart', () => {
    render(<YearEndHistorySection status="ready" history={history} />)

    expect(screen.getByRole('heading', { name: '年榜历史' })).toBeInTheDocument()
    expect(screen.getAllByText('2025', { exact: false }).length).toBeGreaterThan(0)
    expect(screen.getAllByLabelText('第 1 名').length).toBeGreaterThan(0)
    expect(screen.queryByText('完整年度')).not.toBeInTheDocument()
    expect(screen.getAllByText('进行中').length).toBeGreaterThan(0)
    const table = screen.getByRole('table', { name: '年榜历史' })
    expect(within(table).queryByRole('columnheader', { name: '覆盖范围' })).not.toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: '上榜播放' })).toBeInTheDocument()
    expect(table.querySelectorAll('[data-year-end-play-bar]')).toHaveLength(history.length)
    expect(table.querySelector('[data-year-end-rank]')).toHaveClass('font-serif')
    expect(screen.queryByText('年榜排名趋势')).not.toBeInTheDocument()
  })

  it('keeps warming explicit and unavailable silent', () => {
    const view = render(<YearEndHistorySection status="warming" history={[]} />)
    expect(screen.getByText('年榜资料正在后台整理，周榜成绩不受影响。')).toBeInTheDocument()

    view.rerender(<YearEndHistorySection status="unavailable" history={[]} />)
    expect(screen.queryByRole('heading', { name: '年榜历史' })).not.toBeInTheDocument()
  })

  it('renders best year and ranked-year count as peer KPIs inside chart results', () => {
    render(
      <YearEndSummaryKpis
        status="ready"
        summary={{
          best_year: 2026,
          best_rank: 4,
          best_year_is_complete: false,
          latest_year: 2026,
          latest_rank: 4,
          latest_year_is_complete: false,
          ranked_years: 2,
        }}
        variant="cards"
      />,
    )

    expect(screen.getByText('年榜最佳')).toBeInTheDocument()
    expect(screen.getByText('#4')).toBeInTheDocument()
    expect(screen.getByText('2026 年 · 阶段年度')).toBeInTheDocument()
    expect(screen.getByText('年榜入榜')).toBeInTheDocument()
    expect(screen.getByText('2 年')).toBeInTheDocument()
  })

  it('does not emphasize complete coverage in the best-year KPI', () => {
    render(
      <YearEndSummaryKpis
        status="ready"
        summary={{
          best_year: 2025,
          best_rank: 1,
          best_year_is_complete: true,
          latest_year: 2026,
          latest_rank: 4,
          latest_year_is_complete: false,
          ranked_years: 2,
        }}
        variant="plain"
      />,
    )

    expect(screen.getByText('2025 年')).toBeInTheDocument()
    expect(screen.queryByText('完整年度')).not.toBeInTheDocument()
  })
})
