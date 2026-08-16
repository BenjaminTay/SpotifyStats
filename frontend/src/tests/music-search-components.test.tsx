import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { MusicSearchResults } from '@/features/music/search/MusicSearchResults'
import { HighlightedSearchText } from '@/features/music/search/HighlightedSearchText'
import type { MusicSearchCandidateResponse, MusicSearchContextResponse } from '@/types/music-search'

const sampleResults: MusicSearchCandidateResponse = {
  response_version: 'music_search_v2',
  query: 'love',
  normalized_query: 'love',
  snapshot_status: 'ready',
  filter_fingerprint: 'fingerprint',
  kind: null,
  page: 1,
  page_size: 5,
  total: 12,
  total_by_kind: { track: 8, album: 3, artist: 1 },
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
    cover_url: '/covers/albums/42.jpg',
    match_field: 'label',
    match_quality: 'substring',
  }],
  albums: [{
    entity_key: 'album_project:7',
    kind: 'album',
    label: 'Lover',
    subtitle: 'Taylor Swift',
    href: '/music/albums/Lover?artist=Taylor%20Swift',
    track_id: null,
    artist_id: null,
    album_name: 'Lover',
    artist_name: 'Taylor Swift',
    cover_url: null,
    match_field: 'label',
    match_quality: 'exact',
  }],
  artists: [{
    entity_key: 'artist:13',
    kind: 'artist',
    label: 'Taylor Swift',
    subtitle: null,
    href: '/music/artists/Taylor%20Swift',
    track_id: null,
    artist_id: 13,
    album_name: null,
    artist_name: 'Taylor Swift',
    cover_url: null,
    match_field: 'label',
    match_quality: 'substring',
  }],
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
    'album_project:7': { play_events: 82, total_ms: 12_000_000, chart: null },
    'artist:13': { play_events: 82, total_ms: 12_000_000, chart: null },
  },
}

function renderResults(
  data: MusicSearchCandidateResponse | null,
  query = 'love',
  contextData: MusicSearchContextResponse | null = sampleContext,
) {
  return render(
    <MemoryRouter>
      <MusicSearchResults data={data} contextData={contextData} query={query} showGroupLinks />
    </MemoryRouter>,
  )
}

function replaceIntlSegmenter(value: unknown): () => void {
  const descriptor = Object.getOwnPropertyDescriptor(Intl, 'Segmenter')
  Object.defineProperty(Intl, 'Segmenter', {
    configurable: true,
    writable: true,
    value,
  })
  return () => {
    if (descriptor) Object.defineProperty(Intl, 'Segmenter', descriptor)
    else Reflect.deleteProperty(Intl, 'Segmenter')
  }
}

describe('MusicSearchResults', () => {
  it('renders exact totals and progressive context without exposing championship weeks', () => {
    renderResults(sampleResults)

    const trackGroup = screen.getByRole('group', { name: '单曲结果' })
    expect(within(trackGroup).getByRole('link', { name: '查看全部 8 个' })).toBeInTheDocument()
    expect(screen.getByText('查看全部 3 个')).toBeInTheDocument()
    expect(within(trackGroup).getByRole('link', { name: /Cruel Summer/ })).toHaveAttribute('href', '/music/tracks/42')
    expect(within(trackGroup).getByRole('img', { name: 'Cruel Summer 封面' })).toHaveAttribute('src', '/covers/albums/42.jpg')
    expect(within(trackGroup).getByText('17 次播放')).toBeInTheDocument()
    expect(within(trackGroup).getByText('PK #1')).toBeInTheDocument()
    expect(within(trackGroup).getByText('在榜 12周')).toBeInTheDocument()
    expect(within(trackGroup).getByText('走势 #8')).toBeInTheDocument()
    expect(screen.queryByText('冠军 3 周')).not.toBeInTheDocument()
  })

  it('never turns missing context into zero plays and keeps links usable', () => {
    renderResults(sampleResults, 'love', null)

    expect(screen.queryByText('0 次播放')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Cruel Summer/ })).toHaveAttribute('href', '/music/tracks/42')
  })

  it('distinguishes snapshot warming from an empty result', () => {
    renderResults({
      ...sampleResults,
      snapshot_status: 'warming',
      total: 0,
      total_by_kind: { track: 0, album: 0, artist: 0 },
      tracks: [],
      albums: [],
      artists: [],
    }, 'zzzz', null)

    expect(screen.getByText('搜索数据正在准备')).toBeInTheDocument()
    expect(screen.getByText(/准备完成后会自动刷新/)).toBeInTheDocument()
    expect(screen.queryByText('没有找到匹配的音乐详情')).not.toBeInTheDocument()
  })

  it('offers a manual recheck for unavailable data and keeps public copy cache-only', () => {
    const onRetry = vi.fn()
    render(
      <MemoryRouter>
        <MusicSearchResults
          data={{
            ...sampleResults,
            snapshot_status: 'unavailable',
            total: 0,
            total_by_kind: { track: 0, album: 0, artist: 0 },
            tracks: [], albums: [], artists: [],
          }}
          query="love"
          onRetry={onRetry}
          maintenanceHref="/settings#music-metadata-management"
          publicReadonly
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('搜索暂不可用')).toBeInTheDocument()
    expect(screen.getByText(/公开页面只读取已准备的数据/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '重新检查' }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('shows an empty state only for a ready snapshot with no matches', () => {
    renderResults({
      ...sampleResults,
      total: 0,
      total_by_kind: { track: 0, album: 0, artist: 0 },
      tracks: [],
      albums: [],
      artists: [],
    }, 'zzzz', null)

    expect(screen.getByText('没有找到匹配的音乐详情')).toBeInTheDocument()
  })

  it('prompts before the user enters a query', () => {
    renderResults(null, '', null)
    expect(screen.getByText('输入歌曲、专辑或艺人名称开始查找')).toBeInTheDocument()
  })

  it('uses fixed loading rows before the first candidate response', () => {
    render(
      <MemoryRouter>
        <MusicSearchResults data={null} query="love" initialLoading compact />
      </MemoryRouter>,
    )
    const status = screen.getByRole('status', { name: '正在查找音乐详情' })
    expect(within(status).getByText('正在加载搜索结果…')).toBeInTheDocument()
    expect(within(status).getAllByTestId('music-search-loading-row')).toHaveLength(3)
  })

  it('highlights matching text with React nodes and never interprets entity labels as HTML', () => {
    const { container } = render(
      <HighlightedSearchText text={'<img src=x onerror="alert(1)"> Love'} query="love" />,
    )

    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('mark')).toHaveTextContent('Love')
    expect(container).toHaveTextContent('<img src=x onerror="alert(1)"> Love')
  })

  it.each([
    ['“Don’t”—Stop', '"don\'t"-stop', '“Don’t”—Stop'],
    ['ＴＡＹＬＯＲ', 'taylor', 'ＴＡＹＬＯＲ'],
    ['Rock\u00a0\u2003Roll', 'rock roll', 'Rock\u00a0\u2003Roll'],
    ['Straße', 'strasse', 'Straße'],
    ['你好。世界', '.', '。'],
  ])('maps normalized query %s back to safe original graphemes', (text, query, markedText) => {
    const { container } = render(<HighlightedSearchText text={text} query={query} />)
    expect(container.querySelector('mark')?.textContent).toBe(markedText)
    expect(container.textContent).toBe(text)
  })

  it.each([
    ['missing', undefined],
    ['non-constructable', () => undefined],
  ])('uses a code-point safe fallback when Intl.Segmenter is %s', (_label, segmenter) => {
    const restore = replaceIntlSegmenter(segmenter)
    try {
      const text = 'Go 😀 Cafe\u0301。'
      const { container } = render(
        <HighlightedSearchText text={text} query="😀 café." />,
      )
      expect(container.querySelector('mark')?.textContent).toBe('😀 Cafe\u0301。')
      expect(container.textContent).toBe(text)
      expect(container.textContent).not.toContain('\ufffd')
    } finally {
      restore()
    }
  })

  it('highlights the matched subtitle field and labels invisible alias matches', () => {
    const artistMatch = {
      ...sampleResults,
      query: 'taylor',
      normalized_query: 'taylor',
      tracks: [{ ...sampleResults.tracks[0], match_field: 'artist' as const }],
    }
    const { container, unmount } = renderResults(artistMatch, 'taylor', null)
    expect(container.querySelector('mark')).toHaveTextContent('Taylor')
    expect(screen.getByText('匹配艺人', { exact: false })).toBeInTheDocument()
    unmount()

    renderResults({
      ...sampleResults,
      tracks: [{ ...sampleResults.tracks[0], match_field: 'alias' }],
    }, 'swiftie', null)
    expect(screen.getByText('匹配别名', { exact: false })).toBeInTheDocument()
    expect(screen.queryByText('swiftie')).not.toBeInTheDocument()
  })

  it('explains deterministic Chinese variants and fuzzy matches', () => {
    const { unmount } = renderResults({
      ...sampleResults,
      tracks: [{ ...sampleResults.tracks[0], match_type: 'traditional' }],
    }, '周杰伦', null)
    expect(screen.getByText('简繁匹配', { exact: false })).toBeInTheDocument()
    unmount()

    renderResults({
      ...sampleResults,
      tracks: [{
        ...sampleResults.tracks[0],
        match_quality: 'fuzzy',
        match_type: 'fuzzy',
      }],
    }, 'cardgan', null)
    expect(screen.getByText('近似匹配', { exact: false })).toBeInTheDocument()
  })
})
