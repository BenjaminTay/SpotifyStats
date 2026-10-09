import { act, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { EntityStatsPanel } from '@/components/shared/EntityStatsPanel'
import { installDeferredObserver } from './deferred-observer'

const mocks = vi.hoisted(() => ({
  get: vi.fn(), phone: false, period: 'lifetime',
  filters: { min_ms: 30000, music_only: true, merge_enabled: true, dynamic_threshold: true },
}))
vi.mock('@/lib/api', () => ({ api: { get: mocks.get } }))
vi.mock('@/hooks/useViewportMode', () => ({ useViewportMode: () => mocks.phone ? 'phone' : 'desktop' }))
vi.mock('@/hooks/useAnalysis', () => ({ useAnalysisFilters: () => ({ filters: mocks.filters, loading: false }) }))
vi.mock('@/components/shared/AnalysisControls', () => ({
  MetricToggle: () => null,
  useAnalysisQueryState: () => ({ period: mocks.period, periodValue: mocks.period, metric: 'plays', startDate: null, endDate: null, setQuery: vi.fn(), apiParams: { period: mocks.period } }),
}))
vi.mock('@/components/shared/AnalysisTimeRangeSelector', () => ({ AnalysisTimeRangeSelector: () => null }))
vi.mock('@/features/mobile/analysis/MobileAnalysisTimeControl', () => ({ MobileAnalysisTimeControl: () => null }))
vi.mock('@/components/shared/RecentPlaysSection', () => ({ RecentPlaysSection: () => null }))
vi.mock('@/components/charts/ListeningClock', () => ({ ListeningClock: () => null }))
vi.mock('@/components/charts/AnalysisCharts', () => ({ AnalysisTrendChart: () => null }))

const stats = {
  found: true, summary: { total_plays: 30, total_hours: 2 }, daily_metrics: { avg_daily_plays: 15, avg_daily_hours: 1 },
  daily_trend: [], cumulative_trend: [], hourly_distribution: [], weekday_distribution: [], month_distribution: [], year_distribution: [],
}
const ranks = {
  found: true, ranks: { lifetime: 4, last_6_months: 5, last_4_weeks: 6, current_period: 7 },
  top250_counts: { lifetime: 12, last_6_months: 8, last_4_weeks: 3 }, recent_50_count: 2,
}
let observer: ReturnType<typeof installDeferredObserver>
const rankCalls = () => mocks.get.mock.calls.filter(([, params]) => params.include_rank_context)
function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 300000 } } })
  const view = (trackId = '1', mergeLevel = 2) => (
    <QueryClientProvider client={client}><MemoryRouter><EntityStatsPanel kind="track" trackId={trackId} mergeLevel={mergeLevel} /></MemoryRouter></QueryClientProvider>
  )
  return { client, view }
}
beforeEach(() => {
  mocks.phone = false; mocks.period = 'lifetime'; mocks.filters = { min_ms: 30000, music_only: true, merge_enabled: true, dynamic_threshold: true }
  mocks.get.mockReset().mockImplementation((_path, params) => Promise.resolve(params.include_rank_context ? ranks : stats))
  observer = installDeferredObserver()
})
afterEach(() => vi.unstubAllGlobals())

describe('详情全局排名按实际区域可见加载', () => {
  it('Phone 基础统计先显示，排名未进入视口不 GET；滚入后完整保留排名与近期表现', async () => {
    mocks.phone = true
    render(setup().view())
    await screen.findByText('总播放次数')
    expect(rankCalls()).toHaveLength(0)
    observer.enter('[data-deferred="rankings"]')
    expect(rankCalls()).toHaveLength(0)
    const region = document.querySelector('[data-deferred="rank-context"]')!
    const registration = observer.observers.find(item => item.elements.has(region))!
    expect(registration.options?.rootMargin).toBe('0px')
    observer.enter('[data-deferred="rank-context"]')
    await screen.findByText('全时段排名')
    expect(rankCalls()).toHaveLength(1)
    for (const value of ['#4', '#5', '#6', '#7', '12', '8', '3', '2 次']) expect(screen.getByText(value)).toBeInTheDocument()
    observer.enter('[data-deferred="rank-context"]')
    expect(rankCalls()).toHaveLength(1)
  })

  it('Desktop 排名区域已可见时立即请求，不依赖 Phone 或固定延时', async () => {
    observer = installDeferredObserver(true)
    render(setup().view())
    await screen.findByText('全时段排名')
    expect(rankCalls()).toHaveLength(1)
  })

  it.each(['identity', 'filter', 'period', 'merge'] as const)('%s 变化重置可见性资格，中止旧请求且迟到结果不覆盖新上下文', async change => {
    let oldSignal: AbortSignal | undefined
    let resolveOld!: (value: typeof ranks) => void
    mocks.get.mockImplementation((_path, params, _timeout, signal: AbortSignal) => {
      if (!params.include_rank_context) return Promise.resolve(stats)
      if (!oldSignal) {
        oldSignal = signal
        return new Promise(resolve => { resolveOld = resolve })
      }
      return Promise.resolve(ranks)
    })
    const h = setup()
    const rendered = render(h.view())
    await screen.findByText('总播放次数')
    observer.enter('[data-deferred="rank-context"]')
    await waitFor(() => expect(rankCalls()).toHaveLength(1))
    if (change === 'filter') mocks.filters = { ...mocks.filters, min_ms: 45000 }
    if (change === 'period') mocks.period = 'last_4_weeks'
    rendered.rerender(h.view(change === 'identity' ? '2' : '1', change === 'merge' ? 3 : 2))
    await waitFor(() => expect(oldSignal?.aborted).toBe(true))
    await screen.findByText('总播放次数')
    expect(rankCalls()).toHaveLength(1)
    await act(async () => resolveOld({ ...ranks, ranks: { ...ranks.ranks, lifetime: 99 } }))
    expect(screen.queryByText('#99')).not.toBeInTheDocument()
    observer.enter('[data-deferred="rank-context"]')
    await screen.findByText('#4')
    expect(rankCalls()).toHaveLength(2)
    const [path, params] = rankCalls()[1]
    expect(path).toBe(`/music/tracks/l1/${change === 'identity' ? '2' : '1'}/stats`)
    expect(params).toMatchObject({ min_ms: change === 'filter' ? 45000 : 30000, period: change === 'period' ? 'last_4_weeks' : 'lifetime', merge_level: change === 'merge' ? 3 : 2 })
  })

  it('离开统计视图中止已可见排名请求', async () => {
    let signal: AbortSignal | undefined
    mocks.get.mockImplementation((_path, params, _timeout, requestSignal: AbortSignal) => {
      if (!params.include_rank_context) return Promise.resolve(stats)
      signal = requestSignal
      return new Promise(() => {})
    })
    const rendered = render(setup().view())
    await screen.findByText('总播放次数')
    observer.enter('[data-deferred="rank-context"]')
    await waitFor(() => expect(signal).toBeDefined())
    rendered.unmount()
    expect(signal?.aborted).toBe(true)
  })
})
