import { act, render, renderHook, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '@/api/client'
import { ApiError } from '@/api/errors'
import { useVersusPersonal, personalRequestedKey, personalBatchBody } from '@/features/billboard/versus/useVersusPersonal'
import { VersusScoreboardSection } from '@/features/billboard/versus/VersusScoreboardSection'
import { METRIC_DEFS, bestIndices } from '@/features/billboard/versus/versusData'
import type { EntityListItem, VersusEntityData } from '@/types/billboard'
import type { VersusPersonalStats, VersusPersonalRanks } from '@/types/versus-personal'

vi.mock('@/hooks/useViewportMode', () => ({ useViewportMode: () => window.innerWidth < 768 ? 'phone' : 'desktop' }))
const queue: EntityListItem[] = [{ track_id: 1, display: 'One' }, { track_id: 2, display: 'Two' }]
const context = { filter_fingerprint: 'fp', source_revision: 'source-revision-4', statistics_contract_version: 'versus_personal_v1' }
const period = { period: 'lifetime', label: '全部', start_date: '2020-01-01', end_date: '2026-10-01' }
function stats(items = queue): VersusPersonalStats {
  return { ...context, period, entities: items.map((item) => ({ requested_key: personalRequestedKey('track', item), entity_key: `track:${item.track_id}`, found: true, status: 'found', metrics: { total_plays: item.track_id! * 10, total_hours: item.track_id!, active_days: item.track_id!, avg_daily_plays: 10, avg_daily_hours: 1, max_daily_plays: item.track_id! * 3 } })) }
}
function ranks(items = queue): VersusPersonalRanks {
  return { ...context, snapshot: { status: 'ready', freshness: 'current', source_revision: context.source_revision, target_revision: context.source_revision, builder_version: 'entity_rank_context_v2', request_key: 'context-key' }, periods: { lifetime: period, last_6_months: { ...period, period: 'last_6_months' }, last_4_weeks: { ...period, period: 'last_4_weeks' } }, entities: items.map((item) => ({ requested_key: personalRequestedKey('track', item), entity_key: `track:${item.track_id}`, found: true, status: 'found', ranks: { lifetime: item.track_id!, last_6_months: item.track_id!, last_4_weeks: item.track_id! } })) }
}
const charts: VersusEntityData[] = queue.map((item) => ({ name: item.display, cover_url: null, popularity: null, rank_history: [{ week: '2026-09-01', rank: 1, play_count: item.track_id! * 5 }], metrics: Object.fromEntries(METRIC_DEFS.filter((def) => !def.only || def.only === 'track').map((def) => [def.key, item.track_id!])) }))
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } })
  return function Wrapper({ children }: { children: React.ReactNode }) { return <QueryClientProvider client={client}><MemoryRouter>{children}</MemoryRouter></QueryClientProvider> }
}
function Scoreboard({ items = queue, chartData = charts }: { items?: EntityListItem[]; chartData?: VersusEntityData[] | null }) {
  const personal = useVersusPersonal('track', items, { min_ms: 30000 }, true)
  return <VersusScoreboardSection entities={chartData} kind="track" queue={items} buildDetailLink={() => null} personal={personal} />
}
afterEach(() => { vi.restoreAllMocks(); window.innerWidth = 1024 })

describe('bounded comparison requests', () => {
  it('normalizes entity sets and preserves album artist identity', () => {
    expect(personalBatchBody('track', queue)).toEqual(personalBatchBody('track', [...queue].reverse()))
    expect(personalRequestedKey('album', { display: 'Album', album_name: 'same', artist_name: 'A' })).not.toEqual(personalRequestedKey('album', { display: 'Album', album_name: 'same', artist_name: 'B' }))
    expect(bestIndices([10, null], true)).toEqual([])
    expect(bestIndices([0, 4], true)).toEqual([1])
    expect(bestIndices([1, Infinity], false)).toEqual([])
  })
  it('starts both batches together, reorders by requested identity and reuses the set key', async () => {
    const stat = deferred<VersusPersonalStats>(); const rank = deferred<VersusPersonalRanks>()
    const call = vi.spyOn(apiClient, 'postWithParams').mockImplementation((path) => (path.endsWith('personal-stats') ? stat.promise : rank.promise) as Promise<never>)
    const { rerender } = render(<Scoreboard />, { wrapper: wrapper() })
    await waitFor(() => expect(call).toHaveBeenCalledTimes(2))
    expect(screen.getByText('个人播放')).toBeVisible()
    expect(screen.getByText('已完成指标得分')).toBeVisible()
    await act(async () => { stat.resolve(stats()) })
    const row = screen.getByText('个人总播放').closest('tr')!
    await waitFor(() => expect(within(row).getByText('10')).toBeVisible())
    expect(within(row).getByText('20')).toBeVisible()
    expect(screen.queryByText('总分 (胜出指标数)')).not.toBeInTheDocument()
    rerender(<Scoreboard items={[...queue].reverse()} chartData={[...charts].reverse()} />)
    expect(within(screen.getByText('个人总播放').closest('tr')!).getAllByRole('cell').map((cell) => cell.textContent)).toEqual(['20', '10'])
    expect(call).toHaveBeenCalledTimes(2)
    await act(async () => { rank.resolve(ranks()) })
    await waitFor(() => expect(screen.getByText('总分 (胜出指标数)')).toBeVisible())
    expect(call.mock.calls.every(([path, , , , signal]) => path.includes('/billboard/versus/track/personal-') && signal instanceof AbortSignal)).toBe(true)
  })
  it('waits for filters and at least two objects', async () => {
    const call = vi.spyOn(apiClient, 'postWithParams').mockResolvedValue(stats())
    const { rerender } = renderHook(({ items, enabled }) => useVersusPersonal('track', items, {}, enabled), { wrapper: wrapper(), initialProps: { items: queue.slice(0, 1), enabled: true } })
    expect(call).not.toHaveBeenCalled()
    rerender({ items: queue, enabled: false }); expect(call).not.toHaveBeenCalled()
    rerender({ items: queue, enabled: true }); await waitFor(() => expect(call).toHaveBeenCalledTimes(2))
  })
  it('cancels abandoned keys and never exposes old objects after a queue/filter change', async () => {
    const old = deferred<VersusPersonalStats>(); const current = deferred<VersusPersonalStats>()
    const call = vi.spyOn(apiClient, 'postWithParams').mockImplementation((_path, _body, params) => (params.min_ms === 30000 ? old.promise : current.promise) as Promise<never>)
    const { result, rerender } = renderHook(({ items, min }) => useVersusPersonal('track', items, { min_ms: min }, true), { wrapper: wrapper(), initialProps: { items: queue, min: 30000 } })
    await waitFor(() => expect(call).toHaveBeenCalledTimes(2))
    const signal = call.mock.calls[0][4]!
    rerender({ items: [{ track_id: 3, display: 'Three' }, queue[1]], min: 60000 })
    await waitFor(() => expect(call).toHaveBeenCalledTimes(4))
    expect(signal.aborted).toBe(true)
    expect(result.current.stats.data).toBeUndefined()
    // Resolving the abandoned request cannot populate the new key.
    await act(async () => old.resolve(stats()))
    expect(result.current.stats.data).toBeUndefined()
  })
  it('changes types without showing cached track results and sends bounded identities', async () => {
    const call = vi.spyOn(apiClient, 'postWithParams').mockImplementation((path) => path.includes('/track/') ? Promise.resolve(path.endsWith('personal-stats') ? stats() : ranks()) as Promise<never> : new Promise(() => {}))
    const { result, rerender } = renderHook(({ kind, items }: { kind: 'track' | 'album' | 'artist'; items: EntityListItem[] }) => useVersusPersonal(kind, items, { merge_level: 3 }, true), { wrapper: wrapper(), initialProps: { kind: 'track', items: queue } })
    await waitFor(() => expect(result.current.stats.data).toBeDefined())
    rerender({ kind: 'album', items: [{ album_name: 'Same', artist_name: 'A', display: 'A' }, { album_name: 'Same', artist_name: 'B', display: 'B' }] })
    expect(result.current.stats.data).toBeUndefined()
    await waitFor(() => expect(call).toHaveBeenCalledTimes(4))
    expect(call.mock.calls[2][1]).toEqual({ albums: [{ album_name: 'Same', artist_name: 'A' }, { album_name: 'Same', artist_name: 'B' }] })
    rerender({ kind: 'artist', items: [{ artist_name: 'A', display: 'A' }, { artist_name: 'B', display: 'B' }] })
    await waitFor(() => expect(call).toHaveBeenCalledTimes(6))
    expect(call.mock.calls[4][1]).toEqual({ artist_names: ['A', 'B'] })
  })
  it('reads four entities using two bounded batches', async () => {
    const items = [...queue, { track_id: 3, display: 'Three' }, { track_id: 4, display: 'Four' }]
    const call = vi.spyOn(apiClient, 'postWithParams').mockImplementation((path) => Promise.resolve(path.endsWith('personal-stats') ? stats(items) : ranks(items)) as Promise<never>)
    const { result } = renderHook(() => useVersusPersonal('track', items, {}, true), { wrapper: wrapper() })
    await waitFor(() => expect(result.current.ranksData?.entities).toHaveLength(4))
    expect(call).toHaveBeenCalledTimes(2)
    expect(call.mock.calls[0][1]).toEqual({ track_ids: [1, 2, 3, 4] })
  })
  it.each(['source_revision', 'filter_fingerprint', 'statistics_contract_version'] as const)('rejects mismatched %s and refreshes only once', async (field) => {
    const incompatible = { ...ranks(), [field]: 'other' }
    const call = vi.spyOn(apiClient, 'postWithParams').mockImplementation((path) => Promise.resolve(path.endsWith('personal-stats') ? stats() : incompatible) as Promise<never>)
    const { result } = renderHook(() => useVersusPersonal('track', queue, {}, true), { wrapper: wrapper() })
    await waitFor(() => expect(call).toHaveBeenCalledTimes(4))
    await waitFor(() => expect(result.current.ranks.isFetching).toBe(false))
    expect(result.current.mismatched).toBe(true)
    expect(result.current.ranksData).toBeUndefined()
    await new Promise((resolve) => setTimeout(resolve, 30))
    expect(call).toHaveBeenCalledTimes(4)
  })
})

describe('comparison state and scoring', () => {
  it('does not call final score when chart metrics are still missing', async () => {
    vi.spyOn(apiClient, 'postWithParams').mockImplementation((path) => Promise.resolve(path.endsWith('personal-stats') ? stats() : ranks()) as Promise<never>)
    render(<Scoreboard chartData={null} />, { wrapper: wrapper() })
    await waitFor(() => expect(screen.getAllByText('#1')).toHaveLength(3))
    expect(screen.getByText('已完成指标得分')).toBeVisible()
    expect(screen.queryByText('总分 (胜出指标数)')).not.toBeInTheDocument()
  })
  it('keeps available statistics after rank 503, offers a manual retry without automatic requests', async () => {
    let rankReady = false
    const call = vi.spyOn(apiClient, 'postWithParams').mockImplementation((path) => path.endsWith('personal-stats') ? Promise.resolve(stats()) as Promise<never> : rankReady ? Promise.resolve(ranks()) as Promise<never> : Promise.reject(new ApiError(503, 'snapshot_unavailable')))
    render(<Scoreboard />, { wrapper: wrapper() })
    await waitFor(() => expect(screen.getByRole('button', { name: '重试个人排名' })).toBeVisible())
    expect(within(screen.getByText('个人总播放').closest('tr')!).getByText('20')).toBeVisible()
    expect(screen.queryByText('总分 (胜出指标数)')).not.toBeInTheDocument()
    expect(call).toHaveBeenCalledTimes(2)
    rankReady = true
    await userEvent.setup().click(screen.getByRole('button', { name: '重试个人排名' }))
    await waitFor(() => expect(screen.getByText('总分 (胜出指标数)')).toBeVisible())
    expect(call).toHaveBeenCalledTimes(3)
  })
  it('keeps ranks visible when the statistics batch fails and retries only that group', async () => {
    let ready = false
    const call = vi.spyOn(apiClient, 'postWithParams').mockImplementation((path) => path.endsWith('personal-ranks') ? Promise.resolve(ranks()) as Promise<never> : ready ? Promise.resolve(stats()) as Promise<never> : Promise.reject(new ApiError(500, 'failed')))
    render(<Scoreboard />, { wrapper: wrapper() })
    await waitFor(() => expect(screen.getByRole('button', { name: '重试个人播放' })).toBeVisible())
    expect(screen.getAllByText('#1')).toHaveLength(4)
    expect(screen.queryByText('总分 (胜出指标数)')).not.toBeInTheDocument()
    ready = true
    await userEvent.setup().click(screen.getByRole('button', { name: '重试个人播放' }))
    await waitFor(() => expect(screen.getByText('总分 (胜出指标数)')).toBeVisible())
    expect(call).toHaveBeenCalledTimes(3)
  })
  it('does not treat an absent personal rank as zero or a completed row', async () => {
    const data = ranks(); data.entities[1].ranks!.last_4_weeks = null
    vi.spyOn(apiClient, 'postWithParams').mockImplementation((path) => Promise.resolve(path.endsWith('personal-stats') ? stats() : data) as Promise<never>)
    render(<Scoreboard />, { wrapper: wrapper() })
    const row = screen.getByText('近4周排名').closest('tr')!
    await waitFor(() => expect(within(row).getByText('—')).toBeVisible())
    expect(within(row).getByText('#1')).toBeVisible()
    expect(row.querySelector('[style]')).toBeNull()
    expect(screen.getByText('已完成指标得分')).toBeVisible()
  })
  it('preserves true zero but does not award a metric with unavailable or absent opponents', async () => {
    const data = stats(); data.entities[0].metrics!.total_plays = 0
    data.entities[1] = { ...data.entities[1], status: 'unavailable', found: false, metrics: null }
    vi.spyOn(apiClient, 'postWithParams').mockImplementation((path) => Promise.resolve(path.endsWith('personal-stats') ? data : ranks()) as Promise<never>)
    render(<Scoreboard />, { wrapper: wrapper() })
    const row = screen.getByText('个人总播放').closest('tr')!
    await waitFor(() => expect(within(row).getByText('0')).toBeVisible())
    expect(within(row).getByText('暂不可用')).toBeVisible()
    expect(row.querySelector('[style]')).toBeNull()
    expect(screen.getByText('已完成指标得分')).toBeVisible()
  })
  it('keeps phone rows visible before responses and announces no premature overall winner', async () => {
    window.innerWidth = 390
    const stat = deferred<VersusPersonalStats>(); const rank = deferred<VersusPersonalRanks>()
    vi.spyOn(apiClient, 'postWithParams').mockImplementation((path) => (path.endsWith('personal-stats') ? stat.promise : rank.promise) as Promise<never>)
    render(<Scoreboard />, { wrapper: wrapper() })
    expect(screen.getByText('个人播放')).toBeVisible()
    expect(screen.getByRole('heading', { name: '指标尚未齐备' })).toBeVisible()
    await act(async () => { stat.resolve(stats()); rank.resolve(ranks()) })
    await waitFor(() => expect(screen.queryByRole('heading', { name: '指标尚未齐备' })).not.toBeInTheDocument())
    expect(screen.getByText('对决结果')).toBeVisible()
  })
})
