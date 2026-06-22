import { useEffect, useState } from 'react'

const STORAGE_KEY = 'spotify_stats_billboard_name'
const DEFAULT_NAME = 'Billboard'

// ── Public API ──────────────────────────────────────────────

export function getBillboardName(): string {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored?.trim() || DEFAULT_NAME
  } catch {
    return DEFAULT_NAME
  }
}

export function setBillboardName(name: string): void {
  try {
    const trimmed = name.trim()
    if (trimmed && trimmed !== DEFAULT_NAME) {
      localStorage.setItem(STORAGE_KEY, trimmed)
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
    window.dispatchEvent(new Event('billboard-name-change'))
  } catch { /* localStorage unavailable */ }
}

export function useBillboardNameVersion(): number {
  const [version, setVersion] = useState(0)

  useEffect(() => {
    const handleChange = () => setVersion((v) => v + 1)
    window.addEventListener('billboard-name-change', handleChange)
    return () => window.removeEventListener('billboard-name-change', handleChange)
  }, [])

  return version
}
