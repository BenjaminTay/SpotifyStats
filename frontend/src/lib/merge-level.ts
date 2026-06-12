const STORAGE_KEY = 'spotify_stats_merge_level'

export function getDefaultMergeLevel(): number {
  try {
    const v = parseInt(localStorage.getItem(STORAGE_KEY) ?? '', 10)
    if (v === 1 || v === 2 || v === 3) return v
  } catch { /* fall through */ }
  return 2
}

export function setDefaultMergeLevel(level: number) {
  localStorage.setItem(STORAGE_KEY, String(level))
}
