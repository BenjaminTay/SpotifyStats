import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import { queryKeys } from '@/api/query-keys'
import { buildBillboardContextParams } from '@/features/billboard/billboardContext'
import type { AnalysisFilters } from '@/types/analysis'
import type { HomeOverviewResponse } from '@/types/home'

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
