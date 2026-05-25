const BASE_URL = '/api'

async function request<T>(path: string, params?: Record<string, string | number | boolean>): Promise<T> {
  const url = new URL(`${BASE_URL}${path}`, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) url.searchParams.set(k, String(v))
    })
  }
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  get: <T>(path: string, params?: Record<string, string | number | boolean>) =>
    request<T>(path, params),
}

export type { DashboardSummary, DashboardFullResponse, MonthlyTrendPoint, PlatformDist, TopTrack, DowDist, RandomTrack, AccountKpi } from '@/types/dashboard'
export type { BillboardDataResponse, BillboardMeta, WeeklyTrackEntry, WeeklyAlbumEntry, WeeklyArtistEntry, TrackSummary, PowerScoreEntry } from '@/types/billboard'
