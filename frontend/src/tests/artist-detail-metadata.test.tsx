import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import { AlbumDetailHero, ArtistDetailHero } from '@/features/music/details/MusicDetailHeader'
import type { AlbumDetailResponse, ArtistDetailResponse } from '@/types/billboard'

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
    render(<MemoryRouter><ArtistDetailHero data={detail({ followers: 1_239_003, popularity: 61, genres: ['mandopop'] })} onBack={vi.fn()} /></MemoryRouter>)

    expect(screen.getByText('1.2M followers')).toBeInTheDocument()
    expect(screen.getByText('61')).toBeInTheDocument()
    expect(screen.getByText('Mandopop')).toBeInTheDocument()
  })

  it('does not hide a legitimate zero follower count', () => {
    render(<MemoryRouter><ArtistDetailHero data={detail({ followers: 0, popularity: 0 })} onBack={vi.fn()} /></MemoryRouter>)

    expect(screen.getByText('0 followers')).toBeInTheDocument()
    expect(screen.getByText('0', { selector: 'span.font-semibold' })).toBeInTheDocument()
  })

  it('deep-links the canonical artist into music metadata management', () => {
    render(<MemoryRouter><ArtistDetailHero data={detail(null)} onBack={vi.fn()} /></MemoryRouter>)

    expect(screen.getByRole('link', { name: '管理 Jolin Tsai 的艺人身份' })).toHaveAttribute(
      'href',
      expect.stringContaining('metadata=artist-identities'),
    )
    expect(screen.getByRole('link', { name: '管理 Jolin Tsai 的艺人身份' })).toHaveAttribute(
      'href',
      expect.stringContaining('artist=Jolin%20Tsai'),
    )
    expect(screen.getByRole('link', { name: '管理 Jolin Tsai 的艺人身份' })).toHaveAttribute(
      'href', expect.stringContaining('#music-metadata-management'),
    )
  })

  it('places the album management deep link in the title row with return context', () => {
    const album = {
      album_name: 'GUTS',
      artist_name: 'Olivia Rodrigo',
      cover_url: null,
      meta: null,
    } as AlbumDetailResponse
    render(<MemoryRouter><AlbumDetailHero data={album} onBack={vi.fn()} /></MemoryRouter>)

    const link = screen.getByRole('link', { name: '管理 GUTS 的专辑版本' })
    expect(link).toHaveAttribute('href', expect.stringContaining('metadata=album-projects'))
    expect(link).toHaveAttribute('href', expect.stringContaining('album_name=GUTS'))
    expect(link).toHaveAttribute('href', expect.stringContaining('#music-metadata-management'))
  })
})
