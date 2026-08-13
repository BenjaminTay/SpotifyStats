import { useQuery } from '@tanstack/react-query'

import { queryKeys } from '@/api/query-keys'
import { api } from '@/lib/api'
import type {
  ArchiveCohorts,
  ArchiveDiscovery,
  ArchiveJourney,
  ArchiveLibraryEntityType,
  ArchiveLibraryPage,
  ArchiveLibrarySort,
  ArchiveOtherMedia,
  ArchiveOverview,
  ArchiveReturns,
} from '@/types/accountArchive'

export const ARCHIVE_FILTERS = {
  dynamic_threshold: true,
  merge_level: 2,
} as const

const QUERY_OPTIONS = {
  staleTime: 5 * 60 * 1000,
  gcTime: 30 * 60 * 1000,
  refetchOnWindowFocus: false,
} as const

export function useArchiveOverview() {
  return useQuery({
    queryKey: queryKeys.account.archiveOverview(),
    queryFn: () => api.get<ArchiveOverview>('/account/archive-overview'),
    ...QUERY_OPTIONS,
  })
}

export function useArchiveJourney(enabled = true) {
  return useQuery({
    queryKey: queryKeys.account.archiveJourney(ARCHIVE_FILTERS),
    queryFn: () => api.get<ArchiveJourney>('/account/collection-journey', ARCHIVE_FILTERS),
    enabled,
    ...QUERY_OPTIONS,
  })
}

export function useArchiveCohorts(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.account.archiveCohorts(ARCHIVE_FILTERS),
    queryFn: () => api.get<ArchiveCohorts>('/account/collection-cohorts', ARCHIVE_FILTERS),
    enabled,
    ...QUERY_OPTIONS,
  })
}

export function useArchiveReturns(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.account.archiveReturns(ARCHIVE_FILTERS),
    queryFn: () => api.get<ArchiveReturns>('/account/returns', ARCHIVE_FILTERS),
    enabled,
    ...QUERY_OPTIONS,
  })
}

export function useArchiveDiscovery(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.account.archiveDiscovery(ARCHIVE_FILTERS),
    queryFn: () => api.get<ArchiveDiscovery>('/account/discovery', ARCHIVE_FILTERS),
    enabled,
    ...QUERY_OPTIONS,
  })
}

export function useArchiveOtherMedia(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.account.archiveOtherMedia(ARCHIVE_FILTERS),
    queryFn: () => api.get<ArchiveOtherMedia>('/account/other-media', ARCHIVE_FILTERS),
    enabled,
    ...QUERY_OPTIONS,
  })
}

export interface ArchiveLibraryParams {
  entityType: ArchiveLibraryEntityType
  page: number
  limit: number
  search: string
  sort: ArchiveLibrarySort
}

export function useArchiveLibrary(params: ArchiveLibraryParams, enabled: boolean) {
  const requestParams = {
    page: params.page,
    limit: params.limit,
    search: params.search,
    sort: params.sort,
  }
  return useQuery({
    queryKey: queryKeys.account.archiveLibrary(params.entityType, requestParams),
    queryFn: () =>
      api.get<ArchiveLibraryPage>(`/account/library/${params.entityType}`, requestParams),
    enabled,
    placeholderData: (previous) => previous,
    ...QUERY_OPTIONS,
  })
}
