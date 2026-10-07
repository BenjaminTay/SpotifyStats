import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { EntityStatsPanel } from '@/components/shared/EntityStatsPanel'
import { installDeferredObserver } from './deferred-observer'

const mocks = vi.hoisted(() => ({ get: vi.fn(), phone: false }))
vi.mock('@/lib/api', () => ({ api: { get: mocks.get } }))
vi.mock('@/hooks/useViewportMode', () => ({ useViewportMode: () => mocks.phone ? 'phone' : 'desktop' }))
vi.mock('@/hooks/useAnalysis', () => ({
  useAnalysisFilters: () => ({ filters: { min_ms: 30000 }, loading: false }),
  analysisApi: { entityPlays: vi.fn(), entityPlayDates: vi.fn() },
}))
vi.mock('@/components/shared/RecentPlaysSection', () => ({ RecentPlaysSection: () => null }))
vi.mock('@/components/charts/ListeningClock', () => ({ ListeningClock: () => null }))
vi.mock('@/components/charts/AnalysisCharts', () => ({
  AnalysisTrendChart: ({ data }: { data: unknown }) => <pre data-testid="trend">{JSON.stringify(data)}</pre>,
}))
const stats = {
  found: true, summary: { total_plays: 30, total_hours: 2 },
  daily_metrics: { avg_daily_plays: 15, avg_daily_hours: 1 },
  daily_trend: [{ date: '2026-10-05', plays: 10, hours: 1 }, { date: '2026-10-06', plays: 20, hours: 1 }],
  cumulative_trend: [{ date: '2026-10-05', cumulative_plays: 10, cumulative_hours: 1 }, { date: '2026-10-06', cumulative_plays: 30, cumulative_hours: 2 }],
  hourly_distribution: [], weekday_distribution: [], month_distribution: [], year_distribution: [], recent_plays: [],
}
const nullStats = {
  found: false, summary: null, daily_metrics: null, daily_trend: null, cumulative_trend: null,
  hourly_distribution: null, weekday_distribution: null, month_distribution: null, year_distribution: null, recent_plays: null,
}
function Location() { return <span data-testid="location">{useLocation().search}</span> }
function panel(kind: 'track' | 'album' | 'artist' = 'album') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  const view = render(<QueryClientProvider client={client}><MemoryRouter><Location /><EntityStatsPanel kind={kind} trackId={7} albumName="Afterlife" artistName="Artist" releaseDate="2026-10-06" /></MemoryRouter></QueryClientProvider>)
  const baseKey = () => client.getQueryCache().getAll().find(q => q.queryKey[1] === 'entity-stats' && !(q.queryKey[4] as { include_rank_context?: boolean }).include_rank_context)!.queryKey
  return { ...view, client, setStats: async (value: unknown) => act(async () => { client.setQueryData(baseKey(), value) }) }
}
function noFollowups() {
  expect(mocks.get.mock.calls.some(([path, params]) => path.endsWith('/rankings') || params.include_rank_context)).toBe(false)
  expect(screen.queryByText('总播放次数')).not.toBeInTheDocument()
  expect(screen.queryByTestId('trend')).not.toBeInTheDocument()
}
beforeEach(() => { mocks.get.mockReset(); mocks.phone = false; installDeferredObserver(true) })
describe('详情统计无数据与状态切换', () => {
  it.each(['track', 'album', 'artist'] as const)('%s 的 null 统计显示空态且不请求排名', async kind => {
    mocks.get.mockResolvedValue(nullStats); panel(kind)
    expect(await screen.findByText('暂无个人播放统计。')).toBeInTheDocument(); noFollowups()
    expect(screen.getByRole('button', { name: '播放时长' })).toBeInTheDocument()
  })
  it('最小 found=false 响应保留手机时间入口', async () => {
    mocks.phone = true; mocks.get.mockResolvedValue({ found: false }); panel()
    expect(await screen.findByText('暂无个人播放统计。')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '选择时间范围，当前全部时间' })).toBeInTheDocument(); noFollowups()
  })
  it('loading → 无统计 → 有统计 → 无统计保持 hook 顺序', async () => {
    let resolve!: (value: unknown) => void
    mocks.get.mockImplementation(() => new Promise(r => { resolve = r }))
    const view = panel()
    expect(screen.queryByText('暂无个人播放统计。')).not.toBeInTheDocument()
    await act(async () => resolve(nullStats)); await screen.findByText('暂无个人播放统计。')
    await view.setStats(stats); await screen.findByText('总播放次数')
    await waitFor(() => expect(mocks.get.mock.calls.some(([, p]) => p.include_rank_context)).toBe(true))
    await view.setStats({ found: false })
    expect(await screen.findByText('暂无个人播放统计。')).toBeInTheDocument()
    expect(screen.queryByText('总播放次数')).not.toBeInTheDocument()
  })
  it('503 snapshot_unavailable 保留错误，重试后才显示无统计', async () => {
    mocks.get.mockRejectedValueOnce(new Error('snapshot_unavailable')).mockResolvedValue(nullStats)
    const view = panel()
    expect(await screen.findByText('加载失败：snapshot_unavailable')).toBeInTheDocument()
    expect(screen.queryByText('暂无个人播放统计。')).not.toBeInTheDocument(); noFollowups()
    await act(async () => { await view.client.invalidateQueries() })
    expect(await screen.findByText('暂无个人播放统计。')).toBeInTheDocument()
  })
  it.each(['daily_trend', 'cumulative_trend', 'hourly_distribution', 'weekday_distribution', 'month_distribution', 'year_distribution', 'summary', 'daily_metrics'] as const)('found=true 的 %s=null 明确失败，不补零或发排名请求', async field => {
    mocks.get.mockResolvedValue({ ...stats, [field]: null }); panel()
    expect(await screen.findByText('加载失败：统计响应不完整')).toBeInTheDocument()
    expect(screen.queryByText('暂无个人播放统计。')).not.toBeInTheDocument(); noFollowups()
  })
  it('缺少 found 不冒充实体无统计', async () => {
    mocks.get.mockResolvedValue({ daily_trend: null }); panel()
    expect(await screen.findByText('加载失败：统计响应不完整')).toBeInTheDocument(); noFollowups()
  })
  it.each([30, 0])('合法空数组仍显示真实总量 %i，不显示无统计', async total => {
    mocks.get.mockResolvedValue({ ...stats, summary: { total_plays: total, total_hours: total ? 2 : 0 }, daily_trend: [], cumulative_trend: [] }); panel('track')
    expect(await screen.findByText('总播放次数')).toBeInTheDocument()
    expect(screen.queryByText('暂无个人播放统计。')).not.toBeInTheDocument()
    expect(screen.getAllByTestId('trend')[0]).toHaveTextContent('[]')
  })
  it('正常每日/累计数据保留发行日起点，metric 不重复请求，时间变化传递过滤', async () => {
    mocks.get.mockResolvedValue(stats); panel('track'); await screen.findByText('总播放次数')
    expect(screen.getAllByTestId('trend')[0]).toHaveTextContent('"label":"26-10-06","value":20')
    expect(screen.getAllByTestId('trend')[1]).toHaveTextContent('"label":"26-10-06","value":30')
    await waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(2))
    fireEvent.click(screen.getByRole('button', { name: '播放时长' }))
    expect(screen.getByTestId('location')).toHaveTextContent('metric=hours')
    expect(screen.getAllByTestId('trend')[0]).toHaveTextContent('"value":1'); expect(mocks.get).toHaveBeenCalledTimes(2)
    fireEvent.click(screen.getByRole('button', { name: '最近4周' }))
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ period: 'last_4_weeks' })))
    expect(screen.getByTestId('location')).toHaveTextContent('period=last_4_weeks')
  })
})
