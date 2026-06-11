import { useInfiniteQuery, useQuery } from '@tanstack/react-query'

import { queryClient } from '@/api/query-client'
import { queryKeys } from '@/api/query-keys'
import { api } from '@/lib/api'
import type { CommunityFeedResponse } from '@/types/community'

const DEFAULT_LIMIT = 50

function errorMessage(error: unknown): string | null {
  return error instanceof Error ? error.message : error ? String(error) : null
}

export function useCommunityFeed(params: Record<string, string | number | boolean> = {}) {
  const query = useInfiniteQuery<CommunityFeedResponse>({
    queryKey: queryKeys.community.feed(params),
    queryFn: ({ pageParam }: { pageParam: unknown }) =>
      api.get<CommunityFeedResponse>('/community/feed', {
        ...params,
        limit: DEFAULT_LIMIT,
        offset: pageParam as number,
      }),
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

export function preloadCommunityFeed(): void {
  void queryClient.prefetchInfiniteQuery({
    queryKey: queryKeys.community.feed(),
    queryFn: ({ pageParam }: { pageParam: unknown }) =>
      api.get<CommunityFeedResponse>('/community/feed', { limit: DEFAULT_LIMIT, offset: pageParam as number }),
    initialPageParam: 0,
  })
}

export interface TrendingEntity {
  name: string
  count: number
  entity_id?: string | number | null
}

export interface TrendingData {
  artists: TrendingEntity[]
  tracks: TrendingEntity[]
  latest_no1: { track: string | null; artist: string | null; post_id: string } | null
  latest_debut: { track: string | null; artist: string | null; post_id: string } | null
}

export interface PostDetail {
  post: Record<string, unknown>
  replies: Record<string, unknown>[]
}

export function useCommunityPost(postId: string) {
  const { data, isLoading, error, refetch } = useQuery<PostDetail>({
    queryKey: queryKeys.community.post(postId),
    queryFn: () => api.get<PostDetail>(`/community/post/${postId}`),
    staleTime: 5 * 60 * 1000,
    enabled: !!postId,
  })

  return {
    detail: data,
    loading: isLoading,
    error: errorMessage(error),
    refetch,
  }
}

export function useCommunityTrending(params: Record<string, string | number | boolean> = {}) {
  const { data, isLoading, error, refetch } = useQuery<TrendingData>({
    queryKey: queryKeys.community.trending(params),
    queryFn: () => api.get<TrendingData>('/community/trending', params),
    staleTime: 5 * 60 * 1000,
  })

  return {
    trending: data,
    loading: isLoading,
    error: errorMessage(error),
    refetch,
  }
}
