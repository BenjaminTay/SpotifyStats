import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactElement } from 'react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AlbumDetailExperience } from '@/features/music/details/AlbumDetailExperience'
import { ArtistDetailExperience } from '@/features/music/details/ArtistDetailExperience'
import { TrackDetailExperience } from '@/features/music/details/TrackDetailExperience'
import { api } from '@/lib/api'
import { RuntimeCapabilitiesProvider } from '@/hooks/useRuntimeCapabilities'
import { FULL_CAPABILITIES } from '@/hooks/runtimeCapabilities'

vi.mock('@/hooks/useAnalysis', () => ({
  useAnalysisFilters: () => ({
    filters: {
      min_ms: 30_000,
      music_only: true,
      merge_enabled: true,
      dynamic_threshold: true,
      merge_level: 2,
      include_compilations: false,
      bb_top_n: 30,
      bb_album_top_n: 20,
      bb_artist_top_n: 20,
      bb_week_start_dow: 4,
      bb_week_start_hour: 12,
    },
    loading: false,
  }),
}))

vi.mock('@/components/shared/EntityStatsPanel', () => ({
  EntityStatsPanel: () => <div>播放统计内容</div>,
  EntityStatsPrefetch: () => null,
}))

const TRACK_DETAIL = {
  found: true,
  chart_status: 'not_charted',
  effective_play_count: 5,
  track_id: 101,
  track_name: 'History Track',
  artist_name: 'History Artist',
  artist_names: ['History Artist'],
  cover_url: null,
  meta: null,
  summary: null,
  history: [],
  chart_data: { x: [], y: [], texts: [], top_n: 30, peak_position: 0 },
}

const ALBUM_DETAIL = {
  found: true,
  chart_status: 'not_charted',
  track_chart_status: 'not_charted',
  effective_play_count: 5,
  album_name: 'History Album',
  artist_name: 'History Artist',
  cover_url: null,
  meta: null,
  info: null,
  chart_summary: null,
  album_project: null,
  album_weekly_history: [],
  album_no1_by_week: [],
  best_singles_overlay: [],
  tracks: [],
}

const ARTIST_DETAIL = {
  found: true,
  chart_status: 'not_charted',
  track_chart_status: 'not_charted',
  album_chart_status: 'not_charted',
  effective_play_count: 5,
  artist_name: 'History Artist',
  cover_url: null,
  meta: null,
  info: null,
  chart_summary: null,
  artist_weekly_history: [],
  artist_no1_by_week: [],
  week_no1_albums: [],
  best_singles_overlay: [],
  best_albums_overlay: [],
  tracks: [],
  albums: [],
}

function renderWithHistory(path: string, routePath: string, element: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  client.setQueryData(['runtime', 'capabilities'], FULL_CAPABILITIES)
  const router = createMemoryRouter(
    [
      { path: '/source', element: <div>进入详情前的页面</div> },
      { path: routePath, element },
    ],
    { initialEntries: ['/source', path], initialIndex: 1 },
  )
  render(
    <QueryClientProvider client={client}>
      <RuntimeCapabilitiesProvider><RouterProvider router={router} /></RuntimeCapabilitiesProvider>
    </QueryClientProvider>,
  )
  return router
}

afterEach(() => vi.restoreAllMocks())

describe('音乐详情页历史记录', () => {
  it.each([
    {
      name: '单曲',
      path: '/music/tracks/101',
      routePath: '/music/tracks/:trackId',
      element: <TrackDetailExperience />,
      apiPath: '/billboard/track/canonical/101',
      data: TRACK_DETAIL,
      backName: /单曲详情/,
    },
    {
      name: '专辑',
      path: '/music/albums/History%20Album?artist=History%20Artist',
      routePath: '/music/albums/:albumName',
      element: <AlbumDetailExperience />,
      apiPath: '/billboard/album/History Album',
      data: ALBUM_DETAIL,
      backName: /专辑详情/,
    },
    {
      name: '艺人',
      path: '/music/artists/History%20Artist',
      routePath: '/music/artists/:artistName',
      element: <ArtistDetailExperience />,
      apiPath: '/billboard/artist/History Artist',
      data: ARTIST_DETAIL,
      backName: /艺人详情/,
    },
  ])('$name详情切换 Tab 后返回时直接退出详情页', async ({
    path,
    routePath,
    element,
    apiPath,
    data,
    backName,
  }) => {
    vi.spyOn(api, 'get').mockImplementation((requestPath: string) => {
      if (requestPath === apiPath) return Promise.resolve(data)
      return Promise.reject(new Error(`unexpected GET ${requestPath}`))
    })
    const router = renderWithHistory(path, routePath, element)

    fireEvent.click(await screen.findByRole('button', { name: '榜单成绩' }))
    await waitFor(() => {
      expect(router.state.location.search).toContain('tab=overview')
      expect(router.state.historyAction).toBe('REPLACE')
    })

    fireEvent.click(screen.getByRole('button', { name: backName }))
    expect(await screen.findByText('进入详情前的页面')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/source')
  })
})
