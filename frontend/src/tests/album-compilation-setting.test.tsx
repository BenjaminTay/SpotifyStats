import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  charts: vi.fn(),
  useApiData: vi.fn(),
  useBillboardWeekly: vi.fn(),
  useSettings: vi.fn(),
}))

vi.mock('@/components/shared/AnalysisControls', () => ({
  EntityTabs: () => <div role="tablist" aria-label="实体类型" />,
  MetricToggle: () => <div role="group" aria-label="统计维度" />,
  useAnalysisQueryState: () => ({
    metric: 'plays',
    entity: 'album',
    setQuery: vi.fn(),
    apiParams: { period: 'lifetime' },
  }),
}))

vi.mock('@/hooks/useAnalysis', () => ({
  useAnalysisFilters: () => ({
    loading: false,
    filters: {
      min_ms: 30000,
      music_only: true,
      merge_enabled: true,
      dynamic_threshold: true,
      merge_level: 2,
      include_compilations: true,
    },
  }),
  analysisApi: {
    charts: (...args: unknown[]) => mocks.charts(...args),
  },
  useApiData: (...args: unknown[]) => mocks.useApiData(...args),
}))

vi.mock('@/hooks/useBillboard', () => ({
  useBillboardWeekly: (...args: unknown[]) => mocks.useBillboardWeekly(...args),
}))

vi.mock('@/hooks/useSettings', () => ({
  useSettings: () => mocks.useSettings(),
}))

import { AnalysisChartsPage } from '@/pages/AnalysisChartsPage'
import { BillboardPage } from '@/pages/BillboardPage'

describe('album compilation global setting', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.charts.mockResolvedValue({
      rows: [],
      total: 0,
      period: { label: '全部时间' },
    })
    mocks.useApiData.mockImplementation((loader) => {
      void loader()
      return {
        data: { rows: [], total: 0, period: { label: '全部时间' } },
        loading: false,
        error: null,
      }
    })
    mocks.useSettings.mockReturnValue({
      settings: { include_compilations: true },
      loading: false,
      error: null,
    })
    mocks.useBillboardWeekly.mockReturnValue({
      data: {
        meta: { all_weeks_desc: ['2026-06-19'] },
        weekly: [],
        weekly_album: [],
        weekly_artist: [],
      },
      loading: false,
      error: null,
      refetch: vi.fn(),
      selectedWeek: '2026-06-19',
      currentWeekData: { tracks: [], albums: [], artists: [] },
      currentIndex: 0,
      totalWeeks: 1,
      goNext: vi.fn(),
      goPrev: vi.fn(),
      goToWeek: vi.fn(),
    })
  })

  it('loads the personal album chart with the settings compilation preference and no local toggle', () => {
    render(<AnalysisChartsPage />)

    expect(screen.queryByRole('button', { name: '包含精选集' })).not.toBeInTheDocument()
    expect(mocks.charts).toHaveBeenCalledWith(
      expect.objectContaining({ include_compilations: true }),
      expect.objectContaining({
        entity: 'album',
        include_compilations: true,
      }),
    )
  })

  it('loads the Billboard weekly chart with the settings compilation preference and no local toggle', () => {
    render(
      <MemoryRouter>
        <BillboardPage />
      </MemoryRouter>,
    )

    expect(screen.queryByLabelText('含精选集')).not.toBeInTheDocument()
    expect(mocks.useBillboardWeekly).toHaveBeenCalledWith(null, 2, true, true)
  })

  it('waits for settings before enabling the Billboard weekly request', () => {
    mocks.useSettings.mockReturnValue({
      settings: null,
      loading: true,
      error: null,
    })

    render(
      <MemoryRouter>
        <BillboardPage />
      </MemoryRouter>,
    )

    expect(mocks.useBillboardWeekly).toHaveBeenCalledWith(null, 2, false, false)
  })
})
