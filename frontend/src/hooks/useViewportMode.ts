import { useSyncExternalStore } from 'react'

export type ViewportMode = 'phone' | 'compact' | 'desktop'

export const PHONE_MAX_WIDTH = 767
export const COMPACT_MAX_WIDTH = 1023

const PHONE_QUERY = `(max-width: ${PHONE_MAX_WIDTH}px)`
const COMPACT_QUERY = `(max-width: ${COMPACT_MAX_WIDTH}px)`

export function viewportModeForWidth(width: number): ViewportMode {
  if (width <= PHONE_MAX_WIDTH) return 'phone'
  if (width <= COMPACT_MAX_WIDTH) return 'compact'
  return 'desktop'
}

function getSnapshot(): ViewportMode {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return 'desktop'
  if (window.matchMedia(PHONE_QUERY).matches) return 'phone'
  if (window.matchMedia(COMPACT_QUERY).matches) return 'compact'
  return 'desktop'
}

function subscribe(onStoreChange: () => void): () => void {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return () => undefined

  const phoneQuery = window.matchMedia(PHONE_QUERY)
  const compactQuery = window.matchMedia(COMPACT_QUERY)
  phoneQuery.addEventListener('change', onStoreChange)
  compactQuery.addEventListener('change', onStoreChange)

  return () => {
    phoneQuery.removeEventListener('change', onStoreChange)
    compactQuery.removeEventListener('change', onStoreChange)
  }
}

export function useViewportMode(): ViewportMode {
  return useSyncExternalStore(subscribe, getSnapshot, () => 'desktop')
}
