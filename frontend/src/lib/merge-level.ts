const STORAGE_KEY = 'spotify_stats_merge_level'
export type MergeLevel = 2 | 3

export function normalizeMergeLevel(value: unknown): MergeLevel {
  const level = Number(value)
  return level === 3 ? 3 : 2
}

export function getDefaultMergeLevel(): MergeLevel {
  try {
    const v = parseInt(localStorage.getItem(STORAGE_KEY) ?? '', 10)
    if (v === 2 || v === 3) return normalizeMergeLevel(v)
    if (v === 1) localStorage.setItem(STORAGE_KEY, '2')
  } catch { /* fall through */ }
  return 2
}

export function setDefaultMergeLevel(level: number) {
  localStorage.setItem(STORAGE_KEY, level === 3 ? '3' : '2')
}
