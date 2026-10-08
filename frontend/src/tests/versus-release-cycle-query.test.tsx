import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import { apiClient } from '@/api/client'
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
  vi.spyOn(apiClient, 'postWithParams').mockResolvedValue({ comparisons: [comparisons[0]] })
  const { result } = renderHook(() => useReleaseCycleCompare(albums, {}, true), { wrapper: wrapper() })
  await waitFor(() => expect(result.current.data?.comparisons).toHaveLength(2))
  expect(result.current.data?.comparisons[0].album_name).toBe('Two')
  expect(result.current.data?.comparisons[0].metrics.release_week_plays).toBeUndefined()
  expect(result.current.data?.comparisons[1].metrics.release_week_plays).toBe(10)
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
