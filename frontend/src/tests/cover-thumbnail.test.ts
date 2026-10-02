import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { coverArtworkUrl, coverDisplayUrl, coverThumbnailUrl } from '@/lib/cover-thumbnail'

beforeEach(() => { vi.stubGlobal('devicePixelRatio', 1) })
afterEach(() => { vi.unstubAllGlobals() })

describe('coverArtworkUrl', () => {
  it('selects persisted variants and preserves source revisions and fragments', () => {
    expect(coverArtworkUrl('/covers/albums/42.jpg')).toBe('/covers/albums/42.thumb.webp')
    expect(coverArtworkUrl('/covers/artists/7.jpg?v=3#cover', 320)).toBe('/covers/artists/7.320.webp?v=3#cover')
    expect(coverArtworkUrl('/covers/albums/42.jpg', 640)).toBe('/covers/albums/42.640.webp')
    expect(coverArtworkUrl('/covers/albums/42.thumb.webp', 'original')).toBe('/covers/albums/42.jpg')
  })

  it('is idempotent and can switch a list URL to a larger presentation', () => {
    expect(coverArtworkUrl('/covers/albums/42.320.webp', 320)).toBe('/covers/albums/42.320.webp')
    expect(coverArtworkUrl('/covers/albums/42.thumb.webp?v=4', 640)).toBe('/covers/albums/42.640.webp?v=4')
    expect(coverThumbnailUrl('/covers/artists/7.640.webp')).toBe('/covers/artists/7.thumb.webp')
  })

  it.each([
    'https://image.example/cover.jpg',
    'https://site.example/covers/albums/42.jpg',
    '/covers/track/42.jpg',
    '/covers/albums/unknown.jpg',
    '/covers/albums/42.960.webp',
    '/covers/albums/42.jpg/other',
    '',
  ])('preserves external and unknown URL %s', (url) => {
    expect(coverArtworkUrl(url, 320)).toBe(url)
  })
})


describe('coverDisplayUrl', () => {
  it.each([
    [1, 160, 'thumb'], [2, 160, 'thumb'], [3, 160, '320'],
    [1, 320, '320'], [1.5, 320, '320'], [2, 320, '640'], [3, 320, '640'],
    [1, 640, '640'], [2, 640, '640'], [3, 640, '640'],
  ] as const)('selects size %s at base %s before the first request', (dpr, size, suffix) => {
    expect(coverDisplayUrl('/covers/albums/42.jpg?v=2', size, dpr)).toBe(`/covers/albums/42.${suffix}.webp?v=2`)
  })

  it.each([1, 2, 3])('keeps pure address mapping stable at DPR %s', (dpr) => {
    vi.stubGlobal('devicePixelRatio', dpr)
    expect(coverArtworkUrl('/covers/albums/42.jpg', 160)).toBe('/covers/albums/42.thumb.webp')
    expect(coverArtworkUrl('/covers/albums/42.jpg', 320)).toBe('/covers/albums/42.320.webp')
    expect(coverDisplayUrl('/covers/albums/42.640.webp', 'original')).toBe('/covers/albums/42.jpg')
  })

  it('defaults to standard density without a browser window', () => {
    vi.stubGlobal('window', undefined)
    try {
      expect(coverDisplayUrl('/covers/albums/42.jpg')).toBe('/covers/albums/42.thumb.webp')
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('uses the browser pixel density for existing list callers', () => {
    vi.stubGlobal('devicePixelRatio', 3)
    expect(coverThumbnailUrl('/covers/artists/7.jpg')).toBe('/covers/artists/7.320.webp')
    expect(coverDisplayUrl('/covers/albums/42.jpg', 320)).toBe('/covers/albums/42.640.webp')
    expect(coverDisplayUrl('https://image.example/cover.jpg', 320)).toBe('https://image.example/cover.jpg')
  })
})
