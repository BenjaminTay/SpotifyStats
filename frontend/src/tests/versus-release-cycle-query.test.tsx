import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import { apiClient } from '@/api/client'
import { SnapshotUnavailableError } from '@/api/errors'
import { useReleaseCycleCompare, useVersus } from '@/hooks/useBillboard'

const albums = [{ artist_name: 'Beta', album_name: 'Two' }, { artist_name: 'Alpha', album_name: 'One' }]
const comparisons = [...albums].reverse().map((item, index) => ({ ...item, release_date: '2020-01-01', label: item.album_name, metrics: { release_week_plays: index + 10 }, album_timeline: [], album_ranks: [] }))
function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  return ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
}
afterEach(() => vi.restoreAllMocks())

it('holds release computation until personal groups settle and reuses the entity set for reorder', async () => {
  const call = vi.spyOn(apiClient, 'postWithParams').mockResolvedValue({ comparisons })
  const { result, rerender } = renderHook(({ items, enabled }) => useReleaseCycleCompare(items, { min_ms: 30000 }, enabled), { wrapper: wrapper(), initialProps: { items: albums, enabled: false } })
  expect(call).not.toHaveBeenCalled()
  rerender({ items: albums, enabled: true })
  await waitFor(() => expect(result.current.data?.comparisons).toHaveLength(2))
  expect(call.mock.calls[0][1]).toEqual({ items: [...albums].reverse(), weeks_before: 12, weeks_after: 24 })
  expect(call.mock.calls[0][4]).toBeInstanceOf(AbortSignal)
  expect(result.current.data?.comparisons.map((item) => item.album_name)).toEqual(['Two', 'One'])
  rerender({ items: [...albums].reverse(), enabled: true })
  expect(result.current.data?.comparisons.map((item) => item.album_name)).toEqual(['One', 'Two'])
  expect(call).toHaveBeenCalledTimes(1)
})
it('keeps missing releases in their requested display column without turning them into zero', async () => {
  vi.spyOn(apiClient, 'postWithParams').mockResolvedValue({ comparisons: [comparisons[0]], unavailable: [{ ...albums[0], status: 'unavailable', reason: 'artist_identity_unconfirmed' }] })
  const { result, rerender } = renderHook(({ items }) => useReleaseCycleCompare(items, {}, true), { wrapper: wrapper(), initialProps: { items: albums } })
  await waitFor(() => expect(result.current.results).toHaveLength(2))
  expect(result.current.data?.comparisons).toHaveLength(1)
  expect(result.current.results[0]).toEqual({ ...albums[0], status: 'unavailable', reason: 'artist_identity_unconfirmed' })
  expect(result.current.results[0]).not.toHaveProperty('metrics')
  expect(result.current.results[1]).toMatchObject({ album_name: 'One', metrics: { release_week_plays: 10 } })
  rerender({ items: [...albums].reverse() })
  expect(result.current.results.map((item) => item.album_name)).toEqual(['One', 'Two'])
  expect(result.current.results[1]).toMatchObject({ status: 'unavailable', reason: 'artist_identity_unconfirmed' })
})
it('keeps all unavailable releases and identifies an omitted response item explicitly', async () => {
  vi.spyOn(apiClient, 'postWithParams').mockResolvedValue({ comparisons: [], unavailable: [{ ...albums[0], status: 'unavailable', reason: 'release_day_unconfirmed' }] })
  const { result } = renderHook(() => useReleaseCycleCompare(albums), { wrapper: wrapper() })
  await waitFor(() => expect(result.current.results).toHaveLength(2))
  expect(result.current.data?.comparisons).toEqual([])
  expect(result.current.results.map((item) => item.status === 'unavailable' ? item.reason : null)).toEqual(['release_day_unconfirmed', 'missing_result'])
})
it('shows snapshot errors and recovers only through an explicit reading retry', async () => {
  const call = vi.spyOn(apiClient, 'postWithParams')
    .mockRejectedValueOnce(new SnapshotUnavailableError({ status: 'snapshot_unavailable', message: 'not ready' } as never))
    .mockResolvedValueOnce({ comparisons })
  const { result } = renderHook(() => useReleaseCycleCompare(albums), { wrapper: wrapper() })
  await waitFor(() => expect(result.current.error).toContain('榜单数据正在准备'))
  expect(result.current.results).toEqual([])
  result.current.refetch()
  await waitFor(() => expect(result.current.results).toHaveLength(2))
  expect(result.current.error).toBeNull()
  expect(call).toHaveBeenCalledTimes(2)
})
it('does not show an old filter result while its replacement is pending', async () => {
  const call = vi.spyOn(apiClient, 'postWithParams').mockResolvedValueOnce({ comparisons }).mockImplementation(() => new Promise(() => {}))
  const { result, rerender } = renderHook(({ min_ms }) => useReleaseCycleCompare(albums, { min_ms }), { wrapper: wrapper(), initialProps: { min_ms: 30000 } })
  await waitFor(() => expect(result.current.results).toHaveLength(2))
  rerender({ min_ms: 60000 })
  expect(result.current.results).toEqual([])
  expect(result.current.loading).toBe(true)
  await waitFor(() => expect(call).toHaveBeenCalledTimes(2))
})
it('cancels abandoned release requests when the entity set changes', async () => {
  const call = vi.spyOn(apiClient, 'postWithParams').mockImplementation(() => new Promise(() => {}))
  const { rerender } = renderHook(({ items }) => useReleaseCycleCompare(items, {}, true), { wrapper: wrapper(), initialProps: { items: albums } })
  await waitFor(() => expect(call).toHaveBeenCalledTimes(1))
  const signal = call.mock.calls[0][4]!
  rerender({ items: [...albums, { artist_name: 'Third', album_name: 'Three' }] })
  await waitFor(() => expect(call).toHaveBeenCalledTimes(2))
  expect(signal.aborted).toBe(true)
})

it('keeps chart and release queries mounted and maps complete results when the queue is reordered', async () => {
  const chartEntities = [...albums].reverse().map((item, index) => ({ name: `${item.album_name} — ${item.artist_name}`, cover_url: null, popularity: null, rank_history: [{ week: '2026-01-01', rank: index + 1, play_count: index + 10 }], metrics: { power_score: index + 100 } }))
  const call = vi.spyOn(apiClient, 'postWithParams').mockImplementation((path) => Promise.resolve(path.endsWith('/compare') ? { comparisons } : { found: true, entities: chartEntities }) as Promise<never>)
  const { result, rerender } = renderHook(({ items }) => {
    const chart = useVersus('album', { albums: items }, {})
    const cycle = useReleaseCycleCompare(items, {}, !!chart.data?.found)
    return { chart, cycle }
  }, { wrapper: wrapper(), initialProps: { items: albums } })
  await waitFor(() => expect(result.current.cycle.data?.comparisons).toHaveLength(2))
  expect(call).toHaveBeenCalledTimes(2)
  expect(call.mock.calls[0][1]).toEqual({ albums: [...albums].reverse() })
  expect(result.current.chart.data?.entities?.map((entity) => [entity.name, entity.metrics?.power_score, entity.rank_history?.[0].play_count])).toEqual([['Two — Beta', 101, 11], ['One — Alpha', 100, 10]])
  rerender({ items: [...albums].reverse() })
  expect(result.current.chart.loading).toBe(false)
  expect(result.current.chart.data?.found).toBe(true)
  expect(result.current.chart.data?.entities?.map((entity) => [entity.name, entity.metrics?.power_score, entity.rank_history?.[0].play_count])).toEqual([['One — Alpha', 100, 10], ['Two — Beta', 101, 11]])
  expect(result.current.cycle.data?.comparisons.map((item) => item.album_name)).toEqual(['One', 'Two'])
  expect(call).toHaveBeenCalledTimes(2)
})
