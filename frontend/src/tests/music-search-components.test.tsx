import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { MusicSearchResults } from '@/features/music/search/MusicSearchResults'
import type { MusicSearchResponse } from '@/types/music-search'

const sampleResults: MusicSearchResponse = {
  query: 'love',
  limit_per_type: 5,
  total: 3,
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
      cover_url: '/covers/albums/42.jpg',
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
  albums: [
    {
      kind: 'album',
      label: 'Lover',
      subtitle: 'Taylor Swift',
      href: '/music/albums/Lover?artist=Taylor%20Swift',
      play_events: 82,
      total_ms: 12000000,
      track_id: null,
      album_name: 'Lover',
      artist_name: 'Taylor Swift',
      cover_url: null,
      chart: null,
    },
  ],
  artists: [
    {
      kind: 'artist',
      label: 'Taylor Swift',
      subtitle: '82 次播放',
      href: '/music/artists/Taylor%20Swift',
      play_events: 82,
      total_ms: 12000000,
      track_id: null,
      album_name: null,
      artist_name: 'Taylor Swift',
      cover_url: null,
      chart: null,
    },
  ],
}

function renderResults(data: MusicSearchResponse | null, query = 'love') {
  return render(
    <MemoryRouter>
      <MusicSearchResults data={data} query={query} />
    </MemoryRouter>,
  )
}

function renderCompactLoading() {
  return render(
    <MemoryRouter>
      <MusicSearchResults data={null} query="love" loading compact />
    </MemoryRouter>,
  )
}

describe('MusicSearchResults', () => {
  it('renders separated result groups with restrained chart summaries', () => {
    renderResults(sampleResults)

    const trackGroup = screen.getByRole('region', { name: '单曲结果' })
    const albumGroup = screen.getByRole('region', { name: '专辑结果' })
    const artistGroup = screen.getByRole('region', { name: '艺人结果' })
    expect(within(trackGroup).getByText('1')).toBeInTheDocument()
    expect(within(albumGroup).getByText('1')).toBeInTheDocument()
    expect(within(artistGroup).getByText('1')).toBeInTheDocument()

    const trackItem = within(trackGroup).getByRole('listitem')
    expect(within(trackItem).getByRole('link', { name: /Cruel Summer/ })).toHaveAttribute('href', '/music/tracks/42')
    expect(within(trackItem).getByRole('img', { name: 'Cruel Summer 封面' })).toHaveAttribute('src', '/covers/albums/42.jpg')
    expect(within(trackItem).getByText('Taylor Swift · Lover')).toBeInTheDocument()
    expect(within(trackItem).getByText('17 次播放')).toBeInTheDocument()
    expect(within(trackItem).getByText('PK #1')).toBeInTheDocument()
    expect(within(trackItem).getByText('在榜 12周')).toBeInTheDocument()
    expect(within(trackItem).getByText('走势 #8')).toBeInTheDocument()
    expect(screen.queryByText('冠军 3 周')).not.toBeInTheDocument()
    expect(screen.queryByText('2wks')).not.toBeInTheDocument()
    expect(screen.queryByText('未入榜')).not.toBeInTheDocument()

    expect(within(albumGroup).getByRole('link', { name: /Lover/ })).toHaveAttribute(
      'href',
      '/music/albums/Lover?artist=Taylor%20Swift',
    )
    expect(within(artistGroup).getByRole('link', { name: /Taylor Swift/ })).toHaveAttribute(
      'href',
      '/music/artists/Taylor%20Swift',
    )
  })

  it('shows an empty state after a non-empty query has no matches', () => {
    renderResults({ ...sampleResults, total: 0, tracks: [], albums: [], artists: [] }, 'zzzz')

    expect(screen.getByText('没有找到匹配的音乐详情')).toBeInTheDocument()
  })

  it('prompts before the user enters a query', () => {
    renderResults(null, '')

    expect(screen.getByText('输入歌曲、专辑或艺人名称开始查找')).toBeInTheDocument()
  })

  it('keeps quick search loading as a single compact status row', () => {
    renderCompactLoading()

    const status = screen.getByRole('status', { name: '正在查找音乐详情' })
    expect(within(status).getByText('正在加载搜索结果…')).toBeInTheDocument()
    expect(within(status).getByText('匹配播放记录与榜单信息')).toBeInTheDocument()
    expect(within(status).queryAllByTestId('music-search-loading-row')).toHaveLength(0)
    expect(within(status).getByTestId('music-search-loading-message')).toHaveClass('py-2')
  })
})
