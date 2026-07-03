import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { Masthead } from '@/components/layout/Masthead'
import { MusicSearchPage } from '@/features/music/search/MusicSearchPage'
import { ThemeProvider } from '@/hooks/useTheme'
import type { MusicSearchResponse } from '@/types/music-search'

const hookMocks = vi.hoisted(() => ({
  useMusicSearch: vi.fn(),
}))

vi.mock('@/hooks/useAnalysis', () => hookMocks)

const sampleResults: MusicSearchResponse = {
  query: 'love',
  limit_per_type: 5,
  total: 1,
  tracks: [
    {
      kind: 'track',
      label: 'Cruel Summer',
      subtitle: 'Taylor Swift · Lover',
      href: '/music/tracks/42',
      play_events: 17,
      total_ms: 3100000,
      track_id: 42,
      album_name: 'Lover',
      artist_name: 'Taylor Swift',
      cover_url: null,
    },
  ],
  albums: [],
  artists: [],
}

function mockMatchMedia(matches = false) {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}

function renderWithTheme(ui: React.ReactElement, path = '/') {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
    </ThemeProvider>,
  )
}

describe('music search flow', () => {
  beforeEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
    mockMatchMedia()
    hookMocks.useMusicSearch.mockReturnValue({
      data: sampleResults,
      loading: false,
      error: null,
      refetch: vi.fn(),
    })
  })

  it('hydrates the full search page from the q URL parameter', () => {
    renderWithTheme(
      <Routes>
        <Route path="/music/search" element={<MusicSearchPage />} />
      </Routes>,
      '/music/search?q=love',
    )

    expect(screen.getByRole('searchbox', { name: '搜索歌曲、专辑或艺人' })).toHaveValue('love')
    expect(hookMocks.useMusicSearch).toHaveBeenCalledWith('love', undefined, 5)
    expect(screen.getByRole('link', { name: /Cruel Summer/ })).toHaveAttribute('href', '/music/tracks/42')
  })

  it('opens Masthead quick search and links to the full search page', async () => {
    vi.useFakeTimers()

    renderWithTheme(<Masthead />)

    fireEvent.click(screen.getByRole('button', { name: '搜索音乐详情' }))
    expect(screen.getByRole('dialog', { name: '搜索音乐详情' })).toBeInTheDocument()

    fireEvent.change(screen.getByRole('searchbox', { name: '搜索歌曲、专辑或艺人' }), {
      target: { value: 'love' },
    })

    act(() => {
      vi.advanceTimersByTime(260)
    })

    expect(screen.getByRole('link', { name: /Cruel Summer/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '查看全部结果' })).toHaveAttribute('href', '/music/search?q=love')

    vi.useRealTimers()
  })
})
