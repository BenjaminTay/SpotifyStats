import { useState, useEffect, useCallback, useRef } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '@/api/query-keys'
import { api, type SettingsData, type SettingsUpdatePayload, type ImportJob, type ReleaseGroup, type GroupMember, type UngroupedAlbum, type DetectionResult, type TrackGroupCandidate, type TrackGroupConfirmResult, type AlbumRelationConfirmResult, type TrackComparison, type RebuildResult, type VersionMergeScope, type TrackGroupScope, type LLMProfile, type LLMProfileDetail, type LLMProfileCreatePayload, type LLMProfileUpdatePayload, type LLMProfileCreateResult } from '@/lib/api'

// ── useSettings ─────────────────────────────────────────────

interface ClearCacheResult {
  status: string
  deleted_count: number
}

interface SpotifyAuthUrl { auth_url: string; state: string }
interface SpotifyStatus { connected: boolean; scope?: string; connected_at?: string }
interface SpotifySyncResult { success: boolean; total_in_spotify?: number; total_in_db?: number; matched?: number; new_dates?: number; error?: string }

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
      if (!Number.isNaN(n) && n >= 1 && n <= 240) return n
    }
  } catch { /* localStorage unavailable */ }
  return undefined
}

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
  applyProfile: (profileId: number) => Promise<{ status: string; profile_id: number }>
  createProfile: (payload: LLMProfileCreatePayload) => Promise<LLMProfileCreateResult>
  updateProfile: (profileId: number, payload: LLMProfileUpdatePayload) => Promise<LLMProfileDetail>
  deleteProfile: (profileId: number) => Promise<{ status: string }>
}

export function useSettings(): UseSettingsResult {
  const queryClient = useQueryClient()
  const settingsQuery = useQuery({
    queryKey: queryKeys.settings.data(),
    queryFn: () => api.get<SettingsData>('/settings'),
  })
  const [streamingJob, setStreamingJob] = useState<ImportJob | null>(null)
  const [accountJob, setAccountJob] = useState<ImportJob | null>(null)
  const pollRef = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map())

  const refetch = useCallback(() => {
    void settingsQuery.refetch()
  }, [settingsQuery])

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      pollRef.current.forEach((interval) => clearInterval(interval))
      pollRef.current.clear()
    }
  }, [])

  const updateSettings = useCallback(async (payload: SettingsUpdatePayload) => {
    const updated = await api.put<SettingsData>('/settings', payload)
    queryClient.setQueryData(queryKeys.settings.data(), updated)
  }, [queryClient])

  const updateApiKey = useCallback(async (apiKey: string, baseUrl?: string) => {
    const payload: Record<string, string> = { llm_api_key: apiKey }
    if (baseUrl !== undefined) payload.llm_base_url = baseUrl
    await api.put('/settings', payload)
    await settingsQuery.refetch()
  }, [settingsQuery])

  const rebuildAgg = useCallback(() => {
    const params = new URLSearchParams()
    params.set('dynamic_threshold', String(getStoredBool('spotify_stats_dynamic_threshold', true)))
    const maxGap = getStoredNumber('spotify_stats_max_merge_gap_minutes')
    if (maxGap != null) params.set('max_merge_gap_minutes', String(maxGap))
    return api.post<RebuildResult>(`/settings/rebuild-agg?${params.toString()}`, undefined, 120_000)
  }, [])

  const clearTranslationCache = useCallback(() => {
    return api.post<ClearCacheResult>('/settings/clear-translation-cache')
  }, [])

  const fetchProfiles = useCallback(() => {
    return queryClient.fetchQuery({
      queryKey: queryKeys.settings.llmProfiles(),
      queryFn: () => api.get<LLMProfile[]>('/settings/llm-profiles'),
    })
  }, [queryClient])

  const getProfileDetail = useCallback((profileId: number) => {
    return queryClient.fetchQuery({
      queryKey: queryKeys.settings.llmProfile(profileId),
      queryFn: () => api.get<LLMProfileDetail>(`/settings/llm-profiles/${profileId}`),
    })
  }, [queryClient])

  const createProfile = useCallback(async (payload: LLMProfileCreatePayload) => {
    const result = await api.post<LLMProfileCreateResult>('/settings/llm-profiles', payload)
    await queryClient.invalidateQueries({ queryKey: queryKeys.settings.llmProfiles() })
    return result
  }, [queryClient])

  const updateProfile = useCallback(async (profileId: number, payload: LLMProfileUpdatePayload) => {
    const result = await api.put<LLMProfileDetail>(`/settings/llm-profiles/${profileId}`, payload)
    queryClient.setQueryData(queryKeys.settings.llmProfile(profileId), result)
    await queryClient.invalidateQueries({ queryKey: queryKeys.settings.llmProfiles() })
    return result
  }, [queryClient])

  const deleteProfile = useCallback(async (profileId: number) => {
    const result = await api.del<{ status: string }>(`/settings/llm-profiles/${profileId}`)
    queryClient.removeQueries({ queryKey: queryKeys.settings.llmProfile(profileId) })
    await queryClient.invalidateQueries({ queryKey: queryKeys.settings.llmProfiles() })
    return result
  }, [queryClient])

  const applyProfile = useCallback(async (profileId: number) => {
    const result = await api.post<{ status: string; profile_id: number }>(`/settings/llm-profiles/${profileId}/apply`)
    await settingsQuery.refetch()
    return result
  }, [settingsQuery])

  const spotifyConnect = useCallback(() => {
    return api.get<SpotifyAuthUrl>('/spotify/auth/login')
  }, [])

  const spotifyDisconnect = useCallback(async () => {
    await api.del('/spotify/auth/disconnect')
    await settingsQuery.refetch()
  }, [settingsQuery])

  const spotifySync = useCallback(() => {
    return api.post<SpotifySyncResult>('/spotify/auth/sync')
  }, [])

  const checkSpotifyStatus = useCallback(() => {
    return queryClient.fetchQuery({
      queryKey: queryKeys.settings.spotifyStatus(),
      queryFn: () => api.get<SpotifyStatus>('/spotify/auth/status'),
    })
  }, [queryClient])

  const pollImport = useCallback((jobId: string, setter: Dispatch<SetStateAction<ImportJob | null>>) => {
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
    settings: settingsQuery.data ?? null,
    loading: settingsQuery.isLoading,
    error: settingsQuery.error instanceof Error ? settingsQuery.error.message : null,
    refetch,
    updateSettings,
    updateApiKey,
    clearTranslationCache,
    rebuildAgg,
    startStreamingImport, startAccountImport, streamingJob, accountJob,
    spotifyConnect, spotifyDisconnect, spotifySync, checkSpotifyStatus,
    applyProfile,
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
  fetchCollaborationCandidates: () => Promise<TrackGroupCandidate[]>
  confirmTrackCandidate: (originalTrackId: number, candidateTrackId: number, scope?: TrackGroupScope) => Promise<TrackGroupConfirmResult>
  rebuildAlbumProjects: () => Promise<{ status: string }>
  getGroupMembers: (groupId: number) => Promise<GroupMember[]>
  getUngroupedAlbums: (artistName?: string) => Promise<UngroupedAlbum[]>
  compareAlbums: (aId: number, bId: number) => Promise<TrackComparison>
  getAlbumTypes: (ids: number[]) => Promise<Record<string, string>>
  createGroup: (canonicalName: string, artistId: number, primaryAlbumId: number, memberIds: number[], scope?: VersionMergeScope) => Promise<{ group_id: number }>
  confirmAlbumRelation: (canonicalName: string, primaryAlbumId: number, memberAlbumIds: number[], scope?: VersionMergeScope, relationType?: string, confirmTrackPairs?: boolean) => Promise<AlbumRelationConfirmResult>
  updateMembers: (groupId: number, addIds?: number[], removeIds?: number[]) => Promise<{ status: string }>
  setPrimary: (groupId: number, albumId: number) => Promise<{ status: string }>
  deleteGroup: (groupId: number) => Promise<{ status: string }>
}

export function useVersionMerge(): UseVersionMergeResult {
  const queryClient = useQueryClient()
  const groupsQuery = useQuery({
    queryKey: queryKeys.versionMerge.groups(),
    queryFn: () => api.get<ReleaseGroup[]>('/version-merge/groups'),
    enabled: false,
  })

  const fetchGroups = useCallback(() => {
    void groupsQuery.refetch()
  }, [groupsQuery])

  const invalidateMergeDependents = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.versionMerge.all })
    void queryClient.invalidateQueries({ queryKey: queryKeys.analysis.all })
    void queryClient.invalidateQueries({ queryKey: queryKeys.billboard.all })
    void queryClient.invalidateQueries({ queryKey: queryKeys.music.all })
  }, [queryClient])

  const detectGroups = useCallback((overlapThreshold: number) => {
    return api.post<DetectionResult[]>(`/version-merge/detect?overlap_threshold=${overlapThreshold}`)
  }, [])

  const applyDetected = useCallback((confirmedGroups: DetectionResult[]) => {
    return api.post<{ created_count: number; skipped_count: number }>('/version-merge/apply', { confirmed_groups: confirmedGroups })
      .then((result) => {
        invalidateMergeDependents()
        return result
      })
  }, [invalidateMergeDependents])

  const fetchCollaborationCandidates = useCallback(() => {
    return queryClient.fetchQuery({
      queryKey: queryKeys.versionMerge.collaborationCandidates(),
      queryFn: () => api.get<TrackGroupCandidate[]>('/version-merge/track-group-candidates/collaboration'),
    })
  }, [queryClient])

  const confirmTrackCandidate = useCallback((originalTrackId: number, candidateTrackId: number, scope: TrackGroupScope = 'composition') => {
    return api.post<TrackGroupConfirmResult>('/version-merge/track-groups/confirm', {
      original_track_id: originalTrackId,
      candidate_track_id: candidateTrackId,
      scope,
    }).then((result) => {
      invalidateMergeDependents()
      return result
    })
  }, [invalidateMergeDependents])

  const rebuildAlbumProjects = useCallback(() => {
    return api.post<{ status: string }>('/version-merge/album-projects/rebuild')
      .then((result) => {
        invalidateMergeDependents()
        return result
      })
  }, [invalidateMergeDependents])

  const getGroupMembers = useCallback((groupId: number) => {
    return queryClient.fetchQuery({
      queryKey: queryKeys.versionMerge.members(groupId),
      queryFn: () => api.get<GroupMember[]>(`/version-merge/groups/${groupId}/members`),
    })
  }, [queryClient])

  const getUngroupedAlbums = useCallback((artistName?: string) => {
    const params = artistName ? { artist_name: artistName } : undefined
    return queryClient.fetchQuery({
      queryKey: queryKeys.versionMerge.ungrouped(artistName),
      queryFn: () => api.get<UngroupedAlbum[]>('/version-merge/ungrouped', params as Record<string, string | number | boolean>),
    })
  }, [queryClient])

  const compareAlbums = useCallback((aId: number, bId: number) => {
    return queryClient.fetchQuery({
      queryKey: queryKeys.versionMerge.comparison(aId, bId),
      queryFn: () => api.get<TrackComparison>(`/version-merge/compare?album_id_a=${aId}&album_id_b=${bId}`),
    })
  }, [queryClient])

  const getAlbumTypes = useCallback((ids: number[]) => {
    return queryClient.fetchQuery({
      queryKey: queryKeys.versionMerge.albumTypes(ids),
      queryFn: () => api.get<Record<string, string>>(`/version-merge/album-types?album_ids=${ids.join(',')}`),
    })
  }, [queryClient])

  const createGroup = useCallback((canonicalName: string, artistId: number, primaryAlbumId: number, memberIds: number[], scope: VersionMergeScope = 'release') => {
    return api.post<{ group_id: number }>('/version-merge/groups', {
      canonical_name: canonicalName,
      artist_id: artistId,
      primary_album_id: primaryAlbumId,
      member_ids: memberIds,
      scope,
    }).then((result) => {
      invalidateMergeDependents()
      return result
    })
  }, [invalidateMergeDependents])

  const confirmAlbumRelation = useCallback((
    canonicalName: string,
    primaryAlbumId: number,
    memberAlbumIds: number[],
    scope: VersionMergeScope = 'composition',
    relationType = 'rerecord',
    confirmTrackPairs = true,
  ) => {
    return api.post<AlbumRelationConfirmResult>('/version-merge/album-relations/confirm', {
      canonical_name: canonicalName,
      primary_album_id: primaryAlbumId,
      member_album_ids: memberAlbumIds,
      scope,
      relation_type: relationType,
      confirm_track_pairs: confirmTrackPairs,
    }).then((result) => {
      invalidateMergeDependents()
      return result
    })
  }, [invalidateMergeDependents])

  const updateMembers = useCallback((groupId: number, addIds?: number[], removeIds?: number[]) => {
    return api.put<{ status: string }>(`/version-merge/groups/${groupId}/members`, {
      add_ids: addIds ?? null,
      remove_ids: removeIds ?? null,
    }).then((result) => {
      invalidateMergeDependents()
      void queryClient.invalidateQueries({ queryKey: queryKeys.versionMerge.members(groupId) })
      return result
    })
  }, [invalidateMergeDependents, queryClient])

  const setPrimary = useCallback((groupId: number, albumId: number) => {
    return api.put<{ status: string }>(`/version-merge/groups/${groupId}/primary`, { album_id: albumId })
      .then((result) => {
        invalidateMergeDependents()
        void queryClient.invalidateQueries({ queryKey: queryKeys.versionMerge.members(groupId) })
        return result
      })
  }, [invalidateMergeDependents, queryClient])

  const deleteGroup = useCallback((groupId: number) => {
    return api.del<{ status: string }>(`/version-merge/groups/${groupId}`)
      .then((result) => {
        invalidateMergeDependents()
        void queryClient.removeQueries({ queryKey: queryKeys.versionMerge.members(groupId) })
        return result
      })
  }, [invalidateMergeDependents, queryClient])

  return {
    groups: groupsQuery.data ?? [],
    groupsLoading: groupsQuery.isFetching,
    fetchGroups,
    detectGroups, applyDetected, fetchCollaborationCandidates, confirmTrackCandidate, rebuildAlbumProjects,
    getGroupMembers, getUngroupedAlbums,
    compareAlbums, getAlbumTypes, createGroup, confirmAlbumRelation, updateMembers, setPrimary, deleteGroup,
  }
}
