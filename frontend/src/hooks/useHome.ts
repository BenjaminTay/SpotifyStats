import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import { queryKeys } from '@/api/query-keys'
import { buildBillboardContextParams } from '@/features/billboard/billboardContext'
import type { AnalysisFilters } from '@/types/analysis'
import type { HomeOverviewResponse, HomeRediscoveryTrack } from '@/types/home'

const HOME_STALE_TIME = 5 * 60 * 1000
const HOME_PREVIEW_RETRY_MS = 3000
const HOME_PREVIEW_MAX_UPDATES = 7

function isPreviewPending(data: HomeOverviewResponse | undefined): boolean {
  if (!data || data.state === 'empty') return false
  return data.cache_state === 'warming'
    || data.billboard.state === 'unavailable'
    || data.yearly_review.state === 'not_generated'
}

export function useHomeOverview(filters: AnalysisFilters, enabled = true) {
  const params = buildBillboardContextParams(filters)
  return useQuery({
    queryKey: queryKeys.home.overview(params),
    queryFn: () => api.get<HomeOverviewResponse>('/home/overview', params),
    staleTime: HOME_STALE_TIME,
    refetchOnWindowFocus: false,
    // The app warmup runs in a background thread. A bounded retry lets an
    // already-open cold-start home page pick up cache-only previews once they
    // become ready without polling custom filter contexts indefinitely.
    refetchInterval: (query) => (
      isPreviewPending(query.state.data)
      && query.state.dataUpdateCount < HOME_PREVIEW_MAX_UPDATES
        ? HOME_PREVIEW_RETRY_MS
        : false
    ),
    enabled,
  })
}

const HOME_REDISCOVERY_LAST_KEY = 'spotify-stats.home.rediscovery.last'

function readLastRediscovery(filterFingerprint: string): string | null {
  if (typeof window === 'undefined') return null
  try {
    return window.sessionStorage.getItem(`${HOME_REDISCOVERY_LAST_KEY}.${filterFingerprint || 'default'}`)
  } catch {
    return null
  }
}

function writeLastRediscovery(filterFingerprint: string, trackId: string): void {
  if (typeof window === 'undefined') return
  try {
    window.sessionStorage.setItem(`${HOME_REDISCOVERY_LAST_KEY}.${filterFingerprint || 'default'}`, trackId)
  } catch {
    // Session storage is an optional UX enhancement; selection still works without it.
  }
}

export function chooseHomeRediscovery(
  candidates: HomeRediscoveryTrack[],
  filterFingerprint: string,
): HomeRediscoveryTrack | null {
  if (candidates.length === 0) return null
  const previousId = readLastRediscovery(filterFingerprint)
  const selectable = candidates.length > 1 && previousId
    ? candidates.filter((candidate) => String(candidate.entity.entity_id) !== previousId)
    : candidates
  const index = Math.min(selectable.length - 1, Math.floor(Math.random() * selectable.length))
  const selected = selectable[index] ?? candidates[0]
  writeLastRediscovery(filterFingerprint, String(selected.entity.entity_id))
  return selected
}

export function useHomeRediscovery(data: HomeOverviewResponse | undefined): HomeRediscoveryTrack | null {
  const candidates = useMemo(() => (
    data?.rediscovery_candidates?.length
      ? data.rediscovery_candidates
      : data?.rediscovery ? [data.rediscovery] : []
  ), [data])
  const filterFingerprint = data?.filter_fingerprint ?? ''
  const selectionKey = `${filterFingerprint}|${candidates.map((candidate) => String(candidate.entity.entity_id)).join(',')}`
  const [selection, setSelection] = useState<{ key: string; value: HomeRediscoveryTrack | null }>({ key: '', value: null })
  const selectedKey = useRef<string | null>(null)

  useEffect(() => {
    if (selectedKey.current === selectionKey) return
    selectedKey.current = selectionKey
    setSelection({ key: selectionKey, value: chooseHomeRediscovery(candidates, filterFingerprint) })
  }, [candidates, filterFingerprint, selectionKey])

  return selection.key === selectionKey ? selection.value : data?.rediscovery ?? null
}
