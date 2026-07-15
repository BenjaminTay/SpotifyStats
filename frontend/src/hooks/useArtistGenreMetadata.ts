import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '@/api/query-keys'
import { api } from '@/lib/api'
import type {
  ArtistGenreBackfillTaskRequest,
  ArtistGenreCoverageResponse,
  ArtistGenreEvidenceUpdateRequest,
  ArtistGenreReviewItem,
  ArtistGenreReviewDecisionResponse,
  ArtistGenreReviewListResponse,
  ArtistGenreTaxonomyResponse,
} from '@/types/artist-genre-metadata'
import type { ArtistLanguagePlayFilters } from '@/types/artist-language-metadata'
import type { AiTaskCreatePayload } from '@/types/ai-tasks'

function invalidateArtistGenreConsumers(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: queryKeys.metadata.artistGenres.all })
  void queryClient.invalidateQueries({ queryKey: queryKeys.yearlyReview.all })
  void queryClient.invalidateQueries({ queryKey: queryKeys.account.all })
  void queryClient.invalidateQueries({ queryKey: queryKeys.billboard.all })
  void queryClient.invalidateQueries({ queryKey: queryKeys.analysis.all })
}

function playParams(filters: ArtistLanguagePlayFilters) {
  return {
    min_ms: filters.min_ms,
    music_only: filters.music_only,
    merge_enabled: filters.merge_enabled,
    dynamic_threshold: filters.dynamic_threshold,
    ...(filters.max_merge_gap_minutes != null
      ? { max_merge_gap_minutes: filters.max_merge_gap_minutes }
      : {}),
  }
}

export function useArtistGenreCoverage(filters: ArtistLanguagePlayFilters) {
  const params = playParams(filters)
  return useQuery({
    queryKey: queryKeys.metadata.artistGenres.coverage(params),
    queryFn: () => api.get<ArtistGenreCoverageResponse>('/metadata/artist-genres/coverage', params),
  })
}

export function useArtistGenreTaxonomy(filters: ArtistLanguagePlayFilters) {
  const params = playParams(filters)
  return useQuery({
    queryKey: queryKeys.metadata.artistGenres.taxonomy(params),
    queryFn: () => api.get<ArtistGenreTaxonomyResponse>('/metadata/artist-genres/taxonomy', params),
  })
}

export function useArtistGenreReviews(status = 'open', limit = 50) {
  return useQuery({
    queryKey: queryKeys.metadata.artistGenres.reviews(status, limit),
    queryFn: () =>
      api.get<ArtistGenreReviewListResponse>('/metadata/artist-genres/reviews', { status, limit }),
  })
}

export function useApproveArtistGenreReview() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (reviewId: number) =>
      api.post<ArtistGenreReviewDecisionResponse>(
        `/metadata/artist-genres/reviews/${reviewId}/approve`,
        { resolution_note: '已在 Settings 核对标签与证据后批准。' },
      ),
    onSuccess: () => invalidateArtistGenreConsumers(queryClient),
  })
}

export function useRejectArtistGenreReview() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (reviewId: number) =>
      api.post<ArtistGenreReviewDecisionResponse>(
        `/metadata/artist-genres/reviews/${reviewId}/reject`,
        { resolution_note: '已在 Settings 核对后拒绝该建议。' },
      ),
    onSuccess: () => invalidateArtistGenreConsumers(queryClient),
  })
}

export function useUpdateArtistGenreEvidence() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ reviewId, evidence }: { reviewId: number; evidence: ArtistGenreEvidenceUpdateRequest }) =>
      api.patch<ArtistGenreReviewItem>(
        `/metadata/artist-genres/reviews/${reviewId}/evidence`,
        evidence,
      ),
    onSuccess: () => invalidateArtistGenreConsumers(queryClient),
  })
}

export function useStartArtistGenreBackfillTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ArtistGenreBackfillTaskRequest) =>
      api.post<AiTaskCreatePayload>('/ai/tasks/metadata/artist-genres', payload),
    onSuccess: () => invalidateArtistGenreConsumers(queryClient),
  })
}
