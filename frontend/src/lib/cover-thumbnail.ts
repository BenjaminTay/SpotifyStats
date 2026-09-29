/** Keep entity detail artwork on the original URL; lists use the small variant. */
export function coverThumbnailUrl(url: string): string {
  return url.replace(
    /^(\/covers\/(?:albums|artists)\/\d+)\.jpg(\?.*)?$/,
    (_match, base: string, query: string | undefined) => `${base}.thumb.webp${query ?? ''}`,
  )
}
