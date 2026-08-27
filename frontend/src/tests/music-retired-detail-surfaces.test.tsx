import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AlbumDetailExperience } from '@/features/music/details/AlbumDetailExperience'
import { ArtistDetailExperience } from '@/features/music/details/ArtistDetailExperience'
import { TrackDetailExperience } from '@/features/music/details/TrackDetailExperience'
import { RuntimeCapabilitiesProvider } from '@/hooks/useRuntimeCapabilities'
import { FULL_CAPABILITIES } from '@/hooks/runtimeCapabilities'
import { api } from '@/lib/api'

vi.mock('@/hooks/useAnalysis', () => ({
  useAnalysisFilters: () => ({ filters: {}, loading: false }),
}))

vi.mock('@/components/shared/EntityStatsPanel', () => ({
  EntityStatsPanel: () => <div>播放统计内容</div>,
  EntityStatsPrefetch: () => null,
}))

function createClient() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  client.setQueryData(['runtime', 'capabilities'], FULL_CAPABILITIES)
  return client
}

function LocationProbe() {
  const location = useLocation()
  return <output aria-label="当前地址">{location.pathname}{location.search}</output>
}

function wrapperFor(initialEntry: string) {
  const client = createClient()
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={[initialEntry]}>
        <QueryClientProvider client={client}>
          <RuntimeCapabilitiesProvider>
            <Routes>
              <Route path="/music/artists/:artistName" element={<>{children}<LocationProbe /></>} />
              <Route path="/music/albums/:albumName" element={<>{children}<LocationProbe /></>} />
              <Route path="/music/tracks/:trackId" element={<>{children}<LocationProbe /></>} />
            </Routes>
          </RuntimeCapabilitiesProvider>
        </QueryClientProvider>
      </MemoryRouter>
    )
  }
}

afterEach(() => vi.restoreAllMocks())

describe('retired music detail surfaces', () => {
  it('normalizes the retired track lyrics tab without lyrics or enrichment requests', async () => {
    const get = vi.spyOn(api, 'get').mockImplementation((path: string) => {
      if (path === '/billboard/track/canonical/101') {
        return Promise.resolve({
          found: true,
          track_id: 101,
          track_name: 'Retired Lyrics Track',
          artist_name: 'Test Artist',
          artist_names: ['Test Artist'],
          cover_url: null,
          meta: null,
          summary: null,
          history: [],
          chart_data: {},
        })
      }
      return Promise.reject(new Error(`unexpected GET ${path}`))
    })

    render(<TrackDetailExperience />, {
      wrapper: wrapperFor('/music/tracks/101?tab=lyrics'),
    })

    expect(await screen.findByText('播放统计内容')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByLabelText('当前地址')).not.toHaveTextContent('tab='))
    expect(screen.queryByRole('button', { name: '歌词' })).not.toBeInTheDocument()
    expect(get.mock.calls.some(([path]) => String(path).startsWith('/lyrics/'))).toBe(false)
    expect(get.mock.calls.some(([path]) => String(path).includes('/enrichment/track/'))).toBe(false)
  })

  it.each(['career', 'releases'])('normalizes retired artist tab %s without background work', async (tab) => {
    const get = vi.spyOn(api, 'get').mockImplementation((path: string) => {
      if (path === '/billboard/artist/Taylor Swift') {
        return Promise.resolve({
          found: true,
          artist_name: 'Taylor Swift',
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
        })
      }
      return Promise.reject(new Error(`unexpected GET ${path}`))
    })
    const post = vi.spyOn(api, 'post')

    render(<ArtistDetailExperience />, {
      wrapper: wrapperFor(`/music/artists/Taylor%20Swift?tab=${tab}`),
    })

    expect(await screen.findByText('播放统计内容')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByLabelText('当前地址')).not.toHaveTextContent('tab='))
    expect(screen.queryByRole('button', { name: '发行周期' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '艺人生涯' })).not.toBeInTheDocument()
    expect(get.mock.calls.some(([path]) => String(path).includes('/release-cycle/'))).toBe(false)
    expect(post).not.toHaveBeenCalled()
  })

  it('normalizes the retired album era tab without release-cycle or AI requests', async () => {
    const get = vi.spyOn(api, 'get').mockImplementation((path: string) => {
      if (path === '/billboard/album/Midnights') {
        return Promise.resolve({
          found: true,
          album_name: 'Midnights',
          artist_name: 'Taylor Swift',
          cover_url: null,
          meta: null,
          info: null,
          chart_summary: null,
          album_project: null,
          album_weekly_history: [],
          album_no1_by_week: [],
          best_singles_overlay: [],
          tracks: [],
        })
      }
      return Promise.reject(new Error(`unexpected GET ${path}`))
    })
    const post = vi.spyOn(api, 'post')

    render(<AlbumDetailExperience />, {
      wrapper: wrapperFor('/music/albums/Midnights?artist=Taylor%20Swift&tab=era'),
    })

    expect(await screen.findByText('播放统计内容')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByLabelText('当前地址')).not.toHaveTextContent('tab='))
    expect(screen.queryByRole('button', { name: '发行档案' })).not.toBeInTheDocument()
    expect(get.mock.calls.some(([path]) => String(path).includes('/release-cycle/'))).toBe(false)
    expect(post).not.toHaveBeenCalled()
  })
})
