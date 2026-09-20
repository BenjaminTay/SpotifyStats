import { useCallback, useEffect, useMemo, useState } from 'react'
import { keepPreviousData, type QueryClient, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryClient } from '@/api/query-client'
import { queryKeys } from '@/api/query-keys'
import { SnapshotUnavailableError } from '@/api/errors'
import type { BillboardContextParams } from '@/features/billboard/billboardContext'
import {
  api,
  type BillboardAllTimeResponse,
  type BillboardDataResponse,
  type BillboardRecordsResponse,
  type BillboardWeeklyResponse,
  type BillboardYearEndResponse,
  type WeeklyAlbumEntry,
  type WeeklyArtistEntry,
  type WeeklyTrackEntry,
} from '@/lib/api'

let cachedWeekIndex = 0
let cachedWeeklyIndex = 0
const YEAR_END_REQUEST_TIMEOUT_MS = 300_000

export function loadBillboardData(
  params: BillboardContextParams,
  force = false,
): Promise<BillboardDataResponse> {
  return force
    ? queryClient.fetchQuery({
        queryKey: queryKeys.billboard.data(params),
        queryFn: () => api.get<BillboardDataResponse>('/billboard/data', params),
      })
    : queryClient.ensureQueryData({
        queryKey: queryKeys.billboard.data(params),
        queryFn: () => api.get<BillboardDataResponse>('/billboard/data', params),
      })
}

export function preloadBillboardData(params: BillboardContextParams): void {
  void queryClient.prefetchQuery({
    queryKey: queryKeys.billboard.data(params),
    queryFn: () => api.get<BillboardDataResponse>('/billboard/data', params),
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
  if (error instanceof SnapshotUnavailableError) return '榜单数据正在准备，请稍后重新加载。'
  return error instanceof Error ? error.message : error ? String(error) : null
}

function useInitialWeek(initialWeek: string | null | undefined, allWeeks: string[], setWeekIndex: (idx: number) => void) {
  useEffect(() => {
    if (allWeeks.length === 0) return
    if (!initialWeek) {
      setWeekIndex(0)
      return
    }
    const idx = allWeeks.indexOf(initialWeek)
    if (idx >= 0) setWeekIndex(idx)
  }, [initialWeek, allWeeks, setWeekIndex])
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

export function useBillboard(
  params: BillboardContextParams,
  initialWeek?: string | null,
  enabled = true,
): UseBillboardResult {
  const queryClientForHook = useQueryClient()
  const [weekIndex, setWeekIndexState] = useState(cachedWeekIndex)
  const query = useQuery({
    queryKey: queryKeys.billboard.data(params),
    queryFn: () => api.get<BillboardDataResponse>('/billboard/data', params),
    enabled,
  })

  const setWeekIndex = useCallback((idx: number) => {
    cachedWeekIndex = idx
    setWeekIndexState(idx)
  }, [])

  const allWeeks = useMemo(() => query.data?.meta.all_weeks_desc ?? [], [query.data])
  const totalWeeks = allWeeks.length
  const currentIndex = totalWeeks > 0 ? Math.min(weekIndex, totalWeeks - 1) : 0
  const selectedWeek = allWeeks[currentIndex] ?? ''

  useInitialWeek(initialWeek, allWeeks, setWeekIndex)

  const currentWeekData = useMemo(
    () => selectCurrentWeekData(query.data, selectedWeek),
    [query.data, selectedWeek],
  )

  const goNext = useCallback(() => {
    setWeekIndex(Math.max(0, currentIndex - 1))
  }, [currentIndex, setWeekIndex])

  const goPrev = useCallback(() => {
    setWeekIndex(Math.min(totalWeeks - 1, currentIndex + 1))
  }, [currentIndex, setWeekIndex, totalWeeks])

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
    currentIndex,
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

export function useBillboardWeekly(initialWeek?: string | null, mergeLevel = 2, includeCompilations = false, enabled = true) {
  const [weekIndex, setWeekIndexState] = useState(cachedWeeklyIndex)
  const params = { merge_level: mergeLevel, include_compilations: includeCompilations }
  const query = useQuery({
    queryKey: queryKeys.billboard.weekly(params),
    queryFn: () => api.get<BillboardWeeklyResponse>('/billboard/weekly', params),
    enabled,
  })

  const setWeekIndex = useCallback((idx: number) => {
    cachedWeeklyIndex = idx
    setWeekIndexState(idx)
  }, [])

  const allWeeks = useMemo(() => query.data?.meta.all_weeks_desc ?? [], [query.data])
  const totalWeeks = allWeeks.length
  const currentIndex = totalWeeks > 0 ? Math.min(weekIndex, totalWeeks - 1) : 0
  const selectedWeek = allWeeks[currentIndex] ?? ''

  useInitialWeek(initialWeek, allWeeks, setWeekIndex)

  const currentWeekData = useMemo(
    () => selectCurrentWeekData(query.data, selectedWeek),
    [query.data, selectedWeek],
  )

  const goNext = useCallback(() => {
    setWeekIndex(Math.max(0, currentIndex - 1))
  }, [currentIndex, setWeekIndex])

  const goPrev = useCallback(() => {
    setWeekIndex(Math.min(totalWeeks - 1, currentIndex + 1))
  }, [currentIndex, setWeekIndex, totalWeeks])

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
    currentIndex,
    totalWeeks,
    goNext,
    goPrev,
    goToWeek,
  }
}

export function preloadRecordsData(params: BillboardContextParams): void {
  void queryClient.prefetchQuery({
    queryKey: queryKeys.billboard.records(params),
    queryFn: () => api.get<BillboardRecordsResponse>('/billboard/records', params),
  })
}

export function useBillboardRecords(params: BillboardContextParams, enabled = true) {
  const query = useQuery({
    queryKey: queryKeys.billboard.records(params),
    queryFn: () => api.get<BillboardRecordsResponse>('/billboard/records', params),
    enabled,
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

export function useBillboardAllTime(
  mergeLevel = 2,
  includeCompilations = false,
  contextParams: Record<string, string | number | boolean> = {},
  enabled = true,
) {
  const params = { ...contextParams, merge_level: mergeLevel, include_compilations: includeCompilations }
  const query = useQuery({
    queryKey: queryKeys.billboard.allTime(params),
    queryFn: () => api.get<BillboardAllTimeResponse>('/billboard/all-time', params),
    enabled,
  })

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: errorMessage(query.error),
    refetch: () => void query.refetch(),
  }
}

function billboardYearEndParams(
  year: number | null,
  mergeLevel: number,
  includeCompilations: boolean,
): Record<string, string | number | boolean> {
  const params: Record<string, string | number | boolean> = {
    merge_level: mergeLevel,
    include_compilations: includeCompilations,
  }
  if (year) params.year = year
  return params
}

function cacheResolvedBillboardYearEndYear(
  queryClientForHook: QueryClient,
  data: BillboardYearEndResponse | undefined,
  mergeLevel: number,
  includeCompilations: boolean,
): void {
  const resolvedYear = data?.meta.year
  if (!resolvedYear) return

  const params = billboardYearEndParams(resolvedYear, mergeLevel, includeCompilations)
  const queryKey = queryKeys.billboard.yearEnd(params)
  if (!queryClientForHook.getQueryData(queryKey)) {
    queryClientForHook.setQueryData(queryKey, data)
  }
}

export function useBillboardYearEnd(
  year: number | null,
  mergeLevel = 2,
  includeCompilations = false,
  enabled = true,
) {
  const queryClientForHook = useQueryClient()
  const params = billboardYearEndParams(year, mergeLevel, includeCompilations)
  const query = useQuery({
    queryKey: queryKeys.billboard.yearEnd(params),
    queryFn: () => api.get<BillboardYearEndResponse>('/billboard/year-end', params, YEAR_END_REQUEST_TIMEOUT_MS),
    placeholderData: keepPreviousData,
    enabled,
  })
  useEffect(() => {
    cacheResolvedBillboardYearEndYear(queryClientForHook, query.data, mergeLevel, includeCompilations)
  }, [includeCompilations, mergeLevel, query.data, queryClientForHook])

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    fetching: query.isFetching,
    placeholder: query.isPlaceholderData,
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

export function useEntityLists(
  params: Record<string, string | number | boolean> = {},
  search?: string,
  enabled = true,
) {
  const requestParams = search ? { ...params, search } : params
  const query = useQuery({
    queryKey: queryKeys.billboard.entityLists(requestParams),
    queryFn: () =>
      api.get<import('@/types/billboard').EntityListsResponse>(
        '/billboard/entity-lists',
        requestParams,
      ),
    staleTime: 1000 * 60 * 30,
    enabled,
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
  params: Record<string, string | number | boolean> = {},
) {
  const enabled = body !== null
  const query = useQuery({
    queryKey: queryKeys.billboard.versus(kind, { body, filters: params }),
    queryFn: () =>
      api.postWithParams<import('@/types/billboard').VersusResponse>(
        `/billboard/versus/${kind}`,
        body,
        params,
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
  params: Record<string, string | number | boolean> = {},
) {
  const enabled = !!items && items.length >= 2
  const query = useQuery({
    queryKey: queryKeys.billboard.releaseCycleCompare({ items, filters: params }),
    queryFn: () =>
      api.postWithParams<import('@/types/billboard').ReleaseCycleCompareResponse>(
        '/billboard/release-cycle/compare',
        { items, weeks_before: 12, weeks_after: 24 },
        params,
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

/** An old tab/week/filter must never masquerade as the selected context. */
function useBillboardProjection<T>(
  path: string,
  params: Record<string, string | number | boolean>,
  enabled = true,
  retainEntityRows = false,
  retainPreviousContext = false,
) {
  const query = useQuery<T>({
    queryKey: queryKeys.billboard.projection(path, params),
    // Entity projections contain every row. Local view changes can keep those
    // identical facts while the new query resolves, without unmounting inputs.
    // A different entity or Billboard filter must show its own loading state.
    placeholderData: retainPreviousContext ? keepPreviousData : retainEntityRows ? (previous, previousQuery) => {
      const old = previousQuery?.queryKey[3] as Record<string, unknown> | undefined
      const local = new Set(['page', 'page_size', 'sort', 'direction', 'peak_filter', 'search'])
      const keys = new Set([...Object.keys(params), ...Object.keys(old ?? {})])
      return old && [...keys].every(key => local.has(key) || old[key] === params[key]) ? previous : undefined
    } : undefined,
    queryFn: ({ signal }) => api.get<T>(`/billboard/${path}`, params, undefined, signal),
    enabled,
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  })
  return {
    data: query.data ?? null,
    loading: query.isLoading,
    fetching: query.isFetching,
    switching: query.isPlaceholderData,
    error: errorMessage(query.error),
    refetch: () => void query.refetch(),
  }
}

export function useRecordsProjection(params: BillboardContextParams, enabled = true) {
  return useBillboardProjection<import('@/types/billboard').BillboardRecordsProjection>('records', { ...params, projection: 'page' }, enabled)
}
export function useWeeklyProjection(params: BillboardContextParams, week: string | null, entity: string, enabled = true) {
  const client = useQueryClient()
  const result = useBillboardProjection<import('@/types/billboard').BillboardWeeklyProjection>(
    'weekly',
    { ...params, projection: 'page', ...(week ? { week } : {}), entity },
    enabled,
    false,
    true,
  )
  useEffect(() => {
    const projection = result.data
    if (!projection || result.switching) return
    const prefetch = (nextWeek: string, nextEntity: string) => {
      const nextParams = { ...params, projection: 'page', week: nextWeek, entity: nextEntity }
      void client.prefetchQuery({
        queryKey: queryKeys.billboard.projection('weekly', nextParams),
        queryFn: ({ signal }) => api.get('/billboard/weekly', nextParams, undefined, signal),
        staleTime: 5 * 60 * 1000,
      })
    }
    for (const sibling of ['tracks', 'albums', 'artists']) {
      if (sibling !== projection.entity) prefetch(projection.selected_week, sibling)
    }
    const weeks = projection.meta?.all_weeks_desc ?? []
    const index = weeks.indexOf(projection.selected_week)
    for (const neighbor of [weeks[index - 1], weeks[index + 1]]) {
      if (neighbor) prefetch(neighbor, projection.entity)
    }
  }, [client, params, result.data, result.switching])
  return result
}
export function useAllTimeProjection(params: BillboardContextParams, view: Record<string, string | number | boolean>, enabled = true) {
  const client = useQueryClient()
  const result = useBillboardProjection<import('@/types/billboard').BillboardAllTimeProjection>('all-time', { ...params, ...view, projection: 'entity' }, enabled, true)
  useEffect(() => {
    if (!result.data) return
    for (const sibling of ['tracks', 'albums', 'artists']) {
      if (sibling === result.data.entity) continue
      const nextParams = { ...params, ...view, entity: sibling, projection: 'entity' }
      void client.prefetchQuery({
        queryKey: queryKeys.billboard.projection('all-time', nextParams),
        queryFn: ({ signal }) => api.get('/billboard/all-time', nextParams, undefined, signal),
        staleTime: 5 * 60 * 1000,
      })
    }
  }, [client, params, result.data, view])
  return result
}
export function useNumberOnesProjection(params: BillboardContextParams, enabled = true) {
  return useBillboardProjection<import('@/types/billboard').BillboardNumberOnesProjection>('all-time', { ...params, projection: 'number-ones' }, enabled)
}
