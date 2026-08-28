import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MusicSearchResults } from '@/features/music/search/MusicSearchResults'
import { HighlightedSearchText } from '@/features/music/search/HighlightedSearchText'
import { setChineseStyle } from '@/lib/chinese'
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
  afterEach(() => localStorage.removeItem('chineseStyle'))

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

  it('keeps last-known-good candidates clickable while the new index and statistics rebuild', () => {
    renderResults({
      ...sampleResults,
      snapshot_status: 'warming',
      candidate_status: 'degraded',
      candidate_freshness: 'last_known_good',
      statistics_status: 'warming',
      statistics_freshness: 'last_known_good',
      served_filter_fingerprint: 'previous-fingerprint',
      target_filter_fingerprint: 'next-fingerprint',
    }, 'love', {
      ...sampleContext,
      snapshot_status: 'warming',
      statistics_status: 'warming',
      statistics_freshness: 'last_known_good',
      served_filter_fingerprint: 'previous-fingerprint',
      filter_fingerprint: 'previous-fingerprint',
    })

    expect(screen.getByText('搜索索引正在更新')).toBeInTheDocument()
    expect(screen.getByText(/当前继续使用上一可用版本/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Cruel Summer/ })).toHaveAttribute('href', '/music/tracks/42')
    expect(screen.getAllByText('上一版本').length).toBeGreaterThan(0)
    expect(screen.queryByText('搜索暂不可用')).not.toBeInTheDocument()
  })

  it('shows a non-blocking statistics notice alongside a valid empty candidate result', () => {
    renderResults({
      ...sampleResults,
      snapshot_status: 'warming',
      candidate_status: 'ready',
      candidate_freshness: 'current',
      statistics_status: 'warming',
      statistics_freshness: 'unavailable',
      total: 0,
      total_by_kind: { track: 0, album: 0, artist: 0 },
      tracks: [], albums: [], artists: [],
    }, 'zzzz', null)

    expect(screen.getByText('搜索可用，播放统计正在更新')).toBeInTheDocument()
    expect(screen.getByText('没有找到匹配的音乐详情')).toBeInTheDocument()
    expect(screen.queryByText('搜索暂不可用')).not.toBeInTheDocument()
  })

  it('does not replace candidates when statistics maintenance fails', () => {
    renderResults({
      ...sampleResults,
      snapshot_status: 'failed',
      candidate_status: 'ready',
      candidate_freshness: 'current',
      statistics_status: 'failed',
      statistics_freshness: 'last_known_good',
    })

    expect(screen.getByText('搜索可用，播放统计更新失败')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Cruel Summer/ })).toBeInTheDocument()
  })

  it('labels bounded local-catalog fallback without hiding its candidates', () => {
    renderResults({
      ...sampleResults,
      snapshot_status: 'unavailable',
      candidate_status: 'degraded',
      candidate_freshness: 'fallback',
      statistics_status: 'unavailable',
      statistics_freshness: 'unavailable',
      served_filter_fingerprint: null,
    }, 'love', null)

    expect(screen.getByText('正在使用基础搜索')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Cruel Summer/ })).toBeInTheDocument()
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

  it('highlights the matched subtitle field without showing match diagnostics', () => {
    const artistMatch = {
      ...sampleResults,
      query: 'taylor',
      normalized_query: 'taylor',
      tracks: [{ ...sampleResults.tracks[0], match_field: 'artist' as const }],
    }
    const { container, unmount } = renderResults(artistMatch, 'taylor', null)
    expect(container.querySelector('mark')).toHaveTextContent('Taylor')
    expect(screen.queryByText('匹配艺人', { exact: false })).not.toBeInTheDocument()
    unmount()

    renderResults({
      ...sampleResults,
      tracks: [{ ...sampleResults.tracks[0], match_field: 'alias' }],
    }, 'swiftie', null)
    expect(screen.queryByText('匹配别名', { exact: false })).not.toBeInTheDocument()
    expect(screen.queryByText('swiftie')).not.toBeInTheDocument()
  })

  it('does not expose Chinese-variant or fuzzy-match diagnostics', () => {
    const { unmount } = renderResults({
      ...sampleResults,
      tracks: [{ ...sampleResults.tracks[0], match_type: 'traditional' }],
    }, '周杰伦', null)
    expect(screen.queryByText('简繁匹配', { exact: false })).not.toBeInTheDocument()
    unmount()

    renderResults({
      ...sampleResults,
      tracks: [{
        ...sampleResults.tracks[0],
        match_quality: 'fuzzy',
        match_type: 'fuzzy',
      }],
    }, 'cardgan', null)
    expect(screen.queryByText('近似匹配', { exact: false })).not.toBeInTheDocument()
  })

  it('follows global Chinese display preference changes without changing links', async () => {
    const traditionalResult: MusicSearchCandidateResponse = {
      ...sampleResults,
      query: '認了吧',
      normalized_query: '認了吧',
      total: 1,
      total_by_kind: { track: 1, album: 0, artist: 0 },
      tracks: [{
        ...sampleResults.tracks[0],
        label: '認了吧',
        subtitle: '陳奕迅 · 認了吧',
        href: '/music/tracks/42?title=%E8%AA%8D%E4%BA%86%E5%90%A7',
      }],
      albums: [],
      artists: [],
    }

    const { container } = renderResults(traditionalResult, '認了吧', null)
    expect(container).toHaveTextContent('陳奕迅 · 認了吧')

    act(() => setChineseStyle('simplified'))

    await waitFor(() => expect(container).toHaveTextContent('认了吧'))
    expect(container).toHaveTextContent('陈奕迅 · 认了吧')
    expect(container).not.toHaveTextContent('認了吧')
    expect(screen.getByRole('link', { name: /认了吧/ })).toHaveAttribute(
      'href',
      '/music/tracks/42?title=%E8%AA%8D%E4%BA%86%E5%90%A7',
    )
    expect(screen.getByRole('img', { name: '认了吧 封面' })).toBeInTheDocument()
  })
})
