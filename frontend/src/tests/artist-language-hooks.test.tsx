import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { queryKeys } from '@/api/query-keys'
import {
  useArtistLanguageCoverage,
  useArtistLanguageReviews,
  useDecideArtistLanguageReview,
  useSaveArtistLanguageSource,
  useStartArtistLanguageReview,
} from '@/hooks/useArtistLanguageMetadata'
import { api } from '@/lib/api'
import type {
  ArtistLanguageReviewDecisionRequest,
  ArtistLanguageSourceInput,
} from '@/types/artist-language-metadata'

function createClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: Infinity,
      },
    },
  })
}

function wrapperFor(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}

describe('artist language metadata hooks', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('loads coverage with only the current playback filters', async () => {
    const client = createClient()
    const filters = {
      min_ms: 30_000,
      music_only: true,
      merge_enabled: true,
      dynamic_threshold: false,
      max_merge_gap_minutes: 45,
      merge_level: 3,
      include_compilations: true,
      bb_top_n: 40,
    }
    const response = {
      eligible_hours: 10,
      excluded_unattributed_hours: 0,
      classified_hours: 6,
      unknown_hours: 4,
      classified_pct: 60,
      unknown_pct: 40,
      buckets: [],
      source_hours: {},
      top_missing: [],
      caveat: 'approved only',
    }
    vi.spyOn(api, 'get').mockResolvedValue(response)

    const { result } = renderHook(() => useArtistLanguageCoverage(filters), {
      wrapper: wrapperFor(client),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const playFilters = {
      min_ms: 30_000,
      music_only: true,
      merge_enabled: true,
      dynamic_threshold: false,
      max_merge_gap_minutes: 45,
    }
    expect(api.get).toHaveBeenCalledWith('/metadata/artist-languages/coverage', playFilters)
    expect(client.getQueryData(queryKeys.metadata.artistLanguages.coverage(playFilters))).toBe(response)
  })

  it('keys and loads reviews by status and limit', async () => {
    const client = createClient()
    const response = { items: [] }
    vi.spyOn(api, 'get').mockResolvedValue(response)

    const { result } = renderHook(
      () => useArtistLanguageReviews('insufficient_evidence', 25),
      { wrapper: wrapperFor(client) },
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(api.get).toHaveBeenCalledWith('/metadata/artist-languages/reviews', {
      status: 'insufficient_evidence',
      limit: 25,
    })
    expect(
      client.getQueryData(
        queryKeys.metadata.artistLanguages.reviews('insufficient_evidence', 25),
      ),
    ).toBe(response)
  })

  it('starts a review with artist_id and the current five playback filters', async () => {
    const client = createClient()
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries')
    vi.spyOn(api, 'post').mockResolvedValue({ review_id: 12, artist_id: 7 })
    const filters = {
      min_ms: 30_000,
      music_only: true,
      merge_enabled: false,
      dynamic_threshold: true,
      max_merge_gap_minutes: 45,
    }

    const { result } = renderHook(() => useStartArtistLanguageReview(filters), {
      wrapper: wrapperFor(client),
    })

    await act(async () => {
      await result.current.mutateAsync({ artist_id: 7 })
    })

    expect(api.post).toHaveBeenCalledWith(
      '/metadata/artist-languages/reviews?min_ms=30000&music_only=true&merge_enabled=false&dynamic_threshold=true&max_merge_gap_minutes=45',
      { artist_id: 7 },
    )
    expect(invalidateSpy.mock.calls.map(([options]) => options!.queryKey)).toEqual([
      queryKeys.metadata.artistLanguages.all,
      queryKeys.home.all,
      queryKeys.yearlyReview.all,
      queryKeys.analysis.all,
    ])
  })

  it('saves the suggested source with PUT and invalidates user-facing consumers', async () => {
    const client = createClient()
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries')
    vi.spyOn(api, 'put').mockResolvedValue({ source_id: 22 })
    const source: ArtistLanguageSourceInput = {
      classification: 'single_language',
      primary_language_code: 'zh',
      language_variant: 'mandarin',
      evidence: [
        {
          claimed_language_code: 'zh',
          claimed_language_variant: 'mandarin',
          evidence_kind: 'artist_profile',
          performer_attribution: 'artist_vocal_confirmed',
          evidence_url: 'https://example.com/artist',
          evidence_title: 'Artist profile',
          evidence_summary: 'The official profile describes the repertoire language.',
        },
      ],
    }

    const { result } = renderHook(() => useSaveArtistLanguageSource(12), {
      wrapper: wrapperFor(client),
    })

    await act(async () => {
      await result.current.mutateAsync(source)
    })

    expect(api.put).toHaveBeenCalledWith('/metadata/artist-languages/reviews/12/source', source)
    expect(invalidateSpy.mock.calls.map(([options]) => options!.queryKey)).toEqual([
      queryKeys.metadata.artistLanguages.all,
      queryKeys.home.all,
      queryKeys.yearlyReview.all,
      queryKeys.analysis.all,
    ])
  })

  it('submits a review decision with PATCH and invalidates user-facing consumers', async () => {
    const client = createClient()
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries')
    vi.spyOn(api, 'patch').mockResolvedValue({
      review_id: 12,
      review_status: 'approved',
      source_id: 22,
      source_status: 'approved',
    })
    const decision: ArtistLanguageReviewDecisionRequest = {
      action: 'approve',
      resolution_note: 'Evidence checked against the official artist profile.',
    }

    const { result } = renderHook(() => useDecideArtistLanguageReview(12), {
      wrapper: wrapperFor(client),
    })

    await act(async () => {
      await result.current.mutateAsync(decision)
    })

    expect(api.patch).toHaveBeenCalledWith('/metadata/artist-languages/reviews/12', decision)
    expect(invalidateSpy.mock.calls.map(([options]) => options!.queryKey)).toEqual([
      queryKeys.metadata.artistLanguages.all,
      queryKeys.home.all,
      queryKeys.yearlyReview.all,
      queryKeys.analysis.all,
    ])
  })
})
