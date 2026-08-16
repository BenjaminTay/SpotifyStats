import { act, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { Masthead } from '@/components/layout/Masthead'
import { MusicSearchPage } from '@/features/music/search/MusicSearchPage'
import { ThemeProvider } from '@/hooks/useTheme'
import type { AnalysisFilters } from '@/types/analysis'
import type { MusicSearchCandidateResponse, MusicSearchContextResponse } from '@/types/music-search'

const filters: AnalysisFilters = {
  min_ms: 30_000,
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
  bb_week_start_hour: 12,
}

const hookMocks = vi.hoisted(() => ({
  useAnalysisFilters: vi.fn(),
  useMusicSearchCandidates: vi.fn(),
  useMusicSearchContext: vi.fn(),
}))

vi.mock('@/hooks/useAnalysis', () => ({
  useAnalysisFilters: hookMocks.useAnalysisFilters,
}))
vi.mock('@/features/music/search/useMusicSearch', () => ({
  useMusicSearchCandidates: hookMocks.useMusicSearchCandidates,
  useMusicSearchContext: hookMocks.useMusicSearchContext,
}))

const sampleResults: MusicSearchCandidateResponse = {
  response_version: 'music_search_v2',
  query: 'love',
  normalized_query: 'love',
  snapshot_status: 'ready',
  filter_fingerprint: 'fingerprint',
  kind: null,
  page: 1,
  page_size: 5,
  total: 1,
  total_by_kind: { track: 1, album: 0, artist: 0 },
  tracks: [{
    entity_key: 'track:42',
    kind: 'track',
    label: 'Cruel Summer',
    subtitle: 'Taylor Swift · Lover',
    href: '/music/tracks/42',
    track_id: 42,
    artist_id: null,
    album_name: 'Lover',
    artist_name: 'Taylor Swift',
    cover_url: null,
    match_field: 'label',
    match_quality: 'substring',
  }],
  albums: [],
  artists: [],
}

const sampleContext: MusicSearchContextResponse = {
  response_version: 'music_search_context_v1',
  snapshot_status: 'ready',
  filter_fingerprint: 'fingerprint',
  items: {
    'track:42': {
      play_events: 17,
      total_ms: 3_100_000,
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
  },
}

const keyboardResults: MusicSearchCandidateResponse = {
  ...sampleResults,
  total: 2,
  total_by_kind: { track: 2, album: 0, artist: 0 },
  tracks: [
    sampleResults.tracks[0],
    {
      ...sampleResults.tracks[0],
      entity_key: 'track:43',
      label: 'Lover',
      href: '/music/tracks/43',
      track_id: 43,
    },
  ],
}

const pagedTrackResults: MusicSearchCandidateResponse = {
  ...sampleResults,
  kind: 'track',
  page: 2,
  page_size: 20,
  total: 255,
  total_by_kind: { track: 255, album: 0, artist: 0 },
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

function BackButton() {
  const navigate = useNavigate()
  return <button type="button" onClick={() => navigate(-1)}>返回搜索</button>
}

describe('music search flow', () => {
  beforeEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
    sessionStorage.clear()
    mockMatchMedia()
    hookMocks.useAnalysisFilters.mockReturnValue({ filters, loading: false })
    hookMocks.useMusicSearchCandidates.mockReturnValue({
      data: sampleResults,
      initialLoading: false,
      updating: false,
      isPlaceholderData: false,
      error: null,
      refetch: vi.fn(),
    })
    hookMocks.useMusicSearchContext.mockReturnValue({
      data: sampleContext,
      loading: false,
      updating: false,
      error: null,
    })
  })

  it('hydrates q/kind/page from URL and uses 20-row kind pagination', () => {
    renderWithTheme(
      <Routes>
        <Route path="/music/search" element={<MusicSearchPage />} />
      </Routes>,
      '/music/search?q=love&kind=track&page=2',
    )

    expect(screen.getByRole('searchbox', { name: '搜索歌曲、专辑或艺人' })).toHaveValue('love')
    expect(hookMocks.useMusicSearchCandidates).toHaveBeenCalledWith(expect.objectContaining({
      query: 'love',
      kind: 'track',
      page: 2,
      pageSize: 20,
    }))
  })

  it('does not publish a composition query until compositionend plus debounce', () => {
    vi.useFakeTimers()
    renderWithTheme(
      <Routes>
        <Route path="/music/search" element={<><MusicSearchPage /><LocationSearchProbe /></>} />
      </Routes>,
      '/music/search?q=love',
    )

    const searchbox = screen.getByRole('searchbox', { name: '搜索歌曲、专辑或艺人' })
    fireEvent.compositionStart(searchbox)
    fireEvent.change(searchbox, { target: { value: '周杰伦' } })
    act(() => vi.advanceTimersByTime(300))
    expect(new URLSearchParams(screen.getByTestId('location-search').textContent ?? '').get('q')).toBe('love')
    expect(hookMocks.useMusicSearchCandidates).not.toHaveBeenLastCalledWith(expect.objectContaining({ query: '周杰伦' }))

    fireEvent.compositionEnd(searchbox)
    act(() => vi.advanceTimersByTime(300))
    expect(new URLSearchParams(screen.getByTestId('location-search').textContent ?? '').get('q')).toBe('周杰伦')
    expect(hookMocks.useMusicSearchCandidates).toHaveBeenLastCalledWith(expect.objectContaining({ query: '周杰伦' }))
    vi.useRealTimers()
  })

  it('opens with Cmd/Ctrl+K, excludes editable targets, and restores trigger focus', () => {
    renderWithTheme(<><input aria-label="editable" /><Masthead /></>)
    const editable = screen.getByRole('textbox', { name: 'editable' })
    fireEvent.keyDown(editable, { key: 'k', metaKey: true })
    expect(screen.queryByRole('dialog', { name: '搜索音乐详情' })).not.toBeInTheDocument()

    fireEvent.keyDown(window, { key: 'k', metaKey: true })
    expect(screen.getByRole('dialog', { name: '搜索音乐详情' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '关闭搜索' }))
    expect(screen.getByRole('button', { name: '搜索音乐详情' })).toHaveFocus()
  })

  it('keeps no default active option and supports Arrow/Enter navigation', () => {
    vi.useFakeTimers()
    hookMocks.useMusicSearchCandidates.mockReturnValue({
      data: keyboardResults,
      initialLoading: false,
      updating: false,
      isPlaceholderData: false,
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
    const combobox = screen.getByRole('combobox', { name: '搜索歌曲、专辑或艺人' })
    fireEvent.change(combobox, { target: { value: 'love' } })
    act(() => vi.advanceTimersByTime(260))

    const options = screen.getAllByRole('option')
    expect(options[0]).toHaveAttribute('aria-selected', 'false')
    expect(options[1]).toHaveAttribute('aria-selected', 'false')
    fireEvent.keyDown(combobox, { key: 'ArrowDown' })
    expect(options[0]).toHaveAttribute('aria-selected', 'true')
    fireEvent.keyDown(combobox, { key: 'ArrowDown' })
    expect(options[1]).toHaveAttribute('aria-selected', 'true')
    fireEvent.keyDown(combobox, { key: 'Enter' })
    expect(screen.getByText('Track 43 reached')).toBeInTheDocument()
    vi.useRealTimers()
  })

  it('unmounts the Quick Open candidate observer when the dialog closes', () => {
    vi.useFakeTimers()
    renderWithTheme(<Masthead />)
    fireEvent.click(screen.getByRole('button', { name: '搜索音乐详情' }))
    const combobox = screen.getByRole('combobox', { name: '搜索歌曲、专辑或艺人' })
    fireEvent.change(combobox, { target: { value: 'love' } })
    act(() => vi.advanceTimersByTime(260))
    expect(hookMocks.useMusicSearchCandidates).toHaveBeenLastCalledWith(expect.objectContaining({
      query: 'love',
    }))

    fireEvent.click(screen.getByRole('button', { name: '关闭搜索' }))
    expect(screen.queryByRole('dialog', { name: '搜索音乐详情' })).not.toBeInTheDocument()
    vi.useRealTimers()
  })

  it('restores a POP result position only after deferred candidates make the page scrollable', () => {
    let candidateResult: ReturnType<typeof hookMocks.useMusicSearchCandidates> = {
      data: pagedTrackResults,
      initialLoading: false,
      updating: false,
      isPlaceholderData: false,
      error: null,
      refetch: vi.fn(),
    }
    hookMocks.useMusicSearchCandidates.mockImplementation(() => candidateResult)

    const scrollTo = vi.fn()
    const animationFrames: FrameRequestCallback[] = []
    let scrollHeight = 700
    vi.stubGlobal('scrollY', 600)
    vi.stubGlobal('innerHeight', 800)
    vi.stubGlobal('scrollTo', scrollTo)
    vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => {
      animationFrames.push(callback)
      return animationFrames.length
    }))
    vi.stubGlobal('cancelAnimationFrame', vi.fn())
    Object.defineProperty(document.documentElement, 'scrollHeight', {
      configurable: true,
      get: () => scrollHeight,
    })

    const renderTree = () => (
      <ThemeProvider>
        <MemoryRouter initialEntries={['/music/search?q=love&kind=track&page=2']}>
          <Routes>
            <Route path="/music/search" element={<MusicSearchPage />} />
            <Route path="/music/tracks/42" element={<BackButton />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    )
    const view = render(renderTree())

    fireEvent.click(screen.getByRole('link', { name: /Cruel Summer/ }))
    expect(sessionStorage.getItem(
      'spotify-stats:music-search-scroll:/music/search?q=love&kind=track&page=2',
    )).toBe('600')

    candidateResult = {
      data: null,
      initialLoading: true,
      updating: false,
      isPlaceholderData: false,
      error: null,
      refetch: vi.fn(),
    }
    fireEvent.click(screen.getByRole('button', { name: '返回搜索' }))
    expect(screen.getByTestId('music-search-loading-message')).toBeInTheDocument()
    expect(scrollTo).not.toHaveBeenCalled()

    candidateResult = {
      data: pagedTrackResults,
      initialLoading: false,
      updating: false,
      isPlaceholderData: false,
      error: null,
      refetch: vi.fn(),
    }
    view.rerender(renderTree())

    expect(screen.getByText('21–40 / 255 · 第 2 / 13 页')).toBeInTheDocument()
    expect(scrollTo).not.toHaveBeenCalled()
    act(() => animationFrames.shift()?.(0))
    expect(scrollTo).not.toHaveBeenCalled()

    scrollHeight = 2_000
    act(() => animationFrames.shift()?.(16))
    expect(scrollTo).toHaveBeenCalledTimes(1)
    expect(scrollTo).toHaveBeenCalledWith({ top: 600, behavior: 'auto' })

    view.unmount()
    Reflect.deleteProperty(document.documentElement, 'scrollHeight')
    vi.unstubAllGlobals()
  })

  it('does not reuse a saved position for ordinary kind navigation', () => {
    sessionStorage.setItem(
      'spotify-stats:music-search-scroll:/music/search?q=love&kind=album',
      '600',
    )
    const scrollTo = vi.fn()
    vi.stubGlobal('scrollTo', scrollTo)

    const view = renderWithTheme(
      <Routes>
        <Route path="/music/search" element={<><MusicSearchPage /><LocationSearchProbe /></>} />
      </Routes>,
      '/music/search?q=love&kind=track',
    )

    fireEvent.click(screen.getByRole('tab', { name: '专辑' }))

    expect(screen.getByTestId('location-search')).toHaveTextContent('?q=love&kind=album')
    expect(scrollTo).not.toHaveBeenCalled()

    view.unmount()
    vi.unstubAllGlobals()
  })
})
