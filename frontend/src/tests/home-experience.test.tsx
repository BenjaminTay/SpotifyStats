import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, renderHook, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'
import { HomeDesktopExperience } from '@/features/home/HomeDesktopExperience'
import { HomeEmpty } from '@/features/home/HomeStates'
import { HomePhoneExperience } from '@/features/home/HomePhoneExperience'
import { useAnalysisQueryState } from '@/components/shared/AnalysisControls'
import { useHomeOverview } from '@/hooks/useHome'
import type { AnalysisFilters } from '@/types/analysis'
import type { HomeOverviewResponse } from '@/types/home'

const track = {
  entity_type: 'track' as const,
  entity_id: 42,
  name: '久违的歌',
  artist_name: '示例艺人',
  cover_url: '/covers/albums/42.jpg',
  deep_link: '/music/tracks/42',
}

const data: HomeOverviewResponse = {
  schema_version: 'home_overview_v2',
  generated_at: '2026-08-13T10:00:00+08:00',
  filter_fingerprint: 'filters-v1',
  state: 'ready',
  coverage: {
    first_source_date: '2013-01-02',
    source_latest_date: '2026-08-12',
    first_effective_play_date: '2013-01-02',
    latest_effective_play_date: '2026-08-10',
    first_play_date: '2013-01-02',
    latest_play_date: '2026-08-10',
    freshness: 'recent',
    has_account_data: true,
  },
  archive: { total_plays: 91286, total_hours: 4320, unique_tracks: 8241, unique_artists: 1200, unique_albums: 2300, active_days: 2100 },
  headline: { kind: 'comeback', title: '最近，你重新回到了《久违的歌》', statement: '最近4周再次播放了12次。', entity: track },
  recent: {
    period: { start_date: '2026-07-14', end_date: '2026-08-10', label: '最近4周' },
    comparison_period: { start_date: '2026-06-16', end_date: '2026-07-13', label: '此前4周' },
    comparison_available: true,
    summary: { plays: 320, hours: 18.6, active_days: 22, plays_delta_pct: 12.5, hours_delta_pct: -3.2, late_night_pct: 28, weekend_pct: 31 },
    trend: [{ date: '2026-07-14', plays: 4, hours: .2 }, { date: '2026-08-10', plays: 18, hours: 1.1 }],
    leaders: {
      track: { entity: track, plays: 12, hours: .8 },
      album: { entity: { ...track, entity_type: 'album', entity_id: 'album', name: '示例专辑', deep_link: '/music/albums/example' }, plays: 30, hours: 2 },
      artist: { entity: { ...track, entity_type: 'artist', entity_id: 'artist', name: '示例艺人', artist_name: null, deep_link: '/music/artists/example' }, plays: 45, hours: 3 },
    },
  },
  billboard: {
    state: 'ready', week: '2026-08-07',
    track: { entity: track, rank: 1, plays: 12, hours: .8, movement: 'up', previous_rank: 3, rank_change: 2 },
    album: { entity: { ...track, entity_type: 'album', name: '示例专辑' }, rank: 1, plays: 30, hours: 2, movement: 'new', previous_rank: null, rank_change: null },
    artist: { entity: { ...track, entity_type: 'artist', name: '示例艺人', artist_name: null }, rank: 1, plays: 45, hours: 3, movement: 're', previous_rank: null, rank_change: null },
  },
  yearly_review: { state: 'ready', year: 2026, headline: '这一年的声音与轨迹', statement: '八章个人音乐年鉴。', entity: track },
  rediscovery: { entity: track, last_played: '2025-06-01', total_plays: 46, days_since_last_play: 435 },
}

const filters: AnalysisFilters = {
  min_ms: 45000,
  music_only: true,
  merge_enabled: true,
  dynamic_threshold: false,
  max_merge_gap_minutes: 75,
  merge_level: 3,
  include_compilations: true,
  bb_top_n: 50,
  bb_album_top_n: 25,
  bb_artist_top_n: 15,
  bb_week_start_dow: 5,
  bb_week_start_hour: 12,
}

const pinnedRecentRoute = '/analysis/stats?period=last_4_weeks&start=2026-07-14&end=2026-08-10'

function router(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}><MemoryRouter>{children}</MemoryRouter></QueryClientProvider>
}

describe('正式首页 V1', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('renders the streamlined desktop music front page without utility rows', () => {
    render(router(<HomeDesktopExperience data={{ ...data, coverage: { ...data.coverage, freshness: 'aging' } }} />))

    expect(screen.getByText('最近，你重新回到了《久违的歌》')).toBeInTheDocument()
    expect(screen.getByText('最新个人 Billboard')).toBeInTheDocument()
    expect(screen.getByText('重回榜 · 45 次播放')).toBeInTheDocument()
    expect(screen.getByText('新入榜 · 30 次播放')).toBeInTheDocument()
    expect(screen.getByText('长期记忆')).toBeInTheDocument()
    expect(screen.getByText('截至 2026.08.10 的最近 4 周')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /查看最近播放/ })).toHaveAttribute('href', pinnedRecentRoute)
    expect(screen.getByRole('link', { name: /打开完整播放分析/ })).toHaveAttribute('href', pinnedRecentRoute)
    expect(screen.queryByText(/Personal music archive/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/数据更新至/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /搜索我的音乐/ })).not.toBeInTheDocument()
    expect(screen.queryByText('播放记录已有一段时间未更新')).not.toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: '更多功能' })).not.toBeInTheDocument()
  })

  it('keeps the streamlined phone presentation independent', () => {
    render(router(<HomePhoneExperience data={data} />))
    expect(screen.queryByText(/数据更新至/)).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /搜索/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: '更多功能' })).not.toBeInTheDocument()
    expect(screen.getByText('最近 4 周')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /查看最近播放/ })).toHaveAttribute('href', pinnedRecentRoute)
    expect(screen.getByRole('link', { name: '音乐详情' })).toHaveAttribute('href', track.deep_link)
    expect(screen.getByRole('link', { name: /完整播放分析/ })).toHaveAttribute('href', pinnedRecentRoute)
    expect(document.querySelector('[data-home-presentation="phone"]')).toBeInTheDocument()
    expect(document.querySelector('[data-home-presentation="desktop"]')).not.toBeInTheDocument()
    expect(screen.getByText('RE')).toBeInTheDocument()
  })

  it('uses a real import route and never invents empty-state metrics', () => {
    render(router(<HomeEmpty />))
    expect(screen.getByRole('link', { name: /导入 Spotify 数据/ })).toHaveAttribute('href', '/settings#data-import')
    expect(screen.queryByText('91,286')).not.toBeInTheDocument()
  })

  it('keeps the homepage four-week window pinned without changing the direct analysis default', () => {
    const PinnedWrapper = ({ children }: { children: ReactNode }) => (
      <MemoryRouter initialEntries={[pinnedRecentRoute]}>{children}</MemoryRouter>
    )
    const pinned = renderHook(() => useAnalysisQueryState(), { wrapper: PinnedWrapper })
    expect(pinned.result.current.period).toBe('last_4_weeks')
    expect(pinned.result.current.apiParams).toEqual({
      period: 'custom',
      start_date: '2026-07-14',
      end_date: '2026-08-10',
    })
    pinned.unmount()

    const DirectWrapper = ({ children }: { children: ReactNode }) => (
      <MemoryRouter initialEntries={['/analysis/stats']}>{children}</MemoryRouter>
    )
    const direct = renderHook(() => useAnalysisQueryState(), { wrapper: DirectWrapper })
    expect(direct.result.current.period).toBe('lifetime')
    expect(direct.result.current.apiParams).toEqual({ period: 'lifetime' })
  })

  it('renders a limited archive without recent or stale-data utility modules', () => {
    const limited: HomeOverviewResponse = {
      ...data,
      state: 'limited',
      coverage: { ...data.coverage, freshness: 'old' },
      recent: null,
      billboard: { state: 'unavailable', week: null, track: null, album: null, artist: null },
    }
    render(router(<HomePhoneExperience data={limited} />))
    expect(screen.queryByText('播放记录可以更新了')).not.toBeInTheDocument()
    expect(screen.queryByText('最近一章')).not.toBeInTheDocument()
    expect(screen.getByText('当前还没有可用榜单。')).toBeInTheDocument()
  })

  it('sends the complete playback and Billboard context and isolates the query cache', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    vi.spyOn(api, 'get').mockResolvedValue(data)
    const Wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
    const { result } = renderHook(() => useHomeOverview(filters), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(api.get).toHaveBeenCalledWith('/home/overview', expect.objectContaining({
      min_ms: 45000,
      dynamic_threshold: false,
      max_merge_gap_minutes: 75,
      merge_level: 3,
      include_compilations: true,
      bb_top_n: 50,
      bb_album_top_n: 25,
      bb_artist_top_n: 15,
      bb_week_start_dow: 5,
      bb_week_start_hour: 12,
    }))
  })

  it('briefly retries a cold cache-only preview and stops after it becomes ready', async () => {
    vi.useFakeTimers()
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const pending: HomeOverviewResponse = {
      ...data,
      billboard: { state: 'unavailable', week: null, track: null, album: null, artist: null },
      yearly_review: { state: 'not_generated', year: 2026, headline: null, statement: null, entity: null },
    }
    const getSpy = vi.spyOn(api, 'get')
      .mockResolvedValueOnce(pending)
      .mockResolvedValue(data)
    const Wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>

    renderHook(() => useHomeOverview(filters), { wrapper: Wrapper })
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(getSpy).toHaveBeenCalledTimes(1)

    await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
    expect(getSpy).toHaveBeenCalledTimes(2)

    await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
    expect(getSpy).toHaveBeenCalledTimes(2)
  })
})
