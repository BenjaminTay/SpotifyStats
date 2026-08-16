import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { queryKeys } from '@/api/query-keys'
import {
  normalizeMusicSearchQuery,
  analyzeMusicSearchQuery,
} from '@/features/music/search/searchInputController'
import {
  useMusicSearchCandidates,
  useMusicSearchContext,
  musicSearchSnapshotPollInterval,
} from '@/features/music/search/useMusicSearch'
import { api } from '@/lib/api'
import type { AnalysisFilters } from '@/types/analysis'

const filters: AnalysisFilters = {
  min_ms: 30000,
  music_only: true,
  merge_enabled: true,
  dynamic_threshold: true,
  max_merge_gap_minutes: 5,
  merge_level: 2,
  include_compilations: false,
  bb_top_n: 30,
  bb_album_top_n: 20,
  bb_artist_top_n: 20,
  bb_week_start_dow: 4,
  bb_week_start_hour: 0,
}

function createClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } })
}

function wrapperFor(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}

function candidateResponse(
  snapshotStatus: 'ready' | 'warming' | 'unavailable' | 'stale' | 'failed',
  filterFingerprint: string | null = null,
) {
  return {
    response_version: 'music_search_v2' as const,
    query: 'Taylor',
    normalized_query: 'taylor',
    snapshot_status: snapshotStatus,
    filter_fingerprint: filterFingerprint,
    kind: null,
    page: 1,
    page_size: 5,
    total: 0,
    total_by_kind: { track: 0, album: 0, artist: 0 },
    tracks: [], albums: [], artists: [],
  }
}

describe('music search v2 hooks', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('shares stable backend normalization vectors and short-query policy', () => {
    expect(normalizeMusicSearchQuery('  Ｔａｙｌｏｒ　Ｓｗｉｆｔ  ')).toBe('taylor swift')
    expect(normalizeMusicSearchQuery('Straße')).toBe('strasse')
    expect(normalizeMusicSearchQuery('“Don’t”—Stop')).toBe('"don\'t"-stop')
    expect(analyzeMusicSearchQuery('a').eligible).toBe(false)
    expect(analyzeMusicSearchQuery('周').eligible).toBe(true)
  })

  it('passes TanStack AbortSignal and disables automatic retry', async () => {
    const client = createClient()
    let capturedSignal: AbortSignal | undefined
    const get = vi.spyOn(api, 'get').mockImplementation((_path, _params, _timeout, signal) => {
      capturedSignal = signal
      return new Promise(() => undefined)
    })

    const { unmount } = renderHook(
      () => useMusicSearchCandidates({ query: 'taylor', filters }),
      { wrapper: wrapperFor(client) },
    )
    await waitFor(() => expect(get).toHaveBeenCalledTimes(1))
    expect(capturedSignal).toBeInstanceOf(AbortSignal)
    expect(capturedSignal?.aborted).toBe(false)

    unmount()
    await waitFor(() => expect(capturedSignal?.aborted).toBe(true))
  })

  it('normalizes equivalent queries into one candidate cache key', async () => {
    const client = createClient()
    vi.spyOn(api, 'get').mockResolvedValue(candidateResponse('unavailable'))

    const first = renderHook(
      ({ query }) => useMusicSearchCandidates({ query, filters }),
      { wrapper: wrapperFor(client), initialProps: { query: 'ＴＡＹＬＯＲ' } },
    )
    await waitFor(() => expect(first.result.current.initialLoading).toBe(false))
    first.rerender({ query: '  taylor  ' })
    await waitFor(() => expect(first.result.current.initialLoading).toBe(false))

    const candidateQueries = client.getQueryCache().findAll({
      queryKey: ['music', 'search', 'candidates'],
    })
    expect(candidateQueries).toHaveLength(1)
  })

  it('sorts and deduplicates context keys and refuses mismatched fingerprints', async () => {
    const client = createClient()
    const get = vi.spyOn(api, 'get').mockResolvedValue({
      response_version: 'music_search_context_v1',
      snapshot_status: 'ready',
      filter_fingerprint: 'older-fingerprint',
      items: { 'track:1': { play_events: 1, total_ms: 1000, chart: null } },
    })

    const { result } = renderHook(
      () => useMusicSearchContext({
        entityKeys: ['track:2', 'track:1', 'track:2'],
        filterFingerprint: 'current-fingerprint',
        filters,
      }),
      { wrapper: wrapperFor(client) },
    )
    await waitFor(() => expect(get).toHaveBeenCalledTimes(1))
    expect(get.mock.calls[0][1]).toMatchObject({ entity_key: ['track:1', 'track:2'] })
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.data).toBeNull()
    expect(client.getQueryCache().findAll({
      queryKey: queryKeys.music.searchContext(
        'current-fingerprint',
        ['track:2', 'track:1', 'track:2'],
      ),
    })).toHaveLength(1)
  })

  it('sends only the two supported search variant parameters', async () => {
    const client = createClient()
    const get = vi.spyOn(api, 'get')
      .mockResolvedValueOnce(candidateResponse('ready', 'fingerprint'))
      .mockResolvedValueOnce({
        response_version: 'music_search_context_v1',
        snapshot_status: 'ready',
        filter_fingerprint: 'fingerprint',
        items: {},
      })

    const candidates = renderHook(
      () => useMusicSearchCandidates({ query: 'taylor', filters, kind: 'artist' }),
      { wrapper: wrapperFor(client) },
    )
    await waitFor(() => expect(candidates.result.current.data?.snapshot_status).toBe('ready'))
    expect(get.mock.calls[0][1]).toEqual({
      q: 'taylor',
      response_mode: 'candidates',
      eligibility: 'current',
      page: 1,
      page_size: 5,
      kind: 'artist',
      dynamic_threshold: true,
      merge_level: 2,
    })

    const context = renderHook(
      () => useMusicSearchContext({
        entityKeys: ['artist:13'],
        filterFingerprint: 'fingerprint',
        filters,
      }),
      { wrapper: wrapperFor(client) },
    )
    await waitFor(() => expect(context.result.current.loading).toBe(false))
    expect(get.mock.calls[1][1]).toEqual({
      entity_key: ['artist:13'],
      dynamic_threshold: true,
      merge_level: 2,
    })
  })

  it('never uses candidate placeholder data from another filter variant', async () => {
    const client = createClient()
    let resolveNext: ((value: ReturnType<typeof candidateResponse>) => void) | undefined
    vi.spyOn(api, 'get')
      .mockResolvedValueOnce(candidateResponse('ready', 'l2-fingerprint'))
      .mockImplementationOnce(() => new Promise((resolve) => {
        resolveNext = resolve
      }))

    const { result, rerender } = renderHook(
      ({ currentFilters }) => useMusicSearchCandidates({
        query: 'taylor',
        filters: currentFilters,
      }),
      { wrapper: wrapperFor(client), initialProps: { currentFilters: filters } },
    )
    await waitFor(() => expect(result.current.data?.filter_fingerprint).toBe('l2-fingerprint'))

    rerender({ currentFilters: { ...filters, merge_level: 3 } })
    await waitFor(() => expect(result.current.initialLoading).toBe(true))
    expect(result.current.data).toBeNull()
    expect(result.current.isPlaceholderData).toBe(false)

    await act(async () => resolveNext?.(candidateResponse('warming', 'l3-fingerprint')))
    await waitFor(() => expect(result.current.data?.filter_fingerprint).toBe('l3-fingerprint'))
  })

  it('polls only successful warming or stale states with bounded backoff', () => {
    const query = (
      snapshotStatus: 'ready' | 'warming' | 'unavailable' | 'stale' | 'failed',
      dataUpdateCount: number,
      status = 'success',
    ) => ({
      state: {
        data: candidateResponse(snapshotStatus),
        dataUpdateCount,
        status,
      },
    })

    expect(musicSearchSnapshotPollInterval(query('warming', 1))).toBe(2_000)
    expect(musicSearchSnapshotPollInterval(query('stale', 2))).toBe(4_000)
    expect(musicSearchSnapshotPollInterval(query('warming', 3))).toBe(8_000)
    expect(musicSearchSnapshotPollInterval(query('warming', 4))).toBe(10_000)
    expect(musicSearchSnapshotPollInterval(query('warming', 20))).toBe(10_000)
    expect(musicSearchSnapshotPollInterval(query('ready', 2))).toBe(false)
    expect(musicSearchSnapshotPollInterval(query('unavailable', 1))).toBe(false)
    expect(musicSearchSnapshotPollInterval(query('failed', 1))).toBe(false)
    expect(musicSearchSnapshotPollInterval(query('warming', 2, 'error'))).toBe(false)

    const visibility = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
    expect(musicSearchSnapshotPollInterval(query('warming', 2))).toBe(false)
    visibility.mockRestore()
  })

  it('automatically observes warming until ready and then stops', async () => {
    vi.useFakeTimers()
    const client = createClient()
    const get = vi.spyOn(api, 'get')
      .mockResolvedValueOnce(candidateResponse('warming', 'fingerprint'))
      .mockResolvedValue(candidateResponse('ready', 'fingerprint'))

    renderHook(
      () => useMusicSearchCandidates({ query: 'taylor', filters }),
      { wrapper: wrapperFor(client) },
    )
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(get).toHaveBeenCalledTimes(1)

    await act(async () => { await vi.advanceTimersByTimeAsync(2_000) })
    expect(get).toHaveBeenCalledTimes(2)
    await act(async () => { await vi.advanceTimersByTimeAsync(20_000) })
    expect(get).toHaveBeenCalledTimes(2)
  })

  it('does not turn a polling network failure into another automatic retry', async () => {
    vi.useFakeTimers()
    const client = createClient()
    const get = vi.spyOn(api, 'get')
      .mockResolvedValueOnce(candidateResponse('warming', 'fingerprint'))
      .mockRejectedValueOnce(new Error('offline'))

    renderHook(
      () => useMusicSearchCandidates({ query: 'taylor', filters }),
      { wrapper: wrapperFor(client) },
    )
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    await act(async () => { await vi.advanceTimersByTimeAsync(2_000) })
    expect(get).toHaveBeenCalledTimes(2)
    await act(async () => { await vi.advanceTimersByTimeAsync(20_000) })
    expect(get).toHaveBeenCalledTimes(2)
  })
})
