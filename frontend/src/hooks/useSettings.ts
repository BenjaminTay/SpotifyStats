import { useState, useEffect, useCallback, useRef } from 'react'
import { api, type SettingsData, type SettingsUpdatePayload, type ImportJob, type ReleaseGroup, type GroupMember, type UngroupedAlbum, type DetectionResult, type TrackComparison, type RebuildResult, type LLMProfile, type LLMProfileDetail, type LLMProfileCreatePayload, type LLMProfileUpdatePayload, type LLMProfileCreateResult } from '@/lib/api'

// ── Module-level settings cache ─────────────────────────────

let cachedSettings: SettingsData | null = null

// ── useSettings ─────────────────────────────────────────────

interface ClearCacheResult {
  status: string
  deleted_count: number
}

interface SpotifyAuthUrl { auth_url: string; state: string }
interface SpotifyStatus { connected: boolean; scope?: string; connected_at?: string }
interface SpotifySyncResult { success: boolean; total_in_spotify?: number; total_in_db?: number; matched?: number; new_dates?: number; error?: string }

interface UseSettingsResult {
  settings: SettingsData | null
  loading: boolean
  error: string | null
  refetch: () => void
  updateSettings: (payload: SettingsUpdatePayload) => Promise<void>
  updateApiKey: (apiKey: string, baseUrl?: string) => Promise<void>
  clearTranslationCache: () => Promise<ClearCacheResult>
  rebuildAgg: () => Promise<RebuildResult>
  startStreamingImport: () => void
  startAccountImport: () => void
  streamingJob: ImportJob | null
  accountJob: ImportJob | null
  // Spotify OAuth
  spotifyConnect: () => Promise<SpotifyAuthUrl>
  spotifyDisconnect: () => Promise<void>
  spotifySync: () => Promise<SpotifySyncResult>
  checkSpotifyStatus: () => Promise<SpotifyStatus>
  // LLM profiles
  fetchProfiles: () => Promise<LLMProfile[]>
  getProfileDetail: (profileId: number) => Promise<LLMProfileDetail>
  createProfile: (payload: LLMProfileCreatePayload) => Promise<LLMProfileCreateResult>
  updateProfile: (profileId: number, payload: LLMProfileUpdatePayload) => Promise<LLMProfileDetail>
  deleteProfile: (profileId: number) => Promise<{ status: string }>
}

export function useSettings(): UseSettingsResult {
  const [settings, setSettings] = useState<SettingsData | null>(cachedSettings)
  const [loading, setLoading] = useState(!cachedSettings)
  const [error, setError] = useState<string | null>(null)
  const [streamingJob, setStreamingJob] = useState<ImportJob | null>(null)
  const [accountJob, setAccountJob] = useState<ImportJob | null>(null)
  const pollRef = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map())

  const refetch = useCallback(() => {
    setLoading(true)
    api.get<SettingsData>('/settings')
      .then((d) => {
        cachedSettings = d
        setSettings(d)
        setError(null)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!cachedSettings) refetch()
  }, [refetch])

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      pollRef.current.forEach((interval) => clearInterval(interval))
      pollRef.current.clear()
    }
  }, [])

  const updateSettings = useCallback(async (payload: SettingsUpdatePayload) => {
    const updated = await api.put<SettingsData>('/settings', payload)
    cachedSettings = updated
    setSettings(updated)
  }, [])

  const updateApiKey = useCallback(async (apiKey: string, baseUrl?: string) => {
    const payload: Record<string, string> = { llm_api_key: apiKey }
    if (baseUrl !== undefined) payload.llm_base_url = baseUrl
    await api.put('/settings', payload)
  }, [])

  const rebuildAgg = useCallback(() => {
    return api.post<RebuildResult>('/settings/rebuild-agg')
  }, [])

  const clearTranslationCache = useCallback(() => {
    return api.post<ClearCacheResult>('/settings/clear-translation-cache')
  }, [])

  const fetchProfiles = useCallback(() => {
    return api.get<LLMProfile[]>('/settings/llm-profiles')
  }, [])

  const getProfileDetail = useCallback((profileId: number) => {
    return api.get<LLMProfileDetail>(`/settings/llm-profiles/${profileId}`)
  }, [])

  const createProfile = useCallback((payload: LLMProfileCreatePayload) => {
    return api.post<LLMProfileCreateResult>('/settings/llm-profiles', payload)
  }, [])

  const updateProfile = useCallback((profileId: number, payload: LLMProfileUpdatePayload) => {
    return api.put<LLMProfileDetail>(`/settings/llm-profiles/${profileId}`, payload)
  }, [])

  const deleteProfile = useCallback((profileId: number) => {
    return api.del<{ status: string }>(`/settings/llm-profiles/${profileId}`)
  }, [])

  const spotifyConnect = useCallback(() => {
    return api.get<SpotifyAuthUrl>('/spotify/auth/login')
  }, [])

  const spotifyDisconnect = useCallback(async () => {
    await api.del('/spotify/auth/disconnect')
    await refetch()
  }, [refetch])

  const spotifySync = useCallback(() => {
    return api.post<SpotifySyncResult>('/spotify/auth/sync')
  }, [])

  const checkSpotifyStatus = useCallback(() => {
    return api.get<SpotifyStatus>('/spotify/auth/status')
  }, [])

  const pollImport = useCallback((jobId: string, setter: React.Dispatch<React.SetStateAction<ImportJob | null>>) => {
    // Clear any existing poll for this setter's job
    const existing = pollRef.current.get('streaming')
    if (existing) clearInterval(existing)

    const interval = setInterval(() => {
      api.get<ImportJob>(`/import/status/${jobId}`).then((status) => {
        setter(status)
        if (status.status === 'done' || status.status === 'error') {
          clearInterval(interval)
          pollRef.current.delete('streaming')
          if (status.status === 'done') refetch()
        }
      }).catch(() => {})
    }, 1000)

    pollRef.current.set('streaming', interval)
  }, [refetch])

  const startStreamingImport = useCallback(() => {
    api.post<{ job_id: string }>('/import/streaming').then(({ job_id }) => {
      setStreamingJob({ job_id, status: 'running', progress_pct: 0, message: '初始化...', result: null })
      pollImport(job_id, setStreamingJob)
    })
  }, [pollImport])

  const startAccountImport = useCallback(() => {
    api.post<{ job_id: string }>('/import/account').then(({ job_id }) => {
      setAccountJob({ job_id, status: 'running', progress_pct: 0, message: '初始化...', result: null })
      // Use separate track for account polling
      const interval = setInterval(() => {
        api.get<ImportJob>(`/import/status/${job_id}`).then((status) => {
          setAccountJob(status)
          if (status.status === 'done' || status.status === 'error') {
            clearInterval(interval)
            pollRef.current.delete('account')
            if (status.status === 'done') refetch()
          }
        }).catch(() => {})
      }, 1000)
      pollRef.current.set('account', interval)
    })
  }, [refetch])

  return {
    settings, loading, error, refetch, updateSettings, updateApiKey, clearTranslationCache, rebuildAgg,
    startStreamingImport, startAccountImport, streamingJob, accountJob,
    spotifyConnect, spotifyDisconnect, spotifySync, checkSpotifyStatus,
    fetchProfiles, getProfileDetail, createProfile, updateProfile, deleteProfile,
  }
}

// ── useVersionMerge ─────────────────────────────────────────

interface UseVersionMergeResult {
  groups: ReleaseGroup[]
  groupsLoading: boolean
  fetchGroups: () => void
  detectGroups: (overlapThreshold: number) => Promise<DetectionResult[]>
  applyDetected: (confirmedGroups: DetectionResult[]) => Promise<{ created_count: number; skipped_count: number }>
  getGroupMembers: (groupId: number) => Promise<GroupMember[]>
  getUngroupedAlbums: (artistName?: string) => Promise<UngroupedAlbum[]>
  compareAlbums: (aId: number, bId: number) => Promise<TrackComparison>
  getAlbumTypes: (ids: number[]) => Promise<Record<string, string>>
  createGroup: (canonicalName: string, artistId: number, primaryAlbumId: number, memberIds: number[]) => Promise<{ group_id: number }>
  updateMembers: (groupId: number, addIds?: number[], removeIds?: number[]) => Promise<{ status: string }>
  setPrimary: (groupId: number, albumId: number) => Promise<{ status: string }>
  deleteGroup: (groupId: number) => Promise<{ status: string }>
}

export function useVersionMerge(): UseVersionMergeResult {
  const [groups, setGroups] = useState<ReleaseGroup[]>([])
  const [groupsLoading, setGroupsLoading] = useState(false)

  const fetchGroups = useCallback(() => {
    setGroupsLoading(true)
    api.get<ReleaseGroup[]>('/version-merge/groups')
      .then(setGroups)
      .finally(() => setGroupsLoading(false))
  }, [])

  const detectGroups = useCallback((overlapThreshold: number) => {
    return api.post<DetectionResult[]>(`/version-merge/detect?overlap_threshold=${overlapThreshold}`)
  }, [])

  const applyDetected = useCallback((confirmedGroups: DetectionResult[]) => {
    return api.post<{ created_count: number; skipped_count: number }>('/version-merge/apply', { confirmed_groups: confirmedGroups })
  }, [])

  const getGroupMembers = useCallback((groupId: number) => {
    return api.get<GroupMember[]>(`/version-merge/groups/${groupId}/members`)
  }, [])

  const getUngroupedAlbums = useCallback((artistName?: string) => {
    const params = artistName ? { artist_name: artistName } : undefined
    return api.get<UngroupedAlbum[]>('/version-merge/ungrouped', params as Record<string, string | number | boolean>)
  }, [])

  const compareAlbums = useCallback((aId: number, bId: number) => {
    return api.get<TrackComparison>(`/version-merge/compare?album_id_a=${aId}&album_id_b=${bId}`)
  }, [])

  const getAlbumTypes = useCallback((ids: number[]) => {
    return api.get<Record<string, string>>(`/version-merge/album-types?album_ids=${ids.join(',')}`)
  }, [])

  const createGroup = useCallback((canonicalName: string, artistId: number, primaryAlbumId: number, memberIds: number[]) => {
    return api.post<{ group_id: number }>('/version-merge/groups', {
      canonical_name: canonicalName,
      artist_id: artistId,
      primary_album_id: primaryAlbumId,
      member_ids: memberIds,
    })
  }, [])

  const updateMembers = useCallback((groupId: number, addIds?: number[], removeIds?: number[]) => {
    return api.put<{ status: string }>(`/version-merge/groups/${groupId}/members`, {
      add_ids: addIds ?? null,
      remove_ids: removeIds ?? null,
    })
  }, [])

  const setPrimary = useCallback((groupId: number, albumId: number) => {
    return api.put<{ status: string }>(`/version-merge/groups/${groupId}/primary`, { album_id: albumId })
  }, [])

  const deleteGroup = useCallback((groupId: number) => {
    return api.del<{ status: string }>(`/version-merge/groups/${groupId}`)
  }, [])

  return {
    groups, groupsLoading, fetchGroups,
    detectGroups, applyDetected, getGroupMembers, getUngroupedAlbums,
    compareAlbums, getAlbumTypes, createGroup, updateMembers, setPrimary, deleteGroup,
  }
}
