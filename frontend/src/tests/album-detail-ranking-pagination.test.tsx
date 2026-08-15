import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { EntityStatsPanel } from '@/components/shared/EntityStatsPanel'

const mocks = vi.hoisted(() => ({
  filters: {
    min_ms: 30000,
    music_only: true,
    merge_enabled: true,
    dynamic_threshold: true,
    max_merge_gap_minutes: 5,
  },
  get: vi.fn(),
}))

vi.mock('@/lib/api', () => ({ api: { get: mocks.get } }))
vi.mock('@/hooks/useAnalysis', () => ({
  useAnalysisFilters: () => ({ filters: mocks.filters, loading: false }),
  analysisApi: {
    entityPlays: vi.fn(),
    entityPlayDates: vi.fn(),
  },
}))
vi.mock('@/components/shared/AnalysisControls', () => ({
  MetricToggle: () => <div>指标</div>,
  useAnalysisQueryState: () => ({
    period: 'lifetime',
    metric: 'plays',
    periodValue: 'lifetime',
    startDate: null,
    endDate: null,
    setQuery: vi.fn(),
    apiParams: { period: 'lifetime' },
  }),
}))
vi.mock('@/components/shared/AnalysisTimeRangeSelector', () => ({
  AnalysisTimeRangeSelector: () => <div>时间范围</div>,
}))
vi.mock('@/components/charts/AnalysisCharts', () => ({ AnalysisTrendChart: () => null }))
vi.mock('@/components/charts/ListeningClock', () => ({ ListeningClock: () => null }))
vi.mock('@/components/shared/RecentPlaysSection', () => ({ RecentPlaysSection: () => null }))
vi.mock('@/components/shared/CoverCell', () => ({
  CoverCell: ({ label }: { label: string }) => <span>{label}封面</span>,
}))

const stats = {
  found: true,
  summary: { total_plays: 30, total_hours: 2, unique_tracks: 21, unique_artists: 2, active_days: 2 },
  daily_metrics: { avg_daily_plays: 15, avg_daily_hours: 1, avg_active_day_plays: 15, avg_active_day_hours: 1 },
  hourly_distribution: [],
  daily_trend: [],
  cumulative_trend: [],
  weekday_distribution: [],
  month_distribution: [],
  year_distribution: [],
  recent_plays: [],
}

function rankingRow(rank: number) {
  return {
    rank,
    track_id: rank,
    track_name: `项目歌曲 ${rank}`,
    artist_name: 'Primary Artist',
    artist_names: ['Primary Artist', 'Featured Artist'],
    album_name: 'Merged Project',
    plays: 30 - rank,
    hours: 1,
    first_played: '2026-01-01',
    last_played: '2026-02-01',
    avg_daily_plays: 1,
    avg_daily_hours: 0.1,
    share_pct: 1,
    cover_url: null,
  }
}

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <EntityStatsPanel kind="album" albumName="Merged Project" artistName="Primary Artist" mergeLevel={2} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('专辑详情播放排行分页', () => {
  beforeEach(() => {
    mocks.filters = {
      min_ms: 30000,
      music_only: true,
      merge_enabled: true,
      dynamic_threshold: true,
      max_merge_gap_minutes: 5,
    }
    mocks.get.mockReset()
  })

  it('20首以内保持单页且不显示分页控件', async () => {
    mocks.get.mockImplementation((path: string) => path.endsWith('/rankings')
      ? Promise.resolve({ found: true, entity: 'track', metric: 'plays', total: 20, limit: 20, offset: 0, rows: Array.from({ length: 20 }, (_, index) => rankingRow(index + 1)) })
      : Promise.resolve(stats))
    renderPanel()

    expect(await screen.findByText('项目歌曲 20')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '下一页' })).not.toBeInTheDocument()
  })

  it('超过20首可访问末页，筛选变化后回到第一页', async () => {
    mocks.get.mockImplementation((path: string, params: { offset?: number }) => {
      if (!path.endsWith('/rankings')) return Promise.resolve(stats)
      const offset = params.offset ?? 0
      return Promise.resolve({
        found: true,
        entity: 'track',
        metric: 'plays',
        total: 21,
        limit: 20,
        offset,
        rows: offset === 0
          ? Array.from({ length: 20 }, (_, index) => rankingRow(index + 1))
          : [rankingRow(21)],
      })
    })
    const view = renderPanel()

    await screen.findByText('项目歌曲 20')
    fireEvent.click(screen.getAllByRole('button', { name: '下一页' })[0])
    expect(await screen.findByText('项目歌曲 21')).toBeInTheDocument()
    expect(mocks.get).toHaveBeenCalledWith(
      '/music/albums/Merged%20Project/rankings',
      expect.objectContaining({ artist: 'Primary Artist', merge_level: 2, limit: 20, offset: 20 }),
    )

    mocks.filters = { ...mocks.filters, min_ms: 45000 }
    view.rerender(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <EntityStatsPanel kind="album" albumName="Merged Project" artistName="Primary Artist" mergeLevel={2} />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith(
      '/music/albums/Merged%20Project/rankings',
      expect.objectContaining({ min_ms: 45000, offset: 0 }),
    ))
  })
})
