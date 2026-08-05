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
import { analysisApi, musicSearchApi } from '@/hooks/useAnalysis'
import { queryClient } from '@/api/query-client'
import { useProfile } from '@/hooks/useAccount'

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
    expect(client.getQueryData(queryKeys.billboard.weekly({ merge_level: 2, include_compilations: false }))).toBe(weekly)
    expect(result.current.selectedWeek).toBe('2026-05-24')
  })

  it('follows weekly URL history and restores the latest week when the query is removed', async () => {
    const client = createClient()
    const weekly = {
      meta: { all_weeks_desc: ['2026-08-03', '2026-07-27'] },
      weekly: [],
      weekly_album: [],
      weekly_artist: [],
    }
    vi.spyOn(api, 'get').mockResolvedValue(weekly)

    const { result, rerender } = renderHook(
      ({ week }: { week: string | null }) => useBillboardWeekly(week),
      { wrapper: wrapperFor(client), initialProps: { week: null as string | null } },
    )

    await waitFor(() => expect(result.current.selectedWeek).toBe('2026-08-03'))
    rerender({ week: '2026-07-27' })
    await waitFor(() => expect(result.current.selectedWeek).toBe('2026-07-27'))
    rerender({ week: null })
    await waitFor(() => expect(result.current.selectedWeek).toBe('2026-08-03'))
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
      include_compilations: false,
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

  it('invalidates Billboard queries after Billboard settings are updated', async () => {
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
      include_compilations: false,
      db_record_count: 12,
      account_data_imported: true,
      spotify_connected: false,
      spotify_profile: null,
      llm_enabled: false,
      llm_provider: 'deepseek',
      llm_model: '',
      has_llm_key: false,
      llm_active_profile_id: null,
      llm_active_profile_name: null,
      rebuild_pending: false,
    }
    const updated = { ...settings, bb_top_n: 40, rebuild_pending: true }
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries')
    vi.spyOn(api, 'get').mockResolvedValue(settings)
    vi.spyOn(api, 'put').mockResolvedValue(updated)

    const { result } = renderHook(() => useSettings(), {
      wrapper: wrapperFor(client),
    })

    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.updateSettings({ bb_top_n: 40 })
    })

    expect(api.put).toHaveBeenCalledWith('/settings', { bb_top_n: 40 })
    expect(client.getQueryData(queryKeys.settings.data())).toEqual(updated)
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: queryKeys.billboard.all })
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

  it('requests behavior data with only effective behavior filters', async () => {
    queryClient.clear()
    vi.spyOn(api, 'get').mockResolvedValue({
      reason_end: [],
      reason_start: [],
      fwdbtn_by_hour: [],
      most_forwarded: [],
      platform_monthly: [],
      platform_hourly: [],
      shuffle_rate_by_platform: [],
      shuffle_monthly: [],
    })

    await analysisApi.behavior({
      min_ms: 1000,
      music_only: false,
      merge_enabled: false,
      dynamic_threshold: true,
      max_merge_gap_minutes: 30,
      merge_level: 3,
      include_compilations: false,
    })

    expect(api.get).toHaveBeenCalledWith('/behavior', { music_only: false })
  })

  it('stores account profile hero data separately from the heavy account summary', async () => {
    const client = createClient()
    const profile = {
      profile: { identity_displayName: 'Taylor Listener' },
      follows: [{ type: 'artist', name: 'Taylor Swift' }],
      prompts: [],
      stats: { first_play_date: '2022-01-01', total_audio_plays: 1234 },
      banned_items: [],
    }
    vi.spyOn(api, 'get').mockResolvedValue(profile)

    const { result } = renderHook(() => useProfile(), {
      wrapper: wrapperFor(client),
    })

    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(api.get).toHaveBeenCalledWith('/profile')
    expect(client.getQueryData(queryKeys.account.profile())).toBe(profile)
    expect(result.current.data?.profile.identity_displayName).toBe('Taylor Listener')
  })

  it('stores local music search data under music query keys', async () => {
    queryClient.clear()
    const filters = {
      min_ms: 45000,
      music_only: true,
      merge_enabled: false,
      dynamic_threshold: false,
      max_merge_gap_minutes: undefined,
      merge_level: 2,
      include_compilations: false,
      bb_top_n: 40,
      bb_album_top_n: 30,
      bb_artist_top_n: 25,
      bb_week_start_dow: 5,
      bb_week_start_hour: 2,
    }
    const params = {
      q: 'love',
      limit_per_type: 3,
      kind: 'track',
      min_ms: 45000,
      music_only: true,
      merge_enabled: false,
      dynamic_threshold: false,
      merge_level: 2,
      include_chart: true,
      bb_top_n: 40,
      bb_album_top_n: 30,
      bb_artist_top_n: 25,
      bb_week_start_dow: 5,
      bb_week_start_hour: 2,
    }
    const response = {
      query: 'love',
      limit_per_type: 3,
      total: 1,
      tracks: [{ kind: 'track', label: 'Cruel Summer', href: '/music/tracks/42', play_events: 17 }],
      albums: [],
      artists: [],
    }
    vi.spyOn(api, 'get').mockResolvedValue(response)

    const result = await musicSearchApi.search(filters, ' love ', 'track', 3, { includeChart: true })

    expect(api.get).toHaveBeenCalledWith('/music/search', params)
    expect(result).toBe(response)
    expect(queryClient.getQueryData(queryKeys.music.search(params))).toBe(response)
  })

  it('keeps quick music search lightweight unless chart badges are requested', async () => {
    queryClient.clear()
    const filters = {
      min_ms: 45000,
      music_only: true,
      merge_enabled: false,
      dynamic_threshold: false,
      max_merge_gap_minutes: undefined,
      merge_level: 2,
      include_compilations: false,
      bb_top_n: 40,
      bb_album_top_n: 30,
      bb_artist_top_n: 25,
      bb_week_start_dow: 5,
      bb_week_start_hour: 2,
    }
    vi.spyOn(api, 'get').mockResolvedValue({
      query: 'love',
      limit_per_type: 5,
      total: 0,
      tracks: [],
      albums: [],
      artists: [],
    })

    await musicSearchApi.search(filters, ' love ')

    expect(api.get).toHaveBeenCalledWith('/music/search', expect.not.objectContaining({
      include_chart: true,
    }))
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

describe('Merge level query key differentiation', () => {
  it('different merge levels produce different Billboard weekly query keys', () => {
    expect(queryKeys.billboard.weekly({ merge_level: 1 })).not.toEqual(
      queryKeys.billboard.weekly({ merge_level: 2 })
    )
  })

  it('different merge levels produce different Billboard data query keys', () => {
    expect(queryKeys.billboard.data({ merge_level: 1 })).not.toEqual(
      queryKeys.billboard.data({ merge_level: 2 })
    )
  })

  it('different merge levels produce different Billboard records query keys', () => {
    expect(queryKeys.billboard.records({ merge_level: 1 })).not.toEqual(
      queryKeys.billboard.records({ merge_level: 3 })
    )
  })

  it('different merge levels produce different Billboard allTime query keys', () => {
    expect(queryKeys.billboard.allTime({ merge_level: 1 })).not.toEqual(
      queryKeys.billboard.allTime({ merge_level: 2 })
    )
  })

  it('same merge level produces identical query keys', () => {
    expect(queryKeys.billboard.weekly({ merge_level: 2 })).toEqual(
      queryKeys.billboard.weekly({ merge_level: 2 })
    )
  })

  it('merge level query keys are distinct from no-params keys', () => {
    expect(queryKeys.billboard.weekly()).not.toEqual(
      queryKeys.billboard.weekly({ merge_level: 2 })
    )
  })
})
