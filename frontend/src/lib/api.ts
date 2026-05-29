const BASE_URL = '/api'

interface RequestOptions {
  method?: string
  body?: unknown
  params?: Record<string, string | number | boolean>
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = new URL(`${BASE_URL}${path}`, window.location.origin)
  if (options.params) {
    Object.entries(options.params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) url.searchParams.set(k, String(v))
    })
  }
  const res = await fetch(url, {
    method: options.method ?? 'GET',
    headers: options.body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  })
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  get: <T>(path: string, params?: Record<string, string | number | boolean>) =>
    request<T>(path, { params }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body }),
  del: <T>(path: string) =>
    request<T>(path, { method: 'DELETE' }),
}

export type { DashboardSummary, DashboardFullResponse, MonthlyTrendPoint, PlatformDist, TopTrack, DowDist, RandomTrack, AccountKpi } from '@/types/dashboard'
export type { AnalysisOverviewResponse, AnalysisFilters, AnalysisTimeRange, AnalysisPeriod, AnalysisMetric, LeaderboardEntity, AnalysisStatsResponse, AnalysisChartsResponse, EntityStatsResponse } from '@/types/analysis'
export type { BillboardDataResponse, BillboardRecords, BillboardMeta, WeeklyTrackEntry, WeeklyAlbumEntry, WeeklyArtistEntry, TrackSummary, AlbumTrackCounts, ArtistTrackCounts, PowerScoreEntry, TrackDetailResponse, ArtistDetailResponse, AlbumDetailResponse, AlbumEnrichmentResponse, ArtistEnrichmentResponse, TrackEnrichmentResponse, ReleaseCycleAlbumDetailResponse, ReleaseCycleArtistOverviewResponse, StructuredArtist, StructuredAlbum, KeyFact, StatItem, CareerEvent, Achievement, ChartEntry } from '@/types/billboard'
export type { SettingsData, SettingsUpdatePayload, ImportJob, ReleaseGroup, GroupMember, UngroupedAlbum, DetectionResult, DetectionMember, TrackComparison, TrackRow, RebuildResult, LLMProfile, LLMProfileDetail, LLMProfileCreatePayload, LLMProfileUpdatePayload, LLMProfileCreateResult } from '@/types/settings'
