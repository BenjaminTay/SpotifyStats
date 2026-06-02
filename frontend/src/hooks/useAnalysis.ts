import { useCallback, useEffect, useMemo, useState } from 'react'
import type { DependencyList } from 'react'
import { api } from '@/lib/api'
import { useSettings } from '@/hooks/useSettings'
import type {
  AnalysisFilters,
  AnalysisChartsResponse,
  AnalysisMetric,
  AnalysisOverviewResponse,
  AnalysisPeriod,
  AnalysisStatsResponse,
  ArtistDeepDiveResponse,
  ArtistListEntry,
  BehaviorResponse,
  EntityPlaysResponse,
  EntityStatsResponse,
  HeatmapResponse,
  LeaderboardEntity,
  LeaderboardResponse,
  LateNightEntry,
  PlatformHourlyResponse,
  TimelineAnnualPoint,
  TimelineMonthlyResponse,
  TimelineWeeklyResponse,
  WeekdayWeekendResponse,
  YearlyHeatmapEntry,
} from '@/types/analysis'

let overviewCacheKey = ''
let overviewCache: AnalysisOverviewResponse | null = null
let overviewRequest: Promise<AnalysisOverviewResponse> | null = null

function queryKey(filters: Pick<AnalysisFilters, 'min_ms' | 'music_only' | 'merge_enabled'>): string {
  return JSON.stringify(filters)
}

function playParams(filters: AnalysisFilters): Record<string, string | number | boolean> {
  return {
    min_ms: filters.min_ms,
    music_only: filters.music_only,
    merge_enabled: filters.merge_enabled,
  }
}

export function useAnalysisFilters() {
  const { settings, loading } = useSettings()

  const filters = useMemo<AnalysisFilters>(() => {
    return {
      min_ms: settings?.min_ms ?? 30000,
      music_only: settings?.music_only ?? true,
      merge_enabled: settings?.merge_enabled ?? true,
    }
  }, [settings])

  return { filters, loading }
}

export function loadAnalysisOverview(filters: AnalysisFilters, force = false): Promise<AnalysisOverviewResponse> {
  const key = queryKey(filters)
  if (overviewRequest && overviewCacheKey === key) return overviewRequest
  if (overviewCache && overviewCacheKey === key && !force) return Promise.resolve(overviewCache)

  overviewCacheKey = key
  overviewRequest = api.get<AnalysisOverviewResponse>('/analysis/overview', playParams(filters))
    .then((data) => {
      overviewCache = data
      return data
    })
    .finally(() => {
      overviewRequest = null
    })
  return overviewRequest
}

export function preloadAnalysisOverview(): void {
  void loadAnalysisOverview({
    min_ms: 30000,
    music_only: true,
    merge_enabled: true,
  }).catch(() => {})
}

export function useAnalysisOverview(filters: AnalysisFilters) {
  const [data, setData] = useState<AnalysisOverviewResponse | null>(overviewCache)
  const [loading, setLoading] = useState(!overviewCache)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback((force = false) => {
    setLoading(true)
    setError(null)
    loadAnalysisOverview(filters, force)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [filters])

  useEffect(() => {
    refetch()
  }, [refetch])

  return { data, loading, error, refetch: () => refetch(true) }
}

export function useApiData<T>(loader: () => Promise<T>, deps: DependencyList, enabled = true) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled) {
      setLoading(true)
      return
    }
    let active = true
    setLoading(true)
    setError(null)
    loader()
      .then((result) => {
        if (active) setData(result)
      })
      .catch((e: Error) => {
        if (active) setError(e.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [...deps, enabled])

  return { data, loading, error }
}

export const analysisApi = {
  stats: (
    filters: AnalysisFilters,
    params: { period: AnalysisPeriod; start_date?: string; end_date?: string },
  ) =>
    api.get<AnalysisStatsResponse>('/analysis/stats', { ...playParams(filters), ...params }),
  charts: (
    filters: AnalysisFilters,
    params: {
      period: AnalysisPeriod
      start_date?: string
      end_date?: string
      entity: LeaderboardEntity
      metric: AnalysisMetric
      limit?: number
      offset?: number
    },
  ) =>
    api.get<AnalysisChartsResponse>('/analysis/charts', { ...playParams(filters), ...params }),
  trackStats: (
    filters: AnalysisFilters,
    trackId: number | string,
    params: { period: AnalysisPeriod; start_date?: string; end_date?: string },
  ) =>
    api.get<EntityStatsResponse>(`/music/tracks/${trackId}/stats`, { ...playParams(filters), ...params }),
  albumStats: (
    filters: AnalysisFilters,
    albumName: string,
    artist: string | undefined,
    params: { period: AnalysisPeriod; start_date?: string; end_date?: string },
  ) =>
    api.get<EntityStatsResponse>(`/music/albums/${encodeURIComponent(albumName)}/stats`, {
      ...playParams(filters),
      ...params,
      ...(artist ? { artist } : {}),
    }),
  artistStats: (
    filters: AnalysisFilters,
    artistName: string,
    params: { period: AnalysisPeriod; start_date?: string; end_date?: string },
  ) =>
    api.get<EntityStatsResponse>(`/music/artists/${encodeURIComponent(artistName)}/stats`, {
      ...playParams(filters),
      ...params,
    }),
  annual: (filters: AnalysisFilters) =>
    api.get<TimelineAnnualPoint[]>('/timeline/annual', playParams(filters)),
  monthly: (filters: AnalysisFilters, period?: string) =>
    api.get<TimelineMonthlyResponse>('/timeline/monthly', { ...playParams(filters), ...(period ? { period } : {}) }),
  weekly: (filters: AnalysisFilters, week?: string) =>
    api.get<TimelineWeeklyResponse>('/timeline/weekly', { ...playParams(filters), ...(week ? { week } : {}) }),
  leaderboard: (filters: AnalysisFilters, entity: LeaderboardEntity) =>
    api.get<LeaderboardResponse>('/leaderboard', {
      ...playParams(filters),
      entity,
      metric: 'plays',
      time_range: 'all',
      top_n: 30,
    }),
  behavior: (filters: AnalysisFilters) =>
    api.get<BehaviorResponse>('/behavior', playParams(filters)),
  heatmap: (filters: AnalysisFilters) =>
    api.get<HeatmapResponse>('/listening-hours/heatmap', playParams(filters)),
  yearlyHeatmaps: (filters: AnalysisFilters) =>
    api.get<YearlyHeatmapEntry[]>('/listening-hours/yearly', playParams(filters)),
  lateNight: (filters: AnalysisFilters) =>
    api.get<LateNightEntry[]>('/listening-hours/late-night', playParams(filters)),
  weekdayWeekend: (filters: AnalysisFilters) =>
    api.get<WeekdayWeekendResponse>('/listening-hours/weekday-weekend', playParams(filters)),
  platformHourly: (filters: AnalysisFilters) =>
    api.get<PlatformHourlyResponse>('/listening-hours/platform-hourly', playParams(filters)),
  artistList: (filters: AnalysisFilters) =>
    api.get<ArtistListEntry[]>('/artist/list', {
      min_ms: filters.min_ms,
      music_only: filters.music_only,
    }),
  artistDeepDive: (filters: AnalysisFilters, name: string) =>
    api.get<ArtistDeepDiveResponse>(`/artist/${encodeURIComponent(name)}/deep-dive`, playParams(filters)),
  entityPlays: (
    kind: 'track' | 'album' | 'artist',
    id: string,
    filters: AnalysisFilters,
    params: { period: AnalysisPeriod; start_date?: string; end_date?: string; limit?: number; offset?: number; search?: string; date?: string },
    artistName?: string,
  ) => {
    const path =
      kind === 'track'
        ? `/music/tracks/${id}/plays`
        : kind === 'album'
          ? `/music/albums/${encodeURIComponent(id)}/plays`
          : `/music/artists/${encodeURIComponent(id)}/plays`
    const q: Record<string, string | number | boolean> = {
      ...playParams(filters),
      period: params.period,
      start_date: params.start_date ?? '',
      end_date: params.end_date ?? '',
      limit: params.limit ?? 50,
      offset: params.offset ?? 0,
    }
    if (params.search) q.search = params.search
    if (params.date) q.date = params.date
    // Remove empty strings that were defaulted
    if (!q.start_date) delete q.start_date
    if (!q.end_date) delete q.end_date
    if (kind === 'album' && artistName) {
      q.artist = artistName
    }
    return api.get<EntityPlaysResponse>(path, q)
  },
  plays: (
    filters: AnalysisFilters,
    params: { period: AnalysisPeriod; start_date?: string; end_date?: string; limit?: number; offset?: number; search?: string; date?: string },
  ) => {
    const q: Record<string, string | number | boolean> = {
      ...playParams(filters),
      period: params.period,
      start_date: params.start_date ?? '',
      end_date: params.end_date ?? '',
      limit: params.limit ?? 50,
      offset: params.offset ?? 0,
    }
    if (params.search) q.search = params.search
    if (params.date) q.date = params.date
    if (!q.start_date) delete q.start_date
    if (!q.end_date) delete q.end_date
    return api.get<EntityPlaysResponse>('/analysis/plays', q)
  },

  entityPlayDates: (
    kind: 'track' | 'album' | 'artist',
    id: string,
    filters: AnalysisFilters,
    params: { period: AnalysisPeriod; start_date?: string; end_date?: string },
    artistName?: string,
  ) => {
    const path =
      kind === 'track'
        ? `/music/tracks/${id}/play-dates`
        : kind === 'album'
          ? `/music/albums/${encodeURIComponent(id)}/play-dates`
          : `/music/artists/${encodeURIComponent(id)}/play-dates`
    const queryParams: Record<string, string | number | boolean> = {
      ...playParams(filters),
      ...params,
    }
    if (kind === 'album' && artistName) {
      queryParams.artist = artistName
    }
    return api.get<{ date: string; count: number }[]>(path, queryParams)
  },

  playDates: (
    filters: AnalysisFilters,
    params: { period: AnalysisPeriod; start_date?: string; end_date?: string },
  ) =>
    api.get<{ date: string; count: number }[]>('/analysis/play-dates', { ...playParams(filters), ...params }),
}
