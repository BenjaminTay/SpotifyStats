import { fireEvent, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AccountAvatar } from '@/features/community/AccountAvatar'
import { MobileEntityArtwork } from '@/components/mobile/MobileEntityRow'
import { HomeEntityArtwork } from '@/features/home/HomePrimitives'
import { MobileMusicDetailHero } from '@/features/mobile/music/MobileMusicDetail'
import { EntityCover } from '@/features/yearly-review/YearlyReviewPrimitives'
import type { HomeEntityRef } from '@/types/home'

vi.mock('@/lib/chinese', () => ({
  displayName: (value: string) => value,
  useChineseTextVersion: () => 'original',
}))

const entity: HomeEntityRef = {
  entity_type: 'album', entity_id: 42, name: '封面', artist_name: null,
  cover_url: '/covers/albums/42.jpg?v=1', deep_link: '/music/albums/cover',
}

beforeEach(() => { vi.stubGlobal('devicePixelRatio', 1) })
afterEach(() => { vi.unstubAllGlobals() })

describe('artwork presentations', () => {
  it('keeps the home hero priority while selecting a smaller source for list use', () => {
    const { container, rerender } = render(<HomeEntityArtwork entity={entity} artworkSize="large" eager />)
    expect(container.querySelector('img')).toHaveAttribute('src', '/covers/albums/42.640.webp?v=1')
    expect(container.querySelector('img')).toHaveAttribute('loading', 'eager')
    expect(container.querySelector('img')).toHaveAttribute('fetchpriority', 'high')
    rerender(<HomeEntityArtwork entity={entity} artworkSize="small" />)
    expect(container.querySelector('img')).toHaveAttribute('src', '/covers/albums/42.thumb.webp?v=1')
    expect(container.querySelector('img')).toHaveAttribute('loading', 'lazy')
    expect(container.querySelector('img')).toHaveAttribute('decoding', 'async')
  })

  it('clears a hidden failed home image when the entity changes', () => {
    const { container, rerender } = render(<HomeEntityArtwork entity={entity} artworkSize="small" />)
    fireEvent.error(container.querySelector('img')!)
    expect(container.querySelector('img')).toHaveAttribute('hidden')
    rerender(<HomeEntityArtwork entity={{ ...entity, cover_url: '/covers/albums/43.jpg' }} artworkSize="small" />)
    expect(container.querySelector('img')).not.toHaveAttribute('hidden')
    expect(container.querySelector('img')).toHaveAttribute('src', '/covers/albums/43.thumb.webp')
  })

  it('uses the current yearly chapter size without changing external artwork', () => {
    const { container, rerender } = render(<EntityCover entity={entity} size="small" />)
    expect(container.querySelector('img')).toHaveAttribute('src', '/covers/albums/42.thumb.webp?v=1')
    rerender(<EntityCover entity={entity} size="medium" />)
    expect(container.querySelector('img')).toHaveAttribute('src', '/covers/albums/42.320.webp?v=1')
    rerender(<EntityCover entity={{ ...entity, cover_url: 'https://image.example/album.jpg' }} size="medium" />)
    expect(container.querySelector('img')).toHaveAttribute('src', 'https://image.example/album.jpg')
  })

  it('does not leave a reused phone list row in the failed-image state', () => {
    const { container, rerender } = render(<MobileEntityArtwork type="album" coverUrl="/covers/albums/42.jpg" />)
    fireEvent.error(container.querySelector('img')!)
    expect(container.querySelector('img')).toBeNull()
    rerender(<MobileEntityArtwork type="artist" coverUrl="/covers/artists/7.jpg" />)
    expect(container.querySelector('img')).toHaveAttribute('src', '/covers/artists/7.thumb.webp')
    expect(container.querySelector('img')).toHaveAttribute('loading', 'lazy')
  })

  it('chooses sufficient pixels for dense phone artwork on the initial render', () => {
    vi.stubGlobal('devicePixelRatio', 3)
    const { container, rerender } = render(<HomeEntityArtwork entity={entity} artworkSize="small" />)
    expect(container.querySelector('img')).toHaveAttribute('src', '/covers/albums/42.320.webp?v=1')
    rerender(<MobileMusicDetailHero kind="artist" title="艺人" coverUrl="/covers/artists/7.jpg" facts={[]} />)
    expect(container.querySelector('img')).toHaveAttribute('src', '/covers/artists/7.640.webp')
  })

  it('recovers an account avatar when navigating away from a failed account', () => {
    const { container, rerender } = render(<AccountAvatar handle="@chartdata" />)
    expect(container.querySelector('img')).toHaveAttribute('src', '/avatars/chartdata.jpg')
    fireEvent.error(container.querySelector('img')!)
    expect(container.querySelector('img')).toBeNull()
    rerender(<AccountAvatar handle="@billboardcharts" />)
    expect(container.querySelector('img')).toHaveAttribute('src', '/avatars/billboardcharts.jpg')
    expect(container.querySelector('img')).toHaveAttribute('loading', 'lazy')
    expect(container.querySelector('img')).toHaveAttribute('decoding', 'async')
  })

  it('loads a new phone detail entity after the previous image failed', () => {
    const { container, rerender } = render(<MobileMusicDetailHero kind="album" title="首张" coverUrl={entity.cover_url} facts={[]} />)
    expect(container.querySelector('img')).toHaveAttribute('src', '/covers/albums/42.640.webp?v=1')
    fireEvent.error(container.querySelector('img')!)
    expect(container.querySelector('img')).toBeNull()
    rerender(<MobileMusicDetailHero kind="track" title="另一首" coverUrl="/covers/albums/43.jpg" facts={[]} />)
    expect(container.querySelector('img')).toHaveAttribute('src', '/covers/albums/43.320.webp')
    expect(container.querySelector('img')).toHaveAttribute('alt', '另一首')
  })
})
