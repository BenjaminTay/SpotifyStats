import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { queryKeys } from '@/api/query-keys'
import { SnapshotUnavailableError } from '@/api/errors'
import { api } from '@/lib/api'
import { useWeeklyProjection, useRecordsProjection, useNumberOnesProjection, useAllTimeProjection } from '@/hooks/useBillboard'

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  return { client, wrapper: ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider> }
}
afterEach(() => vi.restoreAllMocks())
describe('published Billboard page queries', () => {
  it('keeps publication details out of projection errors', async () => {
    const { wrapper } = setup()
    vi.spyOn(api, 'get').mockRejectedValue(new SnapshotUnavailableError({
      error: 'snapshot_unavailable', status: 'unavailable', family: 'billboard', message: '当前筛选的数据尚未发布，请稍后重试。',
    }))
    const { result } = renderHook(() => useRecordsProjection({ merge_level: 2 }), { wrapper })
    await waitFor(() => expect(result.current.error).toBe('榜单数据正在准备，请稍后重新加载。'))
    expect(result.current.error).not.toContain('发布')
  })
  it('isolates every response parameter in the query key', () => {
    const base = { entity: 'tracks', week: '2026-01-02', page: 1, page_size: 50, sort: 'power_score', direction: 'desc', peak_filter: 'all', search: '', merge_level: 2, min_ms: 30000, bb_top_n: 30 }
    const key = JSON.stringify(queryKeys.billboard.projection('weekly', base))
    for (const field of Object.keys(base)) expect(JSON.stringify(queryKeys.billboard.projection('weekly', { ...base, [field]: 'different' }))).not.toBe(key)
  })
  it('keeps a late previous week from overwriting the selected tab and cancels its transport', async () => {
    const { wrapper } = setup()
    let resolveOld: (value: unknown) => void = () => {}
    const get = vi.spyOn(api, 'get').mockImplementation((_url, params) => params?.week === 'old'
      ? new Promise(resolve => { resolveOld = resolve }) : Promise.resolve({ selected_week: 'new', entity: 'albums' }))
    const { result, rerender } = renderHook(({ week, tab }) => useWeeklyProjection({ merge_level: 2 }, week, tab), { wrapper, initialProps: { week: 'old', tab: 'tracks' } })
    await waitFor(() => expect(get).toHaveBeenCalledTimes(1))
    const signal = get.mock.calls[0][3]
    rerender({ week: 'new', tab: 'albums' })
    await waitFor(() => expect(result.current.data?.selected_week).toBe('new'))
    expect(signal?.aborted).toBe(true)
    await act(async () => resolveOld({ selected_week: 'old', entity: 'tracks' }))
    expect(result.current.data?.entity).toBe('albums')
  })
  it('keeps the previous weekly projection as a correctly labelled transition frame', async () => {
    const { wrapper } = setup()
    let resolveNext: (value: unknown) => void = () => {}
    vi.spyOn(api, 'get').mockImplementation((_url, params) => {
      if (params?.entity === 'tracks') return Promise.resolve({ selected_week: '2026-01-02', entity: 'tracks', meta: { all_weeks_desc: ['2026-01-02'] }, current: [], previous: [], historical: [] })
      if (params?.entity === 'albums') return new Promise(resolve => { resolveNext = resolve })
      return Promise.resolve({ selected_week: '2026-01-02', entity: 'artists', meta: { all_weeks_desc: ['2026-01-02'] }, current: [], previous: [], historical: [] })
    })
    const { result, rerender } = renderHook(({ tab }) => useWeeklyProjection({ merge_level: 2 }, '2026-01-02', tab), {
      wrapper,
      initialProps: { tab: 'tracks' },
    })
    await waitFor(() => expect(result.current.data?.entity).toBe('tracks'))
    rerender({ tab: 'albums' })
    expect(result.current.switching).toBe(true)
    expect(result.current.data?.entity).toBe('tracks')
    await act(async () => resolveNext({ selected_week: '2026-01-02', entity: 'albums', meta: { all_weeks_desc: ['2026-01-02'] }, current: [], previous: [], historical: [] }))
    await waitFor(() => expect(result.current.data?.entity).toBe('albums'))
    expect(result.current.switching).toBe(false)
  })
  it('prefetches sibling weekly entities and reuses them when switching back', async () => {
    const { wrapper } = setup()
    const get = vi.spyOn(api, 'get').mockImplementation((_url, params) => Promise.resolve({
      selected_week: '2026-01-02',
      entity: params?.entity,
      meta: { all_weeks_desc: ['2026-01-02'] },
      current: [],
      previous: [],
      historical: [],
    }))
    const { result, rerender } = renderHook(({ tab }) => useWeeklyProjection({ merge_level: 2 }, '2026-01-02', tab), {
      wrapper,
      initialProps: { tab: 'tracks' },
    })
    await waitFor(() => expect(get.mock.calls.filter(([path]) => path === '/billboard/weekly')).toHaveLength(3))
    rerender({ tab: 'albums' })
    await waitFor(() => expect(result.current.data?.entity).toBe('albums'))
    rerender({ tab: 'tracks' })
    await waitFor(() => expect(result.current.data?.entity).toBe('tracks'))
    expect(get.mock.calls.filter(([path]) => path === '/billboard/weekly')).toHaveLength(3)
  })
  it('retains identical entity rows for local controls, but clears them on context changes', async () => {
    const { wrapper } = setup()
    vi.spyOn(api, 'get').mockImplementation((_url, params) => params?.search === ''
      ? Promise.resolve({ entity: 'tracks', rows: [{ track_id: 1 }] }) : new Promise(() => {}))
    const { result, rerender } = renderHook(({ search, merge_level }) => useAllTimeProjection({ merge_level }, { entity: 'tracks', search }), { wrapper, initialProps: { search: '', merge_level: 2 } })
    await waitFor(() => expect(result.current.data?.rows).toHaveLength(1))
    rerender({ search: 'query', merge_level: 2 })
    expect(result.current.loading).toBe(false)
    expect(result.current.data?.rows).toHaveLength(1)
    rerender({ search: 'query', merge_level: 3 })
    expect(result.current.loading).toBe(true)
    expect(result.current.data).toBeNull()
  })
  it('uses only projections and reuses cached entity on return', async () => {
    const { wrapper } = setup()
    const get = vi.spyOn(api, 'get').mockImplementation((_url, params) => Promise.resolve({ entity: params?.entity, rows: [], records: {} }))
    const { result, rerender } = renderHook(({ entity }) => {
      useRecordsProjection({ merge_level: 2 })
      useNumberOnesProjection({ merge_level: 2 })
      return useAllTimeProjection({ merge_level: 2 }, { entity, page: 1, search: '', sort: 'power_score' })
    }, { wrapper, initialProps: { entity: 'tracks' } })
    await waitFor(() => expect(result.current.data?.entity).toBe('tracks'))
    rerender({ entity: 'artists' })
    await waitFor(() => expect(result.current.data?.entity).toBe('artists'))
    rerender({ entity: 'tracks' })
    await waitFor(() => expect(result.current.data?.entity).toBe('tracks'))
    expect(get.mock.calls.filter(([path]) => path === '/billboard/records')).toHaveLength(1)
    expect(get.mock.calls.every(([path, params]) => path !== '/billboard/data' && params?.projection)).toBe(true)
    expect(get.mock.calls.filter(([path]) => path === '/billboard/all-time').map(([,params])=>params?.projection)).toEqual(expect.arrayContaining(['number-ones', 'entity']))
  })
})
