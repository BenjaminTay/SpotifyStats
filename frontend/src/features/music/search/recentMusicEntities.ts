import { useCallback, useEffect, useState } from 'react'

import type { MusicSearchCandidate, MusicSearchKind } from '@/types/music-search'

const STORAGE_KEY = 'spotify_stats_recent_music_entities_v1'
const MAX_RECENT_ENTITIES = 6

export interface RecentMusicEntity {
  entity_key: string
  label: string
  kind: MusicSearchKind
  href: string
  viewed_at: string
}

function isRecentMusicEntity(value: unknown): value is RecentMusicEntity {
  if (!value || typeof value !== 'object') return false
  const item = value as Record<string, unknown>
  return typeof item.entity_key === 'string'
    && /^(track|album|album_project|artist):[1-9]\d*$/.test(item.entity_key)
    && typeof item.label === 'string'
    && item.label.trim().length > 0
    && (item.kind === 'track' || item.kind === 'album' || item.kind === 'artist')
    && typeof item.href === 'string'
    && item.href.startsWith('/music/')
    && typeof item.viewed_at === 'string'
}

function readRecentMusicEntities(): RecentMusicEntity[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]') as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.filter(isRecentMusicEntity).slice(0, MAX_RECENT_ENTITIES)
  } catch {
    return []
  }
}

function writeRecentMusicEntities(items: RecentMusicEntity[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_RECENT_ENTITIES)))
  } catch {
    // Private convenience state must never block navigation.
  }
}

export function useRecentMusicEntities(enabled: boolean) {
  const [items, setItems] = useState<RecentMusicEntity[]>([])

  useEffect(() => {
    let active = true
    queueMicrotask(() => {
      if (active) setItems(enabled ? readRecentMusicEntities() : [])
    })
    return () => {
      active = false
    }
  }, [enabled])

  const record = useCallback((candidate: MusicSearchCandidate) => {
    if (!enabled) return
    const next: RecentMusicEntity = {
      entity_key: candidate.entity_key,
      label: candidate.label,
      kind: candidate.kind,
      href: candidate.href,
      viewed_at: new Date().toISOString(),
    }
    setItems((current) => {
      const updated = [next, ...current.filter((item) => item.entity_key !== next.entity_key)]
        .slice(0, MAX_RECENT_ENTITIES)
      writeRecentMusicEntities(updated)
      return updated
    })
  }, [enabled])

  const clear = useCallback(() => {
    if (!enabled) return
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // Ignore unavailable storage.
    }
    setItems([])
  }, [enabled])

  return { items, record, clear }
}
