import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '@/api/query-keys'
import { api } from '@/lib/api'
import type {
  ArtistGenreBackfillTaskRequest,
  ArtistGenreCoverageResponse,
  ArtistGenreReviewDecisionResponse,
  ArtistGenreReviewListResponse,
  ArtistGenreTaxonomyResponse,
} from '@/types/artist-genre-metadata'
import type { AiTaskCreatePayload } from '@/types/ai-tasks'

function invalidateArtistGenreConsumers(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: queryKeys.metadata.artistGenres.all })
  void queryClient.invalidateQueries({ queryKey: queryKeys.yearlyReview.all })
  void queryClient.invalidateQueries({ queryKey: queryKeys.account.all })
  void queryClient.invalidateQueries({ queryKey: queryKeys.billboard.all })
  void queryClient.invalidateQueries({ queryKey: queryKeys.analysis.all })
}

export function useArtistGenreCoverage() {
  return useQuery({
    queryKey: queryKeys.metadata.artistGenres.coverage(),
    queryFn: () => api.get<ArtistGenreCoverageResponse>('/metadata/artist-genres/coverage'),
  })
}

export function useArtistGenreTaxonomy() {
  return useQuery({
    queryKey: queryKeys.metadata.artistGenres.taxonomy(),
    queryFn: () => api.get<ArtistGenreTaxonomyResponse>('/metadata/artist-genres/taxonomy'),
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
      api.post<ArtistGenreReviewDecisionResponse>(`/metadata/artist-genres/reviews/${reviewId}/approve`),
    onSuccess: () => invalidateArtistGenreConsumers(queryClient),
  })
}

export function useRejectArtistGenreReview() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (reviewId: number) =>
      api.post<ArtistGenreReviewDecisionResponse>(`/metadata/artist-genres/reviews/${reviewId}/reject`),
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
