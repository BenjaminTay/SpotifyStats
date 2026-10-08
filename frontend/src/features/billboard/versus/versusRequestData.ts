import type { VersusKind } from './versusData'

/** Stable sets for computation; callers restore the user's display order. */
export function canonicalVersusRequest(kind: VersusKind, body: Record<string, unknown> | null) {
  const field = kind === 'track' ? 'track_ids' : kind === 'album' ? 'albums' : 'artist_names'
  const items = (body?.[field] ?? []) as unknown[]
  const identity = (value: unknown) => value && typeof value === 'object'
    ? JSON.stringify(value, Object.keys(value).sort()) : JSON.stringify(value)
  const sorted = [...items].sort((a, b) => identity(a).localeCompare(identity(b)))
  const order = items.map((item) => sorted.findIndex((candidate) => identity(candidate) === identity(item)))
  return { body: body ? { [field]: sorted } : null, order }
}
