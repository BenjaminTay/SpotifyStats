import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'
import { LegacyTrackDetailRedirect } from '@/pages/LegacyTrackDetailRedirect'

vi.mock('@/lib/api', () => ({ api: { get: vi.fn() } }))

function LocationProbe() {
  const location = useLocation()
  return <span data-testid="location">{location.pathname}{location.search}</span>
}

function renderRoute() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/legacy-track/77?tab=overview']}>
        <Routes>
          <Route path="/legacy-track/:legacyTrackId" element={<LegacyTrackDetailRedirect />} />
          <Route path="/music/tracks/:trackId" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('旧歌曲链接兼容解析', () => {
  beforeEach(() => vi.mocked(api.get).mockReset())

  it('唯一映射时保留查询参数并跳到正式 track_id 地址', async () => {
    vi.mocked(api.get).mockResolvedValue({
      source_track_id: 77,
      resolution: 'unique',
      items: [{ l1_id: 912, track_name: 'Song', artist_name: 'Artist' }],
    })
    renderRoute()
    expect(await screen.findByTestId('location')).toHaveTextContent('/music/tracks/912?tab=overview')
  })

  it('一条原始记录承载多个 Spotify ID 时要求用户明确选择', async () => {
    vi.mocked(api.get).mockResolvedValue({
      source_track_id: 77,
      resolution: 'ambiguous',
      items: [
        { l1_id: 912, spotify_track_id: 'spotify-a', track_name: 'Song A', artist_name: 'Artist', cover_url: null },
        { l1_id: 913, spotify_track_id: 'spotify-b', track_name: 'Song B', artist_name: 'Artist', cover_url: null },
      ],
    })
    renderRoute()
    expect(await screen.findByRole('heading', { name: '请选择具体的 Spotify 曲目' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Song A/ })).toHaveAttribute('href', '/music/tracks/912?tab=overview')
    expect(screen.getByRole('link', { name: /Song B/ })).toHaveAttribute('href', '/music/tracks/913?tab=overview')
  })
})
