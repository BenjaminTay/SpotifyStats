import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '@/api/query-keys'
import { buildYearlyReviewParams, yearlyReviewFilterKey } from '@/features/yearly-review/yearlyReviewData'
import { api } from '@/lib/api'
import type { AnalysisFilters } from '@/types/analysis'
import type {
  YearlyReviewAvailableYearsResponse,
  YearlyReviewGenerationStatusResponse,
  YearlyReviewPrewarmRequest,
  YearlyReviewResponse,
} from '@/types/yearly-review-v2'

const YEARLY_REVIEW_COLD_TIMEOUT = 120_000
const GENERATION_POLL_INTERVAL = 1_000

function normalizedYears(years: number[]): number[] {
  return [...new Set(years.filter(year => year > 0))].sort((left, right) => left - right)
}

function generationYearsKey(years: number[]): string {
  return normalizedYears(years).join(',')
}

export function useYearlyReviewV2(
  year: number,
  filters: AnalysisFilters,
  enabled: boolean,
) {
  const params = buildYearlyReviewParams(filters)
  const filterKey = yearlyReviewFilterKey(params)
  const query = useQuery({
    queryKey: queryKeys.yearlyReview.v2Report(year, filterKey),
    queryFn: ({ signal }) => api.get<YearlyReviewResponse>(
      `/yearly-review/${year}`,
      params,
      YEARLY_REVIEW_COLD_TIMEOUT,
      signal,
    ),
    enabled: enabled && year > 0,
    placeholderData: keepPreviousData,
  })
  return { ...query, data: query.data ?? null, filterKey }
}

export function useYearlyReviewV2AvailableYears(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.yearlyReview.v2AvailableYears(),
    queryFn: () => api.get<YearlyReviewAvailableYearsResponse>('/yearly-review/available-years'),
    enabled,
  })
}

export function useYearlyReviewGenerationStatus(
  years: number[],
  filters: AnalysisFilters,
  enabled: boolean,
) {
  const params = buildYearlyReviewParams(filters)
  const filterKey = yearlyReviewFilterKey(params)
  const yearsKey = generationYearsKey(years)
  const query = useQuery({
    queryKey: queryKeys.yearlyReview.v2GenerationStatus(yearsKey, filterKey),
    queryFn: ({ signal }) => api.get<YearlyReviewGenerationStatusResponse>(
      '/yearly-review/generation-status',
      { ...params, years: yearsKey },
      undefined,
      signal,
    ),
    enabled: enabled && yearsKey.length > 0,
    refetchInterval: queryState => queryState.state.data?.tasks.some(
      task => task.state === 'queued' || task.state === 'running',
    ) ? GENERATION_POLL_INTERVAL : false,
  })
  return { ...query, tasks: query.data?.tasks ?? [], filterKey, yearsKey }
}

export function usePrewarmYearlyReviews(filters: AnalysisFilters) {
  const queryClient = useQueryClient()
  const params = buildYearlyReviewParams(filters)
  const filterKey = yearlyReviewFilterKey(params)

  return useMutation({
    mutationFn: (payload: YearlyReviewPrewarmRequest) => api.postWithParams<YearlyReviewGenerationStatusResponse>(
      '/yearly-review/prewarm',
      {
        years: normalizedYears(payload.years),
        foreground_year: payload.foreground_year,
      },
      params,
    ),
    onSuccess: (response, payload) => {
      const yearsKey = generationYearsKey(payload.years)
      queryClient.setQueryData(
        queryKeys.yearlyReview.v2GenerationStatus(yearsKey, filterKey),
        response,
      )
    },
  })
}
