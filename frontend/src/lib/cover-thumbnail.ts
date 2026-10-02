export type CoverArtworkSize = 160 | 320 | 640 | 'original'

/** Select a persisted local variant; provider and unknown URLs remain unchanged. */
export function coverArtworkUrl(url: string, size: CoverArtworkSize = 160): string {
  const extension = size === 'original' ? '.jpg' : size === 160 ? '.thumb.webp' : `.${size}.webp`
  return url.replace(
    /^(\/covers\/(?:albums|artists)\/\d+)(?:\.jpg|\.(?:thumb|320|640)\.webp)([?#].*)?$/,
    (_match, base: string, suffix: string | undefined) => `${base}${extension}${suffix ?? ''}`,
  )
}

/** Choose sufficient pixels before the first request on a dense display. */
export function coverDisplayUrl(
  url: string,
  size: CoverArtworkSize = 160,
  dpr = typeof window === 'undefined' ? 1 : window.devicePixelRatio,
): string {
  const displaySize = size === 160 && dpr > 2
    ? 320
    : size === 320 && dpr > 1.5
      ? 640
      : size
  return coverArtworkUrl(url, displaySize)
}

/** Compatibility entry point for existing small list artwork. */
export function coverThumbnailUrl(url: string): string {
  return coverDisplayUrl(url, 160)
}
