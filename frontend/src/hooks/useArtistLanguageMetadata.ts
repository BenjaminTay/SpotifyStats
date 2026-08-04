import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '@/api/query-keys'
import { api } from '@/lib/api'
import type {
  ArtistLanguageCoverageResponse,
  ArtistLanguagePlayFilters,
  ArtistLanguageReviewCreateRequest,
  ArtistLanguageReviewDecisionRequest,
  ArtistLanguageReviewItem,
  ArtistLanguageReviewListResponse,
  ArtistLanguageReviewMutationResponse,
  ArtistLanguageReviewStatus,
  ArtistLanguageSourceInput,
  ArtistLanguageSourceItem,
} from '@/types/artist-language-metadata'

function playParams(
  filters: ArtistLanguagePlayFilters,
): Record<string, string | number | boolean> {
  const params: Record<string, string | number | boolean> = {
    min_ms: filters.min_ms,
    music_only: filters.music_only,
    merge_enabled: filters.merge_enabled,
    dynamic_threshold: filters.dynamic_threshold,
  }
  if (filters.max_merge_gap_minutes != null) {
    params.max_merge_gap_minutes = filters.max_merge_gap_minutes
  }
  return params
}

function withPlayParams(path: string, filters: ArtistLanguagePlayFilters): string {
  const params = new URLSearchParams()
  Object.entries(playParams(filters)).forEach(([key, value]) => {
    params.set(key, String(value))
  })
  return `${path}?${params.toString()}`
}

function invalidateArtistLanguageConsumers(
  queryClient: ReturnType<typeof useQueryClient>,
) {
  void queryClient.invalidateQueries({
    queryKey: queryKeys.metadata.artistLanguages.all,
  })
  void queryClient.invalidateQueries({ queryKey: queryKeys.yearlyReview.all })
  void queryClient.invalidateQueries({ queryKey: queryKeys.analysis.all })
}

export function useArtistLanguageCoverage(filters: ArtistLanguagePlayFilters) {
  const params = playParams(filters)
  return useQuery({
    queryKey: queryKeys.metadata.artistLanguages.coverage(params),
    queryFn: () =>
      api.get<ArtistLanguageCoverageResponse>(
        '/metadata/artist-languages/coverage',
        params,
      ),
  })
}

export function useArtistLanguageReviews(
  status: ArtistLanguageReviewStatus = 'open',
  limit = 50,
) {
  return useQuery({
    queryKey: queryKeys.metadata.artistLanguages.reviews(status, limit),
    queryFn: () =>
      api.get<ArtistLanguageReviewListResponse>(
        '/metadata/artist-languages/reviews',
        { status, limit },
      ),
  })
}

export function useStartArtistLanguageReview(filters: ArtistLanguagePlayFilters) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: ArtistLanguageReviewCreateRequest) =>
      api.post<ArtistLanguageReviewItem>(
        withPlayParams('/metadata/artist-languages/reviews', filters),
        request,
      ),
    onSuccess: () => invalidateArtistLanguageConsumers(queryClient),
  })
}

export function useSaveArtistLanguageSource(reviewId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (source: ArtistLanguageSourceInput) =>
      api.put<ArtistLanguageSourceItem>(
        `/metadata/artist-languages/reviews/${reviewId}/source`,
        source,
      ),
    onSuccess: () => invalidateArtistLanguageConsumers(queryClient),
  })
}

export function useDecideArtistLanguageReview(reviewId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (decision: ArtistLanguageReviewDecisionRequest) =>
      api.patch<ArtistLanguageReviewMutationResponse>(
        `/metadata/artist-languages/reviews/${reviewId}`,
        decision,
      ),
    onSuccess: () => invalidateArtistLanguageConsumers(queryClient),
  })
}
