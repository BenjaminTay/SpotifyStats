import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { queryKeys } from '@/api/query-keys'
import { api } from '@/lib/api'
import { useBillboardWeekly } from '@/hooks/useBillboard'
import {
  useWeeklyDigest,
  useMonthlyPersonality,
  useYearlyStory,
  useChatSessions,
  useCreateSession,
  useDeleteSession,
} from '@/hooks/useAiInsights'
import { useSettings } from '@/hooks/useSettings'

function createClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: Infinity,
      },
    },
  })
}

function wrapperFor(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}

describe('Phase 5 query hook migration', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('stores Billboard weekly data in TanStack Query cache', async () => {
    const client = createClient()
    const weekly = {
      meta: { all_weeks_desc: ['2026-05-24'] },
      weekly: [{ billboard_week: '2026-05-24', rank: 1 }],
      weekly_album: [],
      weekly_artist: [],
    }
    vi.spyOn(api, 'get').mockResolvedValue(weekly)

    const { result } = renderHook(() => useBillboardWeekly(), {
      wrapper: wrapperFor(client),
    })

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(api.get).toHaveBeenCalledTimes(1)
    expect(client.getQueryData(queryKeys.billboard.weekly({ merge_level: 2 }))).toBe(weekly)
    expect(result.current.selectedWeek).toBe('2026-05-24')
  })

  it('stores settings in TanStack Query cache after the hook loads', async () => {
    const client = createClient()
    const settings = {
      min_ms: 30000,
      music_only: true,
      merge_enabled: true,
      bb_top_n: 30,
      bb_album_top_n: 20,
      bb_artist_top_n: 20,
      bb_week_start_dow: 0,
      bb_week_start_hour: 0,
      db_record_count: 12,
      account_data_imported: true,
      spotify_connected: false,
      spotify_profile: null,
      llm_enabled: false,
      llm_provider: 'deepseek',
      llm_model: '',
      has_llm_key: false,
    }
    vi.spyOn(api, 'get').mockResolvedValue(settings)

    const { result } = renderHook(() => useSettings(), {
      wrapper: wrapperFor(client),
    })

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(api.get).toHaveBeenCalledWith('/settings')
    expect(client.getQueryData(queryKeys.settings.data())).toBe(settings)
    expect(result.current.settings?.min_ms).toBe(30000)
  })

  it('forces a fresh AI weekly report request on every manual refresh', async () => {
    const client = createClient()
    const response = {
      success: true,
      report: 'weekly report',
      cached: false,
      cached_at: null,
      entities: null,
      error: null,
    }
    vi.spyOn(api, 'get').mockResolvedValue(response)

    const { result } = renderHook(() => useWeeklyDigest('2026-05-01', '2026-05-07'), {
      wrapper: wrapperFor(client),
    })

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(api.get).toHaveBeenCalledTimes(1)

    act(() => result.current.refetch())
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2))

    act(() => result.current.refetch())
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(3))
  })
})

describe('AI Insights query hooks', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  const makeClient = () =>
    new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: Infinity },
        mutations: { retry: false },
      },
    })

  function wrapperFor(client: QueryClient) {
    return function Wrapper({ children }: { children: ReactNode }) {
      return <QueryClientProvider client={client}>{children}</QueryClientProvider>
    }
  }

  it('weekly digest is disabled when enabled=false', async () => {
    const client = makeClient()
    vi.spyOn(api, 'get').mockResolvedValue({ success: true, report: null, cached: false })

    renderHook(() => useWeeklyDigest('2026-01-01', '2026-01-07', false), {
      wrapper: wrapperFor(client),
    })

    // Give it a tick to settle — should never fire
    await new Promise((r) => setTimeout(r, 50))
    expect(api.get).not.toHaveBeenCalled()
  })

  it('monthly personality stores response in cache', async () => {
    const client = makeClient()
    const response = {
      success: true,
      report: 'month report',
      cached: false,
      cached_at: null,
      entities: { artists: ['A'], tracks: [] },
      error: null,
    }
    vi.spyOn(api, 'get').mockResolvedValue(response)

    const { result } = renderHook(() => useMonthlyPersonality('2026-01', 2026), {
      wrapper: wrapperFor(client),
    })

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.data).toEqual(response)
    expect(api.get).toHaveBeenCalledWith(
      '/ai-insights/monthly-personality',
      { month: '2026-01', year: 2026 },
      120_000,
      expect.any(AbortSignal),
    )
  })

  it('yearly story maps error to friendly message', async () => {
    const client = makeClient()
    vi.spyOn(api, 'get').mockRejectedValue(new Error('503'))

    const { result } = renderHook(() => useYearlyStory(2026), {
      wrapper: wrapperFor(client),
    })

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toBe('AI 功能未配置，请在设置中配置 LLM')
  })

  it('yearly story is disabled when year is invalid', async () => {
    const client = makeClient()
    vi.spyOn(api, 'get').mockResolvedValue({})

    renderHook(() => useYearlyStory(0), {
      wrapper: wrapperFor(client),
    })

    await new Promise((r) => setTimeout(r, 50))
    expect(api.get).not.toHaveBeenCalled()
  })

  it('chat sessions query returns an empty array when no sessions exist', async () => {
    const client = makeClient()
    vi.spyOn(api, 'get').mockResolvedValue({ success: true, data: [] })

    const { result } = renderHook(() => useChatSessions(), {
      wrapper: wrapperFor(client),
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.data).toEqual([])
  })

  it('create session calls API and returns session data', async () => {
    const client = makeClient()
    const sessionResponse = { success: true, data: { id: 1, title: 'test', created_at: '', updated_at: '', messages: [] } }
    vi.spyOn(api, 'post').mockResolvedValue(sessionResponse)

    const { result } = renderHook(() => useCreateSession(), {
      wrapper: wrapperFor(client),
    })

    const data = await act(() => result.current.mutateAsync('new session'))
    expect(api.post).toHaveBeenCalledWith('/chat/sessions', { title: 'new session' })
    expect(data).toEqual(sessionResponse)
  })

  it('delete session calls API with correct session id', async () => {
    const client = makeClient()
    vi.spyOn(api, 'del').mockResolvedValue({ success: true, data: null })

    const { result } = renderHook(() => useDeleteSession(), {
      wrapper: wrapperFor(client),
    })

    await act(() => result.current.mutateAsync(1))
    expect(api.del).toHaveBeenCalledWith('/chat/sessions/1')
  })
})
