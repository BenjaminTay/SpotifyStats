import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { queryKeys } from '@/api/query-keys'
import { buildYearlyReviewParams, yearlyReviewFilterKey } from '@/features/yearly-review/yearlyReviewData'
import { api } from '@/lib/api'
import type { AnalysisFilters } from '@/types/analysis'
import type {
  YearlyReviewAvailableYearsResponse,
  YearlyReviewRecordsPage,
  YearlyReviewResponse,
} from '@/types/yearly-review-v2'

const YEARLY_REVIEW_COLD_TIMEOUT = 120_000

export function useYearlyReviewV2(
  year: number,
  filters: AnalysisFilters,
  enabled: boolean,
) {
  const params = buildYearlyReviewParams(filters)
  const filterKey = yearlyReviewFilterKey(params)
  const query = useQuery({
    queryKey: queryKeys.yearlyReview.v2Report(year, filterKey),
    queryFn: () => api.get<YearlyReviewResponse>(`/yearly-review/${year}`, params, YEARLY_REVIEW_COLD_TIMEOUT),
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

export function useYearlyReviewV2Records(
  year: number,
  filters: AnalysisFilters,
  page: number,
  pageSize: number,
  enabled: boolean,
) {
  const params = { ...buildYearlyReviewParams(filters), page, page_size: pageSize }
  const filterKey = yearlyReviewFilterKey(buildYearlyReviewParams(filters))
  return useQuery({
    queryKey: queryKeys.yearlyReview.v2Records(year, filterKey, page, pageSize),
    queryFn: () => api.get<YearlyReviewRecordsPage>(`/yearly-review/${year}/records`, params, YEARLY_REVIEW_COLD_TIMEOUT),
    enabled: enabled && year > 0,
    placeholderData: keepPreviousData,
  })
}
