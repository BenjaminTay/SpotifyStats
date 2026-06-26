import { useMemo } from 'react'
import type { DependencyList } from 'react'
import { useQuery } from '@tanstack/react-query'

import { queryClient } from '@/api/query-client'
import { queryKeys } from '@/api/query-keys'
import { api } from '@/lib/api'
import { useSettings } from '@/hooks/useSettings'
import { getDefaultMergeLevel } from '@/lib/merge-level'
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
  PlaybackRecordsResponse,
  TimelineAnnualPoint,
  TimelineMonthlyResponse,
  TimelineWeeklyResponse,
  WeekdayWeekendResponse,
  YearlyHeatmapEntry,
} from '@/types/analysis'

function playParams(filters: AnalysisFilters): Record<string, string | number | boolean> {
  const p: Record<string, string | number | boolean> = {
    min_ms: filters.min_ms,
    music_only: filters.music_only,
    merge_enabled: filters.merge_enabled,
    dynamic_threshold: filters.dynamic_threshold,
  }
  if (filters.max_merge_gap_minutes != null && filters.max_merge_gap_minutes !== undefined) {
    p.max_merge_gap_minutes = filters.max_merge_gap_minutes
  }
  return p
}

export function useAnalysisFilters() {
  const { settings, loading } = useSettings()

  const filters = useMemo<AnalysisFilters>(() => {
    const storedThreshold = getStoredBool('spotify_stats_dynamic_threshold', true)
    const storedGap = getStoredNumber('spotify_stats_max_merge_gap_minutes')
    return {
      min_ms: settings?.min_ms ?? 30000,
      music_only: settings?.music_only ?? true,
      merge_enabled: settings?.merge_enabled ?? true,
      dynamic_threshold: storedThreshold,
      max_merge_gap_minutes: storedGap,
      merge_level: getDefaultMergeLevel(),
      include_compilations: settings?.include_compilations ?? false,
    }
  }, [settings])

  return { filters, loading }
}

function getStoredBool(key: string, fallback: boolean): boolean {
  try {
    const v = localStorage.getItem(key)
    if (v === 'true') return true
    if (v === 'false') return false
  } catch { /* localStorage unavailable */ }
  return fallback
}

function getStoredNumber(key: string): number | undefined {
  try {
    const v = localStorage.getItem(key)
    if (v != null) {
      const n = parseInt(v, 10)
      if (!isNaN(n) && n >= 1 && n <= 240) return n
    }
  } catch { /* localStorage unavailable */ }
  return undefined
}

export function setDynamicThreshold(value: boolean) {
  try { localStorage.setItem('spotify_stats_dynamic_threshold', String(value)) } catch { /* */ }
}

export function setMaxMergeGapMinutes(value: number | undefined) {
  try {
    if (value == null) localStorage.removeItem('spotify_stats_max_merge_gap_minutes')
    else localStorage.setItem('spotify_stats_max_merge_gap_minutes', String(value))
  } catch { /* */ }
}

export function loadAnalysisOverview(filters: AnalysisFilters, force = false): Promise<AnalysisOverviewResponse> {
  const params = playParams(filters)
  const options = {
    queryKey: queryKeys.analysis.overview(params),
    queryFn: () => api.get<AnalysisOverviewResponse>('/analysis/overview', params),
  }
  return force ? queryClient.fetchQuery(options) : queryClient.ensureQueryData(options)
}

export function preloadAnalysisOverview(): void {
  const filters: Record<string, string | number | boolean> = {
    min_ms: 30000,
    music_only: true,
    merge_enabled: true,
    dynamic_threshold: true,
  }
  void queryClient.prefetchQuery({
    queryKey: queryKeys.analysis.overview(filters),
    queryFn: () => api.get<AnalysisOverviewResponse>('/analysis/overview', filters),
  })
}

function errorMessage(error: unknown): string | null {
  return error instanceof Error ? error.message : error ? String(error) : null
}

export function useAnalysisOverview(filters: AnalysisFilters) {
  const params = playParams(filters)
  const query = useQuery({
    queryKey: queryKeys.analysis.overview(params),
    queryFn: () => api.get<AnalysisOverviewResponse>('/analysis/overview', params),
  })

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    error: errorMessage(query.error),
    refetch: () => void query.refetch(),
  }
}

export function useApiData<T>(loader: () => Promise<T>, deps: DependencyList, enabled = true) {
  const query = useQuery({
    queryKey: ['legacy-api-data', ...deps],
    queryFn: loader,
    enabled,
  })

  return {
    data: query.data ?? null,
    loading: enabled ? query.isLoading : true,
    error: errorMessage(query.error),
    refetch: () => void query.refetch(),
  }
}

function fetchQuery<T>(key: readonly unknown[], queryFn: () => Promise<T>): Promise<T> {
  return queryClient.fetchQuery({ queryKey: key, queryFn })
}

function analysisParams(
  filters: AnalysisFilters,
  params: Record<string, string | number | boolean | undefined>,
): Record<string, string | number | boolean> {
  const result: Record<string, string | number | boolean> = { ...playParams(filters) }
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') {
      result[key] = value
    }
  }
  return result
}

export const analysisApi = {
  stats: (
    filters: AnalysisFilters,
    params: { period: AnalysisPeriod; start_date?: string; end_date?: string },
  ) => {
    const q = analysisParams(filters, params)
    return fetchQuery(
      queryKeys.analysis.stats(q),
      () => api.get<AnalysisStatsResponse>('/analysis/stats', q),
    )
  },
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
      include_compilations?: boolean
    },
  ) => {
    const q = analysisParams(filters, { ...params, merge_level: filters.merge_level })
    return fetchQuery(
      queryKeys.analysis.charts(q),
      () => api.get<AnalysisChartsResponse>('/analysis/charts', q),
    )
  },
  trackStats: (
    filters: AnalysisFilters,
    trackId: number | string,
    params: { period: AnalysisPeriod; start_date?: string; end_date?: string },
  ) => {
    const q = analysisParams(filters, params)
    return fetchQuery(
      queryKeys.music.entityStats('track', String(trackId), q),
      () => api.get<EntityStatsResponse>(`/music/tracks/${trackId}/stats`, q),
    )
  },
  albumStats: (
    filters: AnalysisFilters,
    albumName: string,
    artist: string | undefined,
    params: { period: AnalysisPeriod; start_date?: string; end_date?: string },
  ) => {
    const q = analysisParams(filters, { ...params, ...(artist ? { artist } : {}) })
    return fetchQuery(
      queryKeys.music.entityStats('album', `${artist ?? ''}:${albumName}`, q),
      () => api.get<EntityStatsResponse>(`/music/albums/${encodeURIComponent(albumName)}/stats`, q),
    )
  },
  artistStats: (
    filters: AnalysisFilters,
    artistName: string,
    params: { period: AnalysisPeriod; start_date?: string; end_date?: string },
  ) => {
    const q = analysisParams(filters, params)
    return fetchQuery(
      queryKeys.music.entityStats('artist', artistName, q),
      () => api.get<EntityStatsResponse>(`/music/artists/${encodeURIComponent(artistName)}/stats`, q),
    )
  },
  annual: (filters: AnalysisFilters) => {
    const q = playParams(filters)
    return fetchQuery(
      queryKeys.analysis.timeline('annual', q),
      () => api.get<TimelineAnnualPoint[]>('/timeline/annual', q),
    )
  },
  monthly: (filters: AnalysisFilters, period?: string) => {
    const q = analysisParams(filters, { period })
    return fetchQuery(
      queryKeys.analysis.timeline('monthly', q),
      () => api.get<TimelineMonthlyResponse>('/timeline/monthly', q),
    )
  },
  weekly: (filters: AnalysisFilters, week?: string) => {
    const q = analysisParams(filters, { week })
    return fetchQuery(
      queryKeys.analysis.timeline('weekly', q),
      () => api.get<TimelineWeeklyResponse>('/timeline/weekly', q),
    )
  },
  leaderboard: (
    filters: AnalysisFilters,
    entity: LeaderboardEntity,
    includeCompilations: boolean = false,
  ) => {
    const q = {
      ...playParams(filters),
      entity,
      metric: 'plays',
      time_range: 'all',
      top_n: 30,
      merge_level: filters.merge_level,
      include_compilations: includeCompilations,
    }
    return fetchQuery(
      queryKeys.analysis.leaderboard(q),
      () => api.get<LeaderboardResponse>('/leaderboard', q),
    )
  },
  behavior: (filters: AnalysisFilters) => {
    const q = { music_only: filters.music_only }
    return fetchQuery(
      queryKeys.analysis.timeline('behavior', q),
      () => api.get<BehaviorResponse>('/behavior', q),
    )
  },
  heatmap: (filters: AnalysisFilters) => {
    const q = playParams(filters)
    return fetchQuery(
      queryKeys.analysis.listeningHours('heatmap', q),
      () => api.get<HeatmapResponse>('/listening-hours/heatmap', q),
    )
  },
  yearlyHeatmaps: (filters: AnalysisFilters) => {
    const q = playParams(filters)
    return fetchQuery(
      queryKeys.analysis.listeningHours('yearly', q),
      () => api.get<YearlyHeatmapEntry[]>('/listening-hours/yearly', q),
    )
  },
  lateNight: (filters: AnalysisFilters) => {
    const q = playParams(filters)
    return fetchQuery(
      queryKeys.analysis.listeningHours('late-night', q),
      () => api.get<LateNightEntry[]>('/listening-hours/late-night', q),
    )
  },
  weekdayWeekend: (filters: AnalysisFilters) => {
    const q = playParams(filters)
    return fetchQuery(
      queryKeys.analysis.listeningHours('weekday-weekend', q),
      () => api.get<WeekdayWeekendResponse>('/listening-hours/weekday-weekend', q),
    )
  },
  platformHourly: (filters: AnalysisFilters) => {
    const q = playParams(filters)
    return fetchQuery(
      queryKeys.analysis.listeningHours('platform-hourly', q),
      () => api.get<PlatformHourlyResponse>('/listening-hours/platform-hourly', q),
    )
  },
  artistList: (filters: AnalysisFilters) => {
    const q = {
      min_ms: filters.min_ms,
      music_only: filters.music_only,
    }
    return fetchQuery(
      queryKeys.analysis.artistDeepDive('__list__', q),
      () => api.get<ArtistListEntry[]>('/artist/list', q),
    )
  },
  artistDeepDive: (filters: AnalysisFilters, name: string) => {
    const q = playParams(filters)
    return fetchQuery(
      queryKeys.analysis.artistDeepDive(name, q),
      () => api.get<ArtistDeepDiveResponse>(`/artist/${encodeURIComponent(name)}/deep-dive`, q),
    )
  },
  entityPlays: (
    kind: 'track' | 'album' | 'artist',
    id: string,
    filters: AnalysisFilters,
    params: { period: AnalysisPeriod; start_date?: string; end_date?: string; limit?: number; offset?: number; search?: string; date?: string; merge_level?: number },
    artistName?: string,
  ) => {
    const path =
      kind === 'track'
        ? `/music/tracks/${id}/plays`
        : kind === 'album'
          ? `/music/albums/${encodeURIComponent(id)}/plays`
          : `/music/artists/${encodeURIComponent(id)}/plays`
    const q = analysisParams(filters, {
      period: params.period,
      start_date: params.start_date,
      end_date: params.end_date,
      limit: params.limit ?? 50,
      offset: params.offset ?? 0,
      search: params.search,
      date: params.date,
      ...(kind === 'album' && artistName ? { artist: artistName } : {}),
    })
    return fetchQuery(
      queryKeys.music.entityPlays(kind, id, q, Math.floor(Number(q.offset ?? 0) / Number(q.limit ?? 50)) + 1),
      () => api.get<EntityPlaysResponse>(path, q),
    )
  },
  plays: (
    filters: AnalysisFilters,
    params: { period: AnalysisPeriod; start_date?: string; end_date?: string; limit?: number; offset?: number; search?: string; date?: string },
  ) => {
    const q = analysisParams(filters, {
      period: params.period,
      start_date: params.start_date,
      end_date: params.end_date,
      limit: params.limit ?? 50,
      offset: params.offset ?? 0,
      search: params.search,
      date: params.date,
    })
    return fetchQuery(
      queryKeys.analysis.plays(q, Math.floor(Number(q.offset ?? 0) / Number(q.limit ?? 50)) + 1),
      () => api.get<EntityPlaysResponse>('/analysis/plays', q),
    )
  },

  entityPlayDates: (
    kind: 'track' | 'album' | 'artist',
    id: string,
    filters: AnalysisFilters,
    params: { period: AnalysisPeriod; start_date?: string; end_date?: string; merge_level?: number },
    artistName?: string,
  ) => {
    const path =
      kind === 'track'
        ? `/music/tracks/${id}/play-dates`
        : kind === 'album'
          ? `/music/albums/${encodeURIComponent(id)}/play-dates`
          : `/music/artists/${encodeURIComponent(id)}/play-dates`
    const queryParams = analysisParams(filters, {
      ...params,
      ...(kind === 'album' && artistName ? { artist: artistName } : {}),
    })
    return fetchQuery(
      queryKeys.music.entityPlays(kind, `${id}:dates`, queryParams, 0),
      () => api.get<{ date: string; count: number }[]>(path, queryParams),
    )
  },

  playDates: (
    filters: AnalysisFilters,
    params: { period: AnalysisPeriod; start_date?: string; end_date?: string },
  ) => {
    const q = analysisParams(filters, params)
    return fetchQuery(
      queryKeys.analysis.timeline('play-dates', q),
      () => api.get<{ date: string; count: number }[]>('/analysis/play-dates', q),
    )
  },

  records: (
    filters: AnalysisFilters,
    params: { period: AnalysisPeriod; start_date?: string; end_date?: string; merge_level?: number; include_compilations?: boolean },
  ) => {
    const q = analysisParams(filters, {
      period: params.period,
      start_date: params.start_date,
      end_date: params.end_date,
      merge_level: params.merge_level ?? 2,
      include_compilations: params.include_compilations ?? false,
    })
    return fetchQuery(
      queryKeys.analysis.records(q),
      () => api.get<PlaybackRecordsResponse>('/analysis/records', q),
    )
  },
}
