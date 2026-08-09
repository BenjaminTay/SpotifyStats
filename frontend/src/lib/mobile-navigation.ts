import type { Location, NavigateFunction } from 'react-router-dom'

type MobileBackDecision =
  | { type: 'history' }
  | { type: 'target'; to: string }

interface MobileBackDecisionInput {
  historyIndex?: unknown
  search?: string
  state?: unknown
  fallback: string
}

export interface MobileDetailOrigin {
  to: string
  label: string
}

export function isSafeInternalReturnTo(value: unknown): value is string {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) return false

  try {
    const url = new URL(value, 'https://spotify-stats.local')
    return url.origin === 'https://spotify-stats.local'
  } catch {
    return false
  }
}

function returnToFromState(state: unknown): string | null {
  if (!state || typeof state !== 'object') return null
  const value = (state as { returnTo?: unknown }).returnTo
  return isSafeInternalReturnTo(value) ? value : null
}

export function isMusicDetailPath(pathname: string): boolean {
  return pathname.startsWith('/music/tracks/')
    || pathname.startsWith('/music/albums/')
    || pathname.startsWith('/music/artists/')
}

export function mobileDetailOriginFromState(state: unknown): MobileDetailOrigin | null {
  if (!state || typeof state !== 'object') return null
  const origin = (state as { detailOrigin?: unknown }).detailOrigin
  if (!origin || typeof origin !== 'object') return null
  const to = (origin as { to?: unknown }).to
  const label = (origin as { label?: unknown }).label
  if (!isSafeInternalReturnTo(to) || typeof label !== 'string' || !label.trim()) return null
  if (isMusicDetailPath(new URL(to, 'https://spotify-stats.local').pathname)) return null
  return { to, label: label.trim() }
}

export function getMobileBackDecision({
  historyIndex,
  search = '',
  state,
  fallback,
}: MobileBackDecisionInput): MobileBackDecision {
  if (typeof historyIndex === 'number' && historyIndex > 0) return { type: 'history' }

  const queryReturnTo = new URLSearchParams(search).get('return_to')
  if (isSafeInternalReturnTo(queryReturnTo)) return { type: 'target', to: queryReturnTo }

  const stateReturnTo = returnToFromState(state)
  if (stateReturnTo) return { type: 'target', to: stateReturnTo }

  return {
    type: 'target',
    to: isSafeInternalReturnTo(fallback) ? fallback : '/',
  }
}

export function navigateMobileBack(
  navigate: NavigateFunction,
  location: Pick<Location, 'search' | 'state'>,
  fallback: string,
): void {
  const decision = getMobileBackDecision({
    historyIndex: window.history.state?.idx,
    search: location.search,
    state: location.state,
    fallback,
  })

  if (decision.type === 'history') {
    navigate(-1)
    return
  }

  navigate(decision.to, { replace: true })
}
