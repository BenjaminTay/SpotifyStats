export function formatArtistFollowers(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

export function formatAlbumKind(t: string): string {
  switch (t) {
    case 'album':
      return 'Album'
    case 'single':
      return 'Single'
    case 'compilation':
      return 'Compilation'
    default:
      return t
  }
}
