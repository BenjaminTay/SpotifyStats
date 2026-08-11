import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { RankTrendChart } from '@/components/charts/RankTrendChart'
import { EntityStatsPanel } from '@/components/shared/EntityStatsPanel'

const mocks = vi.hoisted(() => ({ get: vi.fn(), setQuery: vi.fn() }))

vi.mock('@/lib/api', () => ({ api: { get: mocks.get } }))
vi.mock('@/hooks/useViewportMode', () => ({ useViewportMode: () => 'phone' }))
vi.mock('@/hooks/useTheme', () => ({ useTheme: () => ({ isDark: false }) }))
vi.mock('@/hooks/useAnalysis', () => ({
  useAnalysisFilters: () => ({ filters: { min_ms: 30000 }, loading: false }),
  analysisApi: { entityPlays: vi.fn(), entityPlayDates: vi.fn() },
}))
vi.mock('@/components/shared/AnalysisControls', () => ({
  MetricToggle: () => <div>图表指标</div>,
  useAnalysisQueryState: () => ({
    period: 'lifetime',
    metric: 'plays',
    periodValue: null,
    startDate: '',
    endDate: '',
    setQuery: mocks.setQuery,
    apiParams: { period: 'lifetime' },
  }),
}))
vi.mock('@/components/shared/AnalysisTimeRangeSelector', () => ({
  AnalysisTimeRangeSelector: () => <div>时间范围</div>,
}))
vi.mock('@/components/shared/RecentPlaysSection', () => ({ RecentPlaysSection: () => null }))
vi.mock('@/components/charts/LazyEChart', () => ({
  LazyEChart: ({ option, style }: {
    option: {
      dataZoom?: Array<{ start?: number; end?: number }>
      series?: Array<{ showSymbol?: boolean }>
    }
    style: { height?: number }
  }) => {
    const zoom = Array.isArray(option.dataZoom) ? option.dataZoom[0] : null
    const series = Array.isArray(option.series) ? option.series[0] : null
    return (
      <div
        data-testid="lazy-echart"
        data-height={style.height}
        data-show-symbol={series?.showSymbol == null ? '' : String(series.showSymbol)}
        data-zoom-start={zoom?.start == null ? '' : String(zoom.start)}
        data-zoom-end={zoom?.end == null ? '' : String(zoom.end)}
      />
    )
  },
}))

const stats = {
  found: true,
  summary: { total_plays: 30, total_hours: 2, unique_tracks: 1, unique_artists: 1, active_days: 2 },
  daily_metrics: { avg_daily_plays: 15, avg_daily_hours: 1, avg_active_day_plays: 15, avg_active_day_hours: 1 },
  first_played: '2026-01-01',
  last_played: '2026-01-02',
  hourly_distribution: [{ hour: 22, plays: 10, hours: 1 }],
  daily_trend: [
    { date: '2026-01-01', plays: 10, hours: 1 },
    { date: '2026-01-02', plays: 20, hours: 1 },
  ],
  cumulative_trend: [
    { date: '2026-01-01', cumulative_plays: 10, cumulative_hours: 1 },
    { date: '2026-01-02', cumulative_plays: 30, cumulative_hours: 2 },
  ],
  weekday_distribution: [{ day: '周四', plays: 10, hours: 1 }],
  month_distribution: [{ month: 1, plays: 30, hours: 2 }],
  year_distribution: [{ year: 2026, plays: 30, hours: 2 }],
  recent_plays: [],
}

function renderStatsPanel(kind: 'track' | 'album' | 'artist' = 'track') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <EntityStatsPanel
          kind={kind}
          trackId={kind === 'track' ? 7 : undefined}
          albumName={kind === 'album' ? 'Detail Album' : undefined}
          artistName={kind === 'track' ? undefined : 'Detail Artist'}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('移动详情图表布局', () => {
  beforeEach(() => {
    mocks.get.mockReset()
    mocks.setQuery.mockReset()
    mocks.get.mockImplementation((path: string) => path.endsWith('/rankings')
      ? Promise.resolve({ found: true, total: 0, rows: [], entity: path.includes('/albums/') ? 'track' : 'album', metric: 'plays' })
      : Promise.resolve(stats))
  })

  it.each(['track', 'album', 'artist'] as const)('%s detail uses the shared mobile time control', async (kind) => {
    renderStatsPanel(kind)
    expect(await screen.findByRole('button', { name: '选择时间范围，当前全部时间' })).toBeInTheDocument()
  })

  it('reuses the playback stats time and metric sheet above detail statistics', async () => {
    renderStatsPanel()

    const trigger = await screen.findByRole('button', { name: '选择时间范围，当前全部时间' })
    expect(trigger).toHaveClass('mobile-time-range-trigger-compact')
    expect(trigger).not.toHaveClass('mobile-time-range-trigger-icon-only')
    expect(trigger.closest('.entity-stats-controls')).toHaveClass('entity-stats-controls-mobile', 'justify-end')
    expect(screen.queryByText('图表指标')).not.toBeInTheDocument()
    expect(screen.queryByText('时间范围')).not.toBeInTheDocument()

    fireEvent.click(trigger)
    const dialog = screen.getByRole('dialog', { name: '时间范围' })
    fireEvent.click(within(dialog).getByRole('radio', { name: '播放时长' }))
    fireEvent.click(within(dialog).getByRole('button', { name: '应用时间范围' }))

    expect(mocks.setQuery).toHaveBeenCalledWith(expect.objectContaining({
      period: 'lifetime',
      metric: 'hours',
    }))
  })

  it('merges trend and distribution charts into switchable compact cards', async () => {
    renderStatsPanel()

    expect(await screen.findByRole('heading', { name: '每日播放' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '累计播放' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '星期分布' })).toBeInTheDocument()
    expect(screen.getAllByTestId('lazy-echart').map((chart) => chart.dataset.height)).toEqual(['220', '216'])
    expect(screen.getByRole('button', { name: '22:00 · 10 次' }).closest('svg')).toHaveStyle({ maxWidth: '216px' })

    fireEvent.click(screen.getByRole('button', { name: '累计' }))
    expect(screen.getByRole('heading', { name: '累计播放' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '每日播放' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '月度' }))
    expect(screen.getByRole('heading', { name: '月度分布' })).toBeInTheDocument()
  })

  it('keeps the full overview sparse and opens detail mode on the latest 26 weeks', () => {
    const start = new Date('2025-01-03T00:00:00Z')
    const data = Array.from({ length: 60 }, (_, index) => {
      const week = new Date(start)
      week.setUTCDate(start.getUTCDate() + index * 7)
      return { week: week.toISOString().slice(0, 10), rank: (index % 30) + 1 }
    })
    render(
      <RankTrendChart
        data={data}
        topN={30}
        compact
        height={248}
        detailWindowSize={26}
        detailWindowPosition="end"
      />,
    )

    expect(screen.getByTestId('lazy-echart')).toHaveAttribute('data-height', '248')
    expect(screen.getByTestId('lazy-echart')).toHaveAttribute('data-show-symbol', 'false')
    expect(screen.getByRole('button', { name: '全貌' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '全貌' })).toHaveClass('rank-trend-mode-button')
    fireEvent.click(screen.getByRole('button', { name: '细节' }))
    expect(screen.getByRole('button', { name: '细节' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByTestId('lazy-echart')).toHaveAttribute('data-show-symbol', 'true')
    expect(Number(screen.getByTestId('lazy-echart').dataset.zoomStart)).toBeCloseTo(56.67, 1)
    expect(screen.getByTestId('lazy-echart')).toHaveAttribute('data-zoom-end', '100')
  })
})
