import type { ApiQueryParam } from '@/api/client'
import { api } from '@/lib/api'
import type {
  MusicSearchCandidateResponse,
  MusicSearchContextResponse,
  MusicSearchKind,
} from '@/types/music-search'

export type MusicSearchEligibility = 'current' | 'any_local'

export interface MusicSearchVariantParams {
  dynamic_threshold: boolean
  merge_level: number
}

export interface MusicSearchCandidateParams {
  q: string
  kind?: MusicSearchKind
  page: number
  pageSize: number
  eligibility: MusicSearchEligibility
  variantParams: MusicSearchVariantParams
}

export const musicSearchApiV2 = {
  searchCandidates: (params: MusicSearchCandidateParams, signal?: AbortSignal) => {
    const query: Record<string, ApiQueryParam> = {
      ...params.variantParams,
      q: params.q,
      response_mode: 'candidates',
      eligibility: params.eligibility,
      page: params.page,
      page_size: params.pageSize,
    }
    if (params.kind) query.kind = params.kind
    return api.get<MusicSearchCandidateResponse>('/music/search', query, undefined, signal)
  },
  getContext: (
    entityKeys: readonly string[],
    variantParams: MusicSearchVariantParams,
    signal?: AbortSignal,
  ) => api.get<MusicSearchContextResponse>(
    '/music/search/context',
    { ...variantParams, entity_key: entityKeys },
    undefined,
    signal,
  ),
}
