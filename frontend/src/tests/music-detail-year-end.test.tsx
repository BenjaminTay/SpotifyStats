import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { MusicChartOverviewSection } from '@/features/music/details/MusicChartOverviewSection'
import { YearEndHistorySection } from '@/features/music/details/YearEndHistorySection'
import { YearEndSummaryKpis } from '@/features/music/details/YearEndSummaryKpis'
import { TrackOverviewSection } from '@/features/music/details/track/TrackOverviewSection'
import type { DetailYearEndHistoryEntry, TrackDetailResponse } from '@/types/billboard'

vi.mock('@/components/charts/RankTrendChart', () => ({
  RankTrendChart: () => <div data-testid="rank-trend-chart" />,
}))

const history: DetailYearEndHistoryEntry[] = [
  {
    year: 2026,
    year_end_rank: 1,
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
    render(
      <MemoryRouter>
        <YearEndHistorySection status="ready" history={history} kind="artist" bestYear={2025} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '年榜历史' })).toBeInTheDocument()
    expect(screen.queryByText('每年最终名次与入榜表现')).not.toBeInTheDocument()
    expect(screen.getAllByText('2025', { exact: false }).length).toBeGreaterThan(0)
    expect(screen.getAllByLabelText('第 1 名').length).toBeGreaterThan(0)
    expect(screen.queryByText('完整年度')).not.toBeInTheDocument()
    expect(screen.getAllByText('进行中').length).toBeGreaterThan(0)
    const table = screen.getByRole('table', { name: '年榜历史' })
    expect(within(table).queryByRole('columnheader', { name: '覆盖范围' })).not.toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: '年度上榜播放' })).toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: '冠军周数' })).toBeInTheDocument()
    expect(within(table).getByRole('columnheader', { name: '前五周数' })).toBeInTheDocument()
    const tableRows = within(table).getAllByRole('row').slice(1)
    expect(tableRows).toHaveLength(history.length)
    expect(within(tableRows[0]).getAllByRole('cell')[0]).toHaveTextContent('2025')
    expect(within(tableRows[1]).getAllByRole('cell')[0]).toHaveTextContent('2026')
    expect(within(tableRows[0]).getAllByRole('cell')[6]).toHaveTextContent('20')
    expect(within(tableRows[1]).getAllByRole('cell')[6]).toHaveTextContent('7')
    tableRows.forEach((row) => expect(row).not.toHaveTextContent(/[年分周]/))
    expect(
      [...document.querySelectorAll('[data-year-end-card-year]')].map((card) => card.getAttribute('data-year-end-card-year')),
    ).toEqual(['2025', '2026'])
    expect(screen.getAllByText('年度上榜播放')).toHaveLength(history.length + 1)
    expect(screen.getAllByText('冠军周数')).toHaveLength(history.length + 1)
    expect(screen.getAllByText('前五周数')).toHaveLength(history.length + 1)
    expect(table.querySelectorAll('[data-year-end-play-bar]')).toHaveLength(history.length)
    expect(table.querySelector('[data-year-end-rank]')).toHaveClass('font-serif')
    expect(within(tableRows[0]).getByText('PEAK')).toBeInTheDocument()
    expect(within(tableRows[1]).queryByText('PEAK')).not.toBeInTheDocument()
    expect(table.querySelectorAll('[data-year-end-peak-label]')).toHaveLength(1)
    expect(table.querySelectorAll('[data-year-end-rank-anchor]')).toHaveLength(history.length)
    expect(table.querySelector('[data-year-end-peak-label]')?.parentElement).toHaveClass(
      'top-1/2',
      '-translate-y-1/2',
      'items-center',
    )
    expect(document.querySelectorAll('[data-year-end-peak-label]')).toHaveLength(2)
    expect(document.querySelectorAll('[data-year-end-peak-slot]')).toHaveLength(history.length)
    expect(document.querySelector('[data-year-end-peak-slot]')).toHaveClass('items-center', 'self-stretch')
    expect(document.querySelectorAll('[data-year-end-year]')).toHaveLength(history.length * 2)
    expect(table.querySelector('[data-year-end-year]')).toHaveClass('font-sans', 'font-semibold', 'text-[15px]', 'tabular-nums')
    expect(table.querySelector('[data-year-end-year]')).not.toHaveClass('font-serif', 'font-normal')
    expect(document.querySelector('[data-year-end-card-year] [data-year-end-year]')).toHaveClass(
      'min-h-11',
      'min-w-11',
      'font-serif',
      'font-semibold',
      'text-[22px]',
      'tabular-nums',
    )
    expect(document.querySelectorAll('[data-year-end-mobile-score-value]')).toHaveLength(history.length * 4)
    document.querySelectorAll('[data-year-end-mobile-score-value]').forEach((value) => {
      expect(value).toHaveClass('flex', 'h-6', 'items-center', 'justify-center')
    })
    expect(table.querySelector('[data-year-end-peak-label]')).toHaveClass(
      'font-sans',
      'text-[10px]',
      'font-bold',
      'uppercase',
      'tracking-[1px]',
      'relative',
      'top-[3px]',
    )
    expect(table.querySelector('[data-year-end-peak-label]')).not.toHaveClass('rounded-full', 'border')
    expect(document.querySelector('[data-year-end-best-rank]')).not.toBeInTheDocument()
    expect(screen.queryByText('年榜排名趋势')).not.toBeInTheDocument()
  })

  it('keeps warming explicit and unavailable silent', () => {
    const view = render(<YearEndHistorySection status="warming" history={[]} kind="track" />)
    expect(screen.getByText('年榜资料正在后台整理，周榜成绩不受影响。')).toBeInTheDocument()

    view.rerender(<YearEndHistorySection status="unavailable" history={[]} kind="track" />)
    expect(screen.queryByRole('heading', { name: '年榜历史' })).not.toBeInTheDocument()
  })

  it('shows partial-start coverage as an unwrapped incomplete label', () => {
    render(
      <MemoryRouter>
        <YearEndHistorySection
          status="ready"
          kind="album"
          history={[{
            ...history[0],
            year: 2024,
            coverage_status: 'partial_start',
          }]}
        />
      </MemoryRouter>,
    )

    expect(screen.queryByText('起始不完整')).not.toBeInTheDocument()
    expect(screen.queryByText('起始缺')).not.toBeInTheDocument()
    screen.getAllByText('不完整').forEach((badge) => expect(badge).toHaveClass('whitespace-nowrap'))
  })

  it.each([
    ['track', 'tracks', '单曲榜'],
    ['album', 'albums', '专辑榜'],
    ['artist', 'artists', '艺人榜'],
  ] as const)('links %s detail years to the matching Year-End tab', (kind, tab, label) => {
    render(
      <MemoryRouter>
        <YearEndHistorySection status="ready" history={[history[1]]} kind={kind} />
      </MemoryRouter>,
    )

    const links = screen.getAllByRole('link', { name: `查看 2025 年${label}` })
    expect(links).toHaveLength(2)
    links.forEach((link) => {
      expect(link).toHaveAttribute('href', `/billboard/year-end?year=2025&tab=${tab}`)
    })
  })

  it('uses balanced desktop KPI columns with and without a Year-End summary', () => {
    const props = {
      kind: 'artist' as const,
      chartSummary: {
        peak_position: 1,
        peak_weeks: 8,
        first_peak_week: '2025-01-03T00:00:00',
        weeks_on_chart: 40,
        first_week: '2025-01-03T00:00:00',
        latest_week: '2025-12-19T00:00:00',
        power_score: 4200,
        power_rank: 1,
      },
      weeklyHistory: [],
      bestSinglesOverlay: [],
      bestAlbumsOverlay: [],
    }
    const view = render(
      <MusicChartOverviewSection
        {...props}
        yearEndStatus="ready"
        yearEndSummary={{
          best_year: 2025,
          best_rank: 1,
          best_year_is_complete: true,
          latest_year: 2025,
          latest_rank: 1,
          latest_year_is_complete: true,
          ranked_years: 1,
        }}
      />,
    )
    const grid = document.querySelector('[data-music-chart-kpi-grid]')
    expect(grid).toHaveClass('lg:grid-cols-3')
    expect(grid).not.toHaveClass('lg:grid-cols-4')

    view.rerender(
      <MusicChartOverviewSection
        {...props}
        yearEndStatus="unavailable"
        yearEndSummary={null}
      />,
    )
    expect(grid).toHaveClass('lg:grid-cols-4')
    expect(grid).not.toHaveClass('lg:grid-cols-3')
  })

  it('uses entity-aware weekly links and shared cards for track chart KPIs', () => {
    const data: TrackDetailResponse = {
      found: true,
      chart_status: 'charted',
      effective_play_count: 240,
      track_id: 7,
      track_name: 'Chart Song',
      artist_name: 'Chart Artist',
      artist_names: ['Chart Artist'],
      cover_url: null,
      meta: null,
      summary: {
        peak_position: 1,
        weeks_on_chart: 12,
        weeks_at_peak: 3,
        first_week: '2025-01-03',
        last_week: '2025-03-21',
        first_peak_week: '2025-01-10',
        total_chart_plays: 180,
        total_plays: 240,
        weeks_at_no1: 3,
        power_score: 980,
        power_rank: 4,
      },
      history: [{
        week: '2025-01-03',
        rank: 2,
        play_count: 40,
        change: 'NEW',
        running_peak: 2,
        running_wks: 1,
        running_peak_wks: 1,
      }],
      chart_data: { x: [], y: [], texts: [], top_n: 25, peak_position: 1 },
      year_end_status: 'ready',
      year_end_summary: {
        best_year: 2025,
        best_rank: 2,
        best_year_is_complete: true,
        latest_year: 2025,
        latest_rank: 2,
        latest_year_is_complete: true,
        ranked_years: 1,
      },
      year_end_history: [],
    }

    render(
      <MemoryRouter>
        <TrackOverviewSection data={data} />
      </MemoryRouter>,
    )

    const grid = document.querySelector('[data-track-chart-kpi-grid]')
    expect(grid).toHaveClass('grid-cols-2', 'gap-5', 'lg:grid-cols-3')
    expect(grid?.children).toHaveLength(6)
    expect(Array.from(grid?.children ?? []).map((card) => card.textContent)).toEqual([
      expect.stringContaining('最高排名'),
      expect.stringContaining('在榜周数'),
      expect.stringContaining('走势点数'),
      expect.stringContaining('总上榜播放'),
      expect.stringContaining('年榜最佳'),
      expect.stringContaining('年榜入榜'),
    ])
    Array.from(grid?.children ?? []).forEach((card) => {
      expect(card).toHaveClass('rounded-[16px]', 'border', 'bg-card', 'p-5')
    })
    expect(screen.getByText('首次达峰 2025/1/10')).toBeInTheDocument()
    expect(screen.getByText('首次入榜 2025/1/3')).toBeInTheDocument()
    expect(screen.getByText('总播放 240')).toBeInTheDocument()
    expect(screen.getByText('走势排名 #4')).toBeInTheDocument()
    expect(
      Array.from(document.querySelectorAll('a')).map((link) => link.getAttribute('href')),
    ).toContain('/billboard?week=2025-01-03&tab=tracks')
  })

  it.each([
    ['album', 'albums'],
    ['artist', 'artists'],
  ] as const)('links %s weekly history to its matching Billboard tab', (kind, tab) => {
    render(
      <MemoryRouter>
        <MusicChartOverviewSection
          kind={kind}
          chartSummary={{
            peak_position: 2,
            peak_weeks: 1,
            first_peak_week: '2025-01-10',
            weeks_on_chart: 2,
            first_week: '2025-01-03',
            latest_week: '2025-01-10',
            power_score: 120,
            power_rank: 8,
          }}
          weeklyHistory={[{
            week: '2025-01-03',
            rank: 2,
            play_count: 20,
            change: 'NEW',
            running_peak: 2,
            running_wks: 1,
            running_peak_wks: 1,
          }]}
          bestSinglesOverlay={[]}
        />
      </MemoryRouter>,
    )

    expect(
      Array.from(document.querySelectorAll('a')).map((link) => link.getAttribute('href')),
    ).toContain(`/billboard?week=2025-01-03&tab=${tab}`)
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
    expect(screen.queryByText('进入年度年终榜')).not.toBeInTheDocument()
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
