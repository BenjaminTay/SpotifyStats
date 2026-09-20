import { useMemo } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'

import { queryKeys, normalizeCommunityParams } from '@/api/query-keys'
import { api } from '@/lib/api'
import { getDefaultMergeLevel } from '@/lib/merge-level'
import { buildBillboardContextParams } from '@/features/billboard/billboardContext'
import { useSettings } from '@/hooks/useSettings'
import type { CommunityFeedResponse, CommunitySnapshotState } from '@/types/community'

const DEFAULT_LIMIT = 50

function errorMessage(error: unknown): string | null {
  return error instanceof Error ? error.message : error ? String(error) : null
}

function getStoredBool(key: string, fallback: boolean): boolean {
  try {
    const v = localStorage.getItem(key)
    if (v === 'true') return true
    if (v === 'false') return false
  } catch { /* localStorage unavailable */ }
  return fallback
}

export function useCommunityChartParams() {
  const { settings, loading, error, refetch } = useSettings()
  const params = useMemo(() => settings ? buildBillboardContextParams({
    ...settings,
    merge_level: getDefaultMergeLevel(),
    dynamic_threshold: getStoredBool('spotify_stats_dynamic_threshold', true),
  }) : {}, [settings])
  return { params, ready: !!settings && !error, loading, error, refetch }
}

export function useCommunityFeed(input: Record<string, string | number | boolean>, enabled: boolean) {
  const params = normalizeCommunityParams(input)
  const query = useInfiniteQuery<CommunityFeedResponse>({
    queryKey: queryKeys.community.feed(params),
    queryFn: ({ pageParam, signal }) =>
      api.get<CommunityFeedResponse>('/community/feed', {
        ...params,
        limit: DEFAULT_LIMIT,
        offset: pageParam as number,
      }, undefined, signal),
    enabled,
    initialPageParam: 0,
    getNextPageParam: (lastPage) => {
      const nextOffset = lastPage.meta.offset + lastPage.meta.returned
      return nextOffset < lastPage.meta.total ? nextOffset : undefined
    },
    staleTime: 10 * 60 * 1000,
  })

  // Flatten all pages into one posts array
  const posts = query.data?.pages.flatMap(page => page.posts) ?? []
  const meta = query.data?.pages[query.data.pages.length - 1]?.meta ?? null

  return {
    posts,
    meta,
    loading: query.isLoading,
    loadingMore: query.isFetchingNextPage,
    error: errorMessage(query.error),
    hasMore: query.hasNextPage,
    loadMore: () => { if (query.hasNextPage && !query.isFetchingNextPage) query.fetchNextPage() },
    refetch: () => void query.refetch(),
  }
}

export interface TrendingEntity {
  name: string
  count: number
  entity_id?: string | number | null
}

export interface TrendingData {
  snapshot?: CommunitySnapshotState
  artists: TrendingEntity[]
  tracks: TrendingEntity[]
  latest_no1: { track: string | null; artist: string | null; post_id: string } | null
  latest_debut: { track: string | null; artist: string | null; post_id: string } | null
}

export interface PostDetail {
  snapshot?: CommunitySnapshotState
  post: Record<string, unknown>
  replies: Record<string, unknown>[]
}

export function useCommunityPost(
  postId: string,
  input: Record<string, string | number | boolean>,
  enabled: boolean,
) {
  const params = normalizeCommunityParams(input)
  const { data, isLoading, error, refetch } = useQuery<PostDetail>({
    queryKey: queryKeys.community.post(postId, params),
    queryFn: ({ signal }) => api.get<PostDetail>(`/community/post/${postId}`, params, undefined, signal),
    staleTime: 5 * 60 * 1000,
    enabled: enabled && !!postId,
  })

  return {
    detail: data,
    loading: isLoading,
    error: errorMessage(error),
    refetch,
  }
}

export function useCommunityTrending(input: Record<string, string | number | boolean>, enabled: boolean) {
  const params = normalizeCommunityParams(input)
  const { data, isLoading, error, refetch } = useQuery<TrendingData>({
    queryKey: queryKeys.community.trending(params),
    queryFn: ({ signal }) => api.get<TrendingData>('/community/trending', params, undefined, signal),
    enabled,
    staleTime: 5 * 60 * 1000,
  })

  return {
    trending: data,
    loading: isLoading,
    error: errorMessage(error),
    refetch,
  }
}
