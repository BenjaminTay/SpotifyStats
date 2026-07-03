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

describe('MusicSearchResults', () => {
  it('renders grouped local music search results with detail links', () => {
    renderResults(sampleResults)

    const trackGroup = screen.getByRole('region', { name: '单曲结果' })
    expect(within(trackGroup).getByRole('link', { name: /Cruel Summer/ })).toHaveAttribute('href', '/music/tracks/42')
    expect(within(trackGroup).getByRole('img', { name: 'Cruel Summer 封面' })).toHaveAttribute('src', '/covers/albums/42.jpg')
    expect(within(trackGroup).getByText('Taylor Swift · Lover')).toBeInTheDocument()
    expect(within(trackGroup).getByText('17 次播放')).toBeInTheDocument()

    const albumGroup = screen.getByRole('region', { name: '专辑结果' })
    expect(within(albumGroup).getByRole('link', { name: /Lover/ })).toHaveAttribute(
      'href',
      '/music/albums/Lover?artist=Taylor%20Swift',
    )

    const artistGroup = screen.getByRole('region', { name: '艺人结果' })
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
})
