import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { queryClient } from '@/api/query-client'
import { queryKeys } from '@/api/query-keys'
import {
  api,
  type BillboardAllTimeResponse,
  type BillboardDataResponse,
  type BillboardRecordsResponse,
  type BillboardWeeklyResponse,
  type WeeklyAlbumEntry,
  type WeeklyArtistEntry,
  type WeeklyTrackEntry,
} from '@/lib/api'

let cachedWeekIndex = 0
let cachedWeeklyIndex = 0

export function loadBillboardData(force = false): Promise<BillboardDataResponse> {
  return force
    ? queryClient.fetchQuery({
        queryKey: queryKeys.billboard.data(),
        queryFn: () => api.get<BillboardDataResponse>('/billboard/data'),
      })
    : queryClient.ensureQueryData({
        queryKey: queryKeys.billboard.data(),
        queryFn: () => api.get<BillboardDataResponse>('/billboard/data'),
      })
}

export function preloadBillboardData(): void {
  void queryClient.prefetchQuery({
    queryKey: queryKeys.billboard.data(),
    queryFn: () => api.get<BillboardDataResponse>('/billboard/data'),
  })
}

interface CurrentWeekData {
  tracks: WeeklyTrackEntry[]
  albums: WeeklyAlbumEntry[]
  artists: WeeklyArtistEntry[]
}

interface UseBillboardResult {
  data: BillboardDataResponse | null
  loading: boolean
  error: string | null
  refetch: () => void
  selectedWeek: string
  currentWeekData: CurrentWeekData
  currentIndex: number
  totalWeeks: number
  goNext: () => void
  goPrev: () => void
  goToWeek: (week: string) => void
}

function errorMessage(error: unknown): string | null {
  return error instanceof Error ? error.message : error ? String(error) : null
}

function useInitialWeek(initialWeek: string | null | undefined, allWeeks: string[], setWeekIndex: (idx: number) => void) {
  const initialWeekApplied = useRef(false)

  useEffect(() => {
    if (initialWeek && !initialWeekApplied.current && allWeeks.length > 0) {
      const idx = allWeeks.indexOf(initialWeek)
      if (idx >= 0) setWeekIndex(idx)
      initialWeekApplied.current = true
    }
  }, [initialWeek, allWeeks, setWeekIndex])

  useEffect(() => {
    initialWeekApplied.current = false
  }, [initialWeek])
}

function selectCurrentWeekData(
  data: Pick<BillboardWeeklyResponse, 'weekly' | 'weekly_album' | 'weekly_artist'> | null | undefined,
  selectedWeek: string,
): CurrentWeekData {
  if (!data) return { tracks: [], albums: [], artists: [] }
  return {
    tracks: data.weekly.filter((w) => w.billboard_week === selectedWeek).sort((a, b) => a.rank - b.rank),
    albums: data.weekly_album.filter((w) => w.billboard_week === selectedWeek).sort((a, b) => a.rank - b.rank),
    artists: data.weekly_artist.filter((w) => w.billboard_week === selectedWeek).sort((a, b) => a.rank - b.rank),
  }
}

export function useBillboard(initialWeek?: string | null, mergeLevel = 2): UseBillboardResult {
  const queryClientForHook = useQueryClient()
  const [weekIndex, setWeekIndexState] = useState(cachedWeekIndex)
  const params = { merge_level: mergeLevel }
  const query = useQuery({
    queryKey: queryKeys.billboard.data(params),
    queryFn: () => api.get<BillboardDataResponse>('/billboard/data', params),
  })

  const setWeekIndex = useCallback((idx: number) => {
    cachedWeekIndex = idx
    setWeekIndexState(idx)
  }, [])

  const allWeeks = query.data?.meta.all_weeks_desc ?? []
  const totalWeeks = allWeeks.length
  const selectedWeek = allWeeks[weekIndex] ?? ''

  useEffect(() => {
    if (query.data && weekIndex >= query.data.meta.all_weeks_desc.length) setWeekIndex(0)
  }, [query.data, setWeekIndex, weekIndex])

  useInitialWeek(initialWeek, allWeeks, setWeekIndex)

  const currentWeekData = useMemo(
    () => selectCurrentWeekData(query.data, selectedWeek),
    [query.data, selectedWeek],
  )

  const goNext = useCallback(() => {
    setWeekIndex(Math.max(0, weekIndex - 1))
  }, [setWeekIndex, weekIndex])

  const goPrev = useCallback(() => {
    setWeekIndex(Math.min(totalWeeks - 1, weekIndex + 1))
  }, [setWeekIndex, totalWeeks, weekIndex])

  const goToWeek = useCallback((week: string) => {
    const idx = allWeeks.indexOf(week)
    if (idx >= 0) setWeekIndex(idx)
  }, [allWeeks, setWeekIndex])

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: errorMessage(query.error),
    refetch: () => void queryClientForHook.invalidateQueries({ queryKey: queryKeys.billboard.data() }),
    selectedWeek,
    currentWeekData,
    currentIndex: weekIndex,
    totalWeeks,
    goNext,
    goPrev,
    goToWeek,
  }
}

export function preloadWeeklyData(): void {
  void queryClient.prefetchQuery({
    queryKey: queryKeys.billboard.weekly(),
    queryFn: () => api.get<BillboardWeeklyResponse>('/billboard/weekly'),
  })
}

export function useBillboardWeekly(initialWeek?: string | null, mergeLevel = 2) {
  const [weekIndex, setWeekIndexState] = useState(cachedWeeklyIndex)
  const params = { merge_level: mergeLevel }
  const query = useQuery({
    queryKey: queryKeys.billboard.weekly(params),
    queryFn: () => api.get<BillboardWeeklyResponse>('/billboard/weekly', params),
  })

  const setWeekIndex = useCallback((idx: number) => {
    cachedWeeklyIndex = idx
    setWeekIndexState(idx)
  }, [])

  const allWeeks = query.data?.meta.all_weeks_desc ?? []
  const totalWeeks = allWeeks.length
  const selectedWeek = allWeeks[weekIndex] ?? ''

  useEffect(() => {
    if (query.data && weekIndex >= query.data.meta.all_weeks_desc.length) setWeekIndex(0)
  }, [query.data, setWeekIndex, weekIndex])

  useInitialWeek(initialWeek, allWeeks, setWeekIndex)

  const currentWeekData = useMemo(
    () => selectCurrentWeekData(query.data, selectedWeek),
    [query.data, selectedWeek],
  )

  const goNext = useCallback(() => {
    setWeekIndex(Math.max(0, weekIndex - 1))
  }, [setWeekIndex, weekIndex])

  const goPrev = useCallback(() => {
    setWeekIndex(Math.min(totalWeeks - 1, weekIndex + 1))
  }, [setWeekIndex, totalWeeks, weekIndex])

  const goToWeek = useCallback((week: string) => {
    const idx = allWeeks.indexOf(week)
    if (idx >= 0) setWeekIndex(idx)
  }, [allWeeks, setWeekIndex])

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: errorMessage(query.error),
    refetch: () => void query.refetch(),
    selectedWeek,
    currentWeekData,
    currentIndex: weekIndex,
    totalWeeks,
    goNext,
    goPrev,
    goToWeek,
  }
}

export function preloadRecordsData(): void {
  void queryClient.prefetchQuery({
    queryKey: queryKeys.billboard.records({ merge_level: 2 }),
    queryFn: () => api.get<BillboardRecordsResponse>('/billboard/records', { merge_level: 2 }),
  })
}

export function useBillboardRecords(mergeLevel = 2) {
  const params = { merge_level: mergeLevel }
  const query = useQuery({
    queryKey: queryKeys.billboard.records(params),
    queryFn: () => api.get<BillboardRecordsResponse>('/billboard/records', params),
  })

  return {
    data: query.data?.records ?? null,
    loading: query.isLoading,
    error: errorMessage(query.error),
    refetch: () => void query.refetch(),
  }
}

export function preloadAllTimeData(): void {
  void queryClient.prefetchQuery({
    queryKey: queryKeys.billboard.allTime({ merge_level: 2 }),
    queryFn: () => api.get<BillboardAllTimeResponse>('/billboard/all-time', { merge_level: 2 }),
  })
}

export function useBillboardAllTime(mergeLevel = 2) {
  const params = { merge_level: mergeLevel }
  const query = useQuery({
    queryKey: queryKeys.billboard.allTime(params),
    queryFn: () => api.get<BillboardAllTimeResponse>('/billboard/all-time', params),
  })

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: errorMessage(query.error),
    refetch: () => void query.refetch(),
  }
}

export function preloadEntityLists(): void {
  void queryClient.prefetchQuery({
    queryKey: queryKeys.billboard.entityLists(),
    queryFn: () => api.get<import('@/types/billboard').EntityListsResponse>('/billboard/entity-lists'),
  })
}

export function useEntityLists(search?: string) {
  const query = useQuery({
    queryKey: queryKeys.billboard.entityLists(search ? { search } : {}),
    queryFn: () =>
      api.get<import('@/types/billboard').EntityListsResponse>(
        '/billboard/entity-lists',
        search ? { search } : undefined,
      ),
    staleTime: 1000 * 60 * 30,
  })
  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: errorMessage(query.error),
    refetch: () => void query.refetch(),
  }
}

export function useVersus(
  kind: 'track' | 'album' | 'artist',
  body: Record<string, unknown> | null,
) {
  const enabled = body !== null
  const query = useQuery({
    queryKey: queryKeys.billboard.versus(kind, body ?? {}),
    queryFn: () =>
      api.post<import('@/types/billboard').VersusResponse>(
        `/billboard/versus/${kind}`,
        body,
      ),
    enabled,
  })
  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: errorMessage(query.error),
    refetch: () => void query.refetch(),
  }
}

export function useReleaseCycleCompare(
  items: { artist_name: string; album_name: string }[] | null,
) {
  const enabled = !!items && items.length >= 2
  const query = useQuery({
    queryKey: queryKeys.billboard.releaseCycleCompare(items ? { items } : {}),
    queryFn: () =>
      api.post<import('@/types/billboard').ReleaseCycleCompareResponse>(
        '/billboard/release-cycle/compare',
        { items, weeks_before: 12, weeks_after: 24 },
      ),
    enabled,
  })
  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: errorMessage(query.error),
    refetch: () => void query.refetch(),
  }
}
