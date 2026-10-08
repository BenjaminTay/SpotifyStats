import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import { queryKeys } from '@/api/query-keys'
import type { EntityListItem } from '@/types/billboard'
import type { VersusPersonalContext, VersusPersonalStats, VersusPersonalRanks } from '@/types/versus-personal'
import type { VersusKind } from './versusData'

export function personalRequestedKey(kind: VersusKind, item: EntityListItem): string {
  return JSON.stringify(kind === 'track' ? ['track', item.track_id]
    : kind === 'album' ? ['album', item.artist_name, item.album_name] : ['artist', item.artist_name])
}

export function personalBatchBody(kind: VersusKind, queue: EntityListItem[]) {
  const sorted = [...queue].sort((a, b) => personalRequestedKey(kind, a).localeCompare(personalRequestedKey(kind, b)))
  if (kind === 'track') return { track_ids: sorted.map((item) => item.track_id) }
  if (kind === 'album') return { albums: sorted.map(({ album_name, artist_name }) => ({ album_name, artist_name })) }
  return { artist_names: sorted.map((item) => item.artist_name) }
}

function stableContext(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableContext).join(',')}]`
  if (value && typeof value === 'object') return JSON.stringify(Object.keys(value).sort().map((key) => [key, stableContext((value as Record<string, unknown>)[key])]))
  return JSON.stringify(value)
}
export function samePersonalContext(a: VersusPersonalContext, b: VersusPersonalContext): boolean {
  return a.filter_fingerprint === b.filter_fingerprint
    && a.statistics_contract_version === b.statistics_contract_version
    && a.source_revision === b.source_revision
}

export function useVersusPersonal(kind: VersusKind, queue: EntityListItem[], params: Record<string, string | number | boolean>, enabled: boolean) {
  const body = personalBatchBody(kind, queue)
  const keyParams = { body, filters: params }
  const stats = useQuery({
    queryKey: queryKeys.billboard.versusPersonal('stats', kind, keyParams),
    queryFn: ({ signal }) => apiClient.postWithParams<VersusPersonalStats>(`/billboard/versus/${kind}/personal-stats`, body, params, undefined, signal),
    enabled: enabled && queue.length >= 2,
    retry: false,
  })
  const ranks = useQuery({
    queryKey: queryKeys.billboard.versusPersonal('ranks', kind, keyParams),
    queryFn: ({ signal }) => apiClient.postWithParams<VersusPersonalRanks>(`/billboard/versus/${kind}/personal-ranks`, body, params, undefined, signal),
    enabled: enabled && queue.length >= 2,
    retry: false,
  })
  const mismatched = !!stats.data && !!ranks.data && !samePersonalContext(stats.data, ranks.data)
  const contextKey = stableContext({ kind, ...keyParams })
  const refreshed = useRef<string | null>(null)
  const refetchStats = stats.refetch
  const refetchRanks = ranks.refetch
  useEffect(() => {
    if (!enabled || !mismatched || stats.isFetching || ranks.isFetching || refreshed.current === contextKey) return
    refreshed.current = contextKey
    void refetchStats()
    void refetchRanks()
  }, [enabled, mismatched, stats.isFetching, ranks.isFetching, contextKey, refetchStats, refetchRanks])
  return { stats, ranks, mismatched, statsData: enabled ? stats.data : undefined, ranksData: !enabled || mismatched ? undefined : ranks.data }
}

export type VersusPersonalState = ReturnType<typeof useVersusPersonal>
