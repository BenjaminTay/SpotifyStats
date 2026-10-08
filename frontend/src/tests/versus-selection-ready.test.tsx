import { act, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { apiClient } from '@/api/client'
import { useVersus } from '@/hooks/useBillboard'
import { useVersusPersonal, personalBatchBody } from '@/features/billboard/versus/useVersusPersonal'
import { useVersusSelectionReady } from '@/features/billboard/versus/useVersusSelectionReady'
import type { EntityListItem } from '@/types/billboard'
import type { VersusKind } from '@/features/billboard/versus/versusData'

const queue = [1, 2, 3, 4].map((track_id) => ({ track_id, display: String(track_id) }))
interface Props { kind: VersusKind; items: EntityListItem[]; filters: Record<string, string | number | boolean> }
function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } })
  return ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
}
function useReads({ kind, items, filters }: Props) {
  const ready = useVersusSelectionReady(kind, items, filters)
  const chart = useVersus(kind, ready ? personalBatchBody(kind, items) : null, filters)
  const personal = useVersusPersonal(kind, items, filters, ready)
  return { ready, chart, personal }
}
beforeEach(() => vi.useFakeTimers())
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers() })

it('starts two objects immediately and sends only the fourth-object batch after a rapid third/fourth addition', async () => {
  const timestamps: number[] = []
  const call = vi.spyOn(apiClient, 'postWithParams').mockImplementation(() => { timestamps.push(Date.now()); return new Promise(() => {}) })
  const { result, rerender } = renderHook(useReads, { wrapper: wrapper(), initialProps: { kind: 'track', items: queue.slice(0, 2), filters: {} } as Props })
  expect(result.current.ready).toBe(true)
  expect(call).toHaveBeenCalledTimes(3)
  rerender({ kind: 'track', items: queue.slice(0, 3), filters: {} })
  expect(result.current.ready).toBe(false)
  expect(result.current.chart.data).toBeNull()
  expect(result.current.personal.statsData).toBeUndefined()
  await act(() => vi.advanceTimersByTimeAsync(100))
  rerender({ kind: 'track', items: queue, filters: {} })
  const selectedFourthAt = Date.now()
  await act(() => vi.advanceTimersByTimeAsync(219))
  expect(call).toHaveBeenCalledTimes(3)
  await act(() => vi.advanceTimersByTimeAsync(1))
  expect(call).toHaveBeenCalledTimes(6)
  expect(call.mock.calls.slice(3).every(([, body]) => JSON.stringify(body) === JSON.stringify({ track_ids: [1, 2, 3, 4] }))).toBe(true)
  expect(timestamps.slice(3).every((timestamp) => timestamp - selectedFourthAt === 220)).toBe(true)
})
it('sends a stable third-object selection after 220ms and does not restart the timer on reorder', async () => {
  const call = vi.spyOn(apiClient, 'postWithParams').mockImplementation(() => new Promise(() => {}))
  const { result, rerender } = renderHook(useReads, { wrapper: wrapper(), initialProps: { kind: 'track', items: queue.slice(0, 2), filters: {} } as Props })
  rerender({ kind: 'track', items: queue.slice(0, 3), filters: {} })
  await act(() => vi.advanceTimersByTimeAsync(150))
  rerender({ kind: 'track', items: queue.slice(0, 3).reverse(), filters: {} })
  await act(() => vi.advanceTimersByTimeAsync(70))
  expect(result.current.ready).toBe(true)
  expect(call).toHaveBeenCalledTimes(6)
  rerender({ kind: 'track', items: queue.slice(0, 3), filters: {} })
  expect(result.current.ready).toBe(true)
  expect(call).toHaveBeenCalledTimes(6)
})
it('cancels a pending selection across filter/type changes and never requests the abandoned queue', async () => {
  const call = vi.spyOn(apiClient, 'postWithParams').mockImplementation(() => new Promise(() => {}))
  const { result, rerender } = renderHook(useReads, { wrapper: wrapper(), initialProps: { kind: 'track', items: queue.slice(0, 2), filters: { min_ms: 30000 } } as Props })
  const initialSignal = call.mock.calls[0][4]!
  rerender({ kind: 'track', items: queue.slice(0, 3), filters: { min_ms: 30000 } })
  await act(() => vi.advanceTimersByTimeAsync(100))
  rerender({ kind: 'track', items: queue.slice(0, 3), filters: { min_ms: 60000 } })
  await act(() => vi.advanceTimersByTimeAsync(100))
  const artists = ['A', 'B', 'C'].map((artist_name) => ({ artist_name, display: artist_name }))
  rerender({ kind: 'artist', items: artists, filters: { min_ms: 60000 } })
  expect(result.current.personal.statsData).toBeUndefined()
  expect(result.current.chart.data).toBeNull()
  await act(() => vi.advanceTimersByTimeAsync(220))
  expect(call).toHaveBeenCalledTimes(6)
  expect(initialSignal.aborted).toBe(true)
  expect(call.mock.calls.slice(3).every(([path, body, filters]) => path.includes('/artist') && JSON.stringify(body) === JSON.stringify({ artist_names: ['A', 'B', 'C'] }) && filters.min_ms === 60000)).toBe(true)
})
it('starts the current two-object context immediately after cancelling a pending third-object selection', async () => {
  const call = vi.spyOn(apiClient, 'postWithParams').mockImplementation(() => new Promise(() => {}))
  const { result, rerender } = renderHook(useReads, { wrapper: wrapper(), initialProps: { kind: 'track', items: queue.slice(0, 2), filters: {} } as Props })
  rerender({ kind: 'track', items: queue.slice(0, 3), filters: {} })
  await act(() => vi.advanceTimersByTimeAsync(100))
  rerender({ kind: 'album', items: [{ display: 'One', artist_name: 'A', album_name: 'One' }, { display: 'Two', artist_name: 'B', album_name: 'Two' }], filters: {} })
  expect(result.current.ready).toBe(true)
  expect(call).toHaveBeenCalledTimes(6)
  await act(() => vi.advanceTimersByTimeAsync(220))
  expect(call).toHaveBeenCalledTimes(6)
  expect(call.mock.calls.slice(3).every(([path]) => path.includes('/album'))).toBe(true)
})
