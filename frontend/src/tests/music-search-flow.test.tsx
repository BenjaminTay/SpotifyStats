import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
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
      artist_id: null,
      album_name: 'Lover',
      artist_name: 'Taylor Swift',
      cover_url: null,
      chart: {
        peak_position: 1,
        peak_weeks: 2,
        weeks_on_chart: 12,
        weeks_at_no1: 3,
        power_score: 1234,
        power_rank: 8,
        first_week: '2026-01-02',
        latest_week: '2026-03-20',
        first_peak_week: '2026-01-09',
      },
    },
  ],
  albums: [],
  artists: [],
}

const keyboardResults: MusicSearchResponse = {
  ...sampleResults,
  total: 2,
  tracks: [
    sampleResults.tracks[0],
    {
      ...sampleResults.tracks[0],
      label: 'Lover',
      href: '/music/tracks/43',
      track_id: 43,
      play_events: 9,
      chart: {
        peak_position: 3,
        peak_weeks: 1,
        weeks_on_chart: 4,
        weeks_at_no1: 0,
        power_score: 820,
        power_rank: 18,
        first_week: '2026-02-06',
        latest_week: '2026-02-27',
        first_peak_week: '2026-02-13',
      },
    },
  ],
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

function LocationSearchProbe() {
  const location = useLocation()
  return <output data-testid="location-search">{location.search}</output>
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
    expect(hookMocks.useMusicSearch).toHaveBeenCalledWith('love', undefined, 5, { includeChart: true })
    expect(screen.getByRole('link', { name: /Cruel Summer/ })).toHaveAttribute('href', '/music/tracks/42')
  })

  it('uses the compact mobile result hierarchy and waits for IME composition before updating q', () => {
    vi.useFakeTimers()
    mockMatchMedia(true)

    renderWithTheme(
      <Routes>
        <Route path="/music/search" element={<><MusicSearchPage /><LocationSearchProbe /></>} />
      </Routes>,
      '/music/search?q=love',
    )

    const searchbox = screen.getByRole('searchbox', { name: '搜索歌曲、专辑或艺人' })
    expect(screen.queryByRole('heading', { name: '音乐查找' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Cruel Summer/ })).toHaveTextContent('PK #1')
    expect(screen.getByRole('link', { name: /Cruel Summer/ })).toHaveTextContent('走势 #8')

    fireEvent.compositionStart(searchbox)
    fireEvent.change(searchbox, { target: { value: '周杰伦' } })
    act(() => vi.advanceTimersByTime(300))
    expect(new URLSearchParams(screen.getByTestId('location-search').textContent ?? '').get('q')).toBe('love')

    fireEvent.compositionEnd(searchbox)
    act(() => vi.advanceTimersByTime(300))
    expect(new URLSearchParams(screen.getByTestId('location-search').textContent ?? '').get('q')).toBe('周杰伦')

    vi.useRealTimers()
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
    expect(screen.getByText('PK #1')).toBeInTheDocument()
    expect(screen.getByText('在榜 12周')).toBeInTheDocument()
    expect(screen.getByText('走势 #8')).toBeInTheDocument()
    expect(screen.queryByText('冠军 3 周')).not.toBeInTheDocument()
    expect(hookMocks.useMusicSearch).toHaveBeenCalledWith('love', undefined, 5, { includeChart: true })
    expect(screen.getByRole('link', { name: '查看全部结果' })).toHaveAttribute('href', '/music/search?q=love')

    vi.useRealTimers()
  })

  it('shows a clear loading message while quick search is waiting for chart results', () => {
    vi.useFakeTimers()
    hookMocks.useMusicSearch.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: vi.fn(),
    })

    renderWithTheme(<Masthead />)

    fireEvent.click(screen.getByRole('button', { name: '搜索音乐详情' }))
    fireEvent.change(screen.getByRole('searchbox', { name: '搜索歌曲、专辑或艺人' }), {
      target: { value: 'love' },
    })

    act(() => {
      vi.advanceTimersByTime(260)
    })

    expect(screen.getByText('正在加载搜索结果…')).toBeInTheDocument()

    vi.useRealTimers()
  })

  it('lets keyboard users select quick search results and open the active result', () => {
    vi.useFakeTimers()
    hookMocks.useMusicSearch.mockReturnValue({
      data: keyboardResults,
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    renderWithTheme(
      <Routes>
        <Route path="/" element={<Masthead />} />
        <Route path="/music/tracks/43" element={<div>Track 43 reached</div>} />
      </Routes>,
    )

    fireEvent.click(screen.getByRole('button', { name: '搜索音乐详情' }))
    const searchbox = screen.getByRole('searchbox', { name: '搜索歌曲、专辑或艺人' })
    fireEvent.change(searchbox, {
      target: { value: 'love' },
    })

    act(() => {
      vi.advanceTimersByTime(260)
    })

    const firstResult = screen.getByRole('link', { name: /Cruel Summer/ })
    const secondResult = screen.getByRole('link', { name: /PK #3/ })
    expect(firstResult).not.toHaveAttribute('aria-current')
    expect(secondResult).not.toHaveAttribute('aria-current')

    fireEvent.keyDown(searchbox, { key: 'ArrowDown' })
    expect(firstResult).toHaveAttribute('aria-current', 'true')

    fireEvent.keyDown(searchbox, { key: 'ArrowDown' })
    expect(secondResult).toHaveAttribute('aria-current', 'true')

    fireEvent.keyDown(searchbox, { key: 'Enter' })
    expect(screen.getByText('Track 43 reached')).toBeInTheDocument()

    vi.useRealTimers()
  })
})
