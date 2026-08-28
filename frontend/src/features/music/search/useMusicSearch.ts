import { useQuery } from '@tanstack/react-query'

import { queryKeys } from '@/api/query-keys'
import type { AnalysisFilters } from '@/types/analysis'
import type { MusicSearchCandidateResponse, MusicSearchKind } from '@/types/music-search'

import {
  musicSearchApiV2,
  type MusicSearchEligibility,
  type MusicSearchVariantParams,
} from './api'
import {
  musicSearchCandidateFreshness,
  musicSearchCandidateStatus,
  musicSearchServedFilterFingerprint,
  musicSearchStatisticsStatus,
} from './musicSearchUtils'
import { analyzeMusicSearchQuery } from './searchInputController'

const SNAPSHOT_POLL_START_MS = 2_000
const SNAPSHOT_POLL_MAX_MS = 10_000

function semanticParams(filters: AnalysisFilters): Record<string, string | number | boolean> {
  return {
    min_ms: filters.min_ms,
    music_only: filters.music_only,
    merge_enabled: filters.merge_enabled,
    dynamic_threshold: filters.dynamic_threshold,
    max_merge_gap_minutes: filters.max_merge_gap_minutes ?? 5,
    merge_level: filters.merge_level,
    include_compilations: filters.include_compilations,
    bb_top_n: filters.bb_top_n ?? 30,
    bb_album_top_n: filters.bb_album_top_n ?? 20,
    bb_artist_top_n: filters.bb_artist_top_n ?? 20,
    bb_week_start_dow: filters.bb_week_start_dow ?? 4,
    bb_week_start_hour: filters.bb_week_start_hour ?? 0,
  }
}

export function musicSearchSemanticFilterKey(filters: AnalysisFilters): string {
  return JSON.stringify(semanticParams(filters))
}

function supportedVariantParams(filters: AnalysisFilters): MusicSearchVariantParams {
  return {
    dynamic_threshold: filters.dynamic_threshold,
    merge_level: filters.merge_level,
  }
}

type CandidatePollingQuery = {
  state: {
    data?: MusicSearchCandidateResponse
    dataUpdateCount: number
    status: string
  }
}

export function musicSearchSnapshotPollInterval(query: CandidatePollingQuery): number | false {
  const data = query.state.data
  const statisticsStatus = data ? musicSearchStatisticsStatus(data) : undefined
  const candidateStatus = data ? musicSearchCandidateStatus(data) : undefined
  const candidateNeedsRefresh = Boolean(
    data
    && (candidateStatus === 'ready' || candidateStatus === 'degraded')
    && musicSearchCandidateFreshness(data) === 'last_known_good',
  )
  const statisticsNeedsRefresh = statisticsStatus === 'warming' || statisticsStatus === 'stale'
  if (
    query.state.status === 'error'
    || (!candidateNeedsRefresh && !statisticsNeedsRefresh)
    || (typeof document !== 'undefined' && document.visibilityState === 'hidden')
  ) {
    return false
  }
  const completedPolls = Math.max(0, query.state.dataUpdateCount - 1)
  return Math.min(SNAPSHOT_POLL_START_MS * (2 ** completedPolls), SNAPSHOT_POLL_MAX_MS)
}

export function useMusicSearchCandidates({
  query,
  filters,
  filtersLoading = false,
  kind,
  page = 1,
  pageSize = 5,
  eligibility = 'current',
}: {
  query: string
  filters: AnalysisFilters
  filtersLoading?: boolean
  kind?: MusicSearchKind
  page?: number
  pageSize?: number
  eligibility?: MusicSearchEligibility
}) {
  const analysis = analyzeMusicSearchQuery(query)
  const filterKey = musicSearchSemanticFilterKey(filters)
  const variantParams = supportedVariantParams(filters)
  const result = useQuery({
    queryKey: queryKeys.music.searchCandidates(
      filterKey,
      analysis.normalizedQuery,
      kind,
      page,
      pageSize,
      eligibility,
    ),
    queryFn: ({ signal }) => musicSearchApiV2.searchCandidates({
      q: query.trim(),
      kind,
      page,
      pageSize,
      eligibility,
      variantParams,
    }, signal),
    enabled: analysis.eligible && !filtersLoading,
    retry: 0,
    placeholderData: (previousData, previousQuery) => (
      previousQuery?.queryKey[3] === filterKey ? previousData : undefined
    ),
    refetchInterval: musicSearchSnapshotPollInterval,
    refetchIntervalInBackground: false,
    refetchOnReconnect: false,
    refetchOnWindowFocus: false,
    gcTime: 10 * 60 * 1000,
  })

  return {
    data: result.data ?? null,
    initialLoading: analysis.eligible && (filtersLoading || result.isPending),
    updating: result.isFetching && !result.isPending,
    isPlaceholderData: result.isPlaceholderData,
    error: result.error instanceof Error ? result.error.message : null,
    refetch: () => void result.refetch(),
  }
}

export function useMusicSearchContext({
  entityKeys,
  filterFingerprint,
  filters,
  enabled = true,
}: {
  entityKeys: readonly string[]
  filterFingerprint: string | null
  filters: AnalysisFilters
  enabled?: boolean
}) {
  const stableKeys = [...new Set(entityKeys)].sort().slice(0, 30)
  const result = useQuery({
    queryKey: queryKeys.music.searchContext(filterFingerprint ?? 'unavailable', stableKeys),
    queryFn: ({ signal }) => musicSearchApiV2.getContext(
      stableKeys,
      supportedVariantParams(filters),
      signal,
    ),
    enabled: enabled && Boolean(filterFingerprint) && stableKeys.length > 0,
    retry: 0,
    refetchOnReconnect: false,
    refetchOnWindowFocus: false,
    staleTime: 30 * 60 * 1000,
  })
  const data = result.data
    && musicSearchServedFilterFingerprint(result.data) === filterFingerprint
    ? result.data
    : null
  return {
    data,
    loading: result.isPending && result.fetchStatus === 'fetching',
    updating: result.isFetching && !result.isPending,
    error: result.error instanceof Error ? result.error.message : null,
  }
}
