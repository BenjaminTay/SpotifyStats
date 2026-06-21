const SPOTIFY_IMAGE_SIZES = [640, 300, 64]

/**
 * Generate srcSet from a Spotify cover URL.
 * Spotify CDN URLs follow the pattern https://i.scdn.co/image/{hash}.
 * Returns undefined if the URL pattern doesn't match (graceful degradation).
 */
export function srcsetFromCoverUrl(
  url: string | null | undefined,
): string | undefined {
  if (!url) return undefined
  // Match Spotify CDN pattern
  if (!url.startsWith('https://i.scdn.co/image/')) return undefined
  return SPOTIFY_IMAGE_SIZES.map((w) => `${url} ${w}w`).join(', ')
}

/**
 * Sizes attribute for responsive cover images.
 */
export function coverSizes(defaultSize = '64px'): string {
  return `(max-width: 640px) 48px, (max-width: 1024px) 64px, ${defaultSize}`
}

/**
 * Sizes attribute for hero/header cover images (larger).
 */
export function heroCoverSizes(): string {
  return '(max-width: 640px) 80px, (max-width: 1024px) 120px, 300px'
}
