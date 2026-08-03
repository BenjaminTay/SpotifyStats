import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ArtistDetailHero } from '@/features/music/details/MusicDetailHeader'
import type { ArtistDetailResponse } from '@/types/billboard'

function detail(meta: ArtistDetailResponse['meta']): ArtistDetailResponse {
  return {
    found: true,
    artist_name: 'Jolin Tsai',
    cover_url: null,
    meta,
    info: {} as ArtistDetailResponse['info'],
    chart_summary: {} as ArtistDetailResponse['chart_summary'],
    artist_weekly_history: [],
    artist_no1_by_week: [],
    week_no1_albums: [],
    best_singles_overlay: [],
    best_albums_overlay: [],
    tracks: [],
    albums: [],
  }
}

describe('artist detail provider metadata', () => {
  it('renders merged identity followers and popularity in the hero', () => {
    render(
      <ArtistDetailHero
        data={detail({ followers: 1_239_003, popularity: 61, genres: ['mandopop'] })}
        onBack={vi.fn()}
      />,
    )

    expect(screen.getByText('1.2M followers')).toBeInTheDocument()
    expect(screen.getByText('61')).toBeInTheDocument()
    expect(screen.getByText('Mandopop')).toBeInTheDocument()
  })

  it('does not hide a legitimate zero follower count', () => {
    render(<ArtistDetailHero data={detail({ followers: 0, popularity: 0 })} onBack={vi.fn()} />)

    expect(screen.getByText('0 followers')).toBeInTheDocument()
    expect(screen.getByText('0', { selector: 'span.font-semibold' })).toBeInTheDocument()
  })
})
