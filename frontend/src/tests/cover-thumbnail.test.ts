import { describe, expect, it } from 'vitest'

import { coverThumbnailUrl } from '@/lib/cover-thumbnail'

describe('coverThumbnailUrl', () => {
  it('maps local album and artist files while preserving query revisions', () => {
    expect(coverThumbnailUrl('/covers/albums/42.jpg')).toBe('/covers/albums/42.thumb.webp')
    expect(coverThumbnailUrl('/covers/artists/7.jpg?v=3')).toBe('/covers/artists/7.thumb.webp?v=3')
  })

  it('leaves external and unknown cover URLs alone', () => {
    expect(coverThumbnailUrl('https://image.example/cover.jpg')).toBe('https://image.example/cover.jpg')
    expect(coverThumbnailUrl('/covers/track/42.jpg')).toBe('/covers/track/42.jpg')
  })
})
