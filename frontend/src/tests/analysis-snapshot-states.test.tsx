import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { SnapshotUnavailableError } from '@/api/errors'
import { AnalysisStatsPage } from '@/pages/AnalysisStatsPage'
import { AnalysisRecordsPage } from '@/pages/AnalysisRecordsPage'

const state = vi.hoisted(() => ({ phone: false, error: null as Error | null }))
vi.mock('@/hooks/useViewportMode', () => ({ useViewportMode: () => state.phone ? 'phone' : 'desktop' }))
vi.mock('@/components/shared/AnalysisControls', () => ({
  useAnalysisQueryState: () => ({ apiParams: {}, period: 'lifetime', metric: 'plays', setQuery: vi.fn() }),
  MetricToggle: () => null,
}))
vi.mock('@/hooks/useAnalysis', () => ({
  useAnalysisFilters: () => ({ filters: { min_ms: 30000, merge_level: 2 }, loading: false }),
  usePreparedAnalysisData: () => ({ data: null, loading: false, switching: false, error: state.error?.message, errorObject: state.error, refetch: vi.fn() }),
  analysisApi: { stats: vi.fn(), records: vi.fn(), prepareSnapshot: vi.fn() },
}))

describe('analysis publication errors', () => {
  it.each([false, true])('separates unavailable from general failure for both routes (phone=%s)', async phone => {
    state.phone = phone
    for (const Page of [AnalysisStatsPage, AnalysisRecordsPage]) {
      for (const unavailable of [true, false]) {
        state.error = unavailable ? new SnapshotUnavailableError({ error: 'snapshot_unavailable', status: 'unavailable', family: 'analysis_stats', message: '当前筛选的数据尚未发布，请稍后重试。' }) : new Error('connection failed')
        const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
        const view = render(<QueryClientProvider client={client}><MemoryRouter><Page /></MemoryRouter></QueryClientProvider>)
        expect(await screen.findByRole('alert')).toHaveTextContent(unavailable ? '暂不可用' : '加载播放')
        expect(screen.queryByText('暂无播放记录')).not.toBeInTheDocument()
        expect(screen.queryByLabelText('正在加载')).not.toBeInTheDocument()
        expect(view.container.querySelector('[data-slot="skeleton"]')).toBeNull()
        expect(screen.queryByLabelText('播放统计核心数据')).not.toBeInTheDocument()
        view.unmount()
        client.clear()
      }
    }
  })
})
