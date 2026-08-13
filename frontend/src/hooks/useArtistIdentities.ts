import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { queryKeys } from '@/api/query-keys'
import { api } from '@/lib/api'
import type {
  ArtistIdentityCandidate,
  ArtistIdentityEvent,
  ArtistIdentityMutation,
  ArtistIdentityOverview,
  ArtistIdentityPreview,
} from '@/types/settings'

export interface IdentityDraft {
  artist_ids: number[]
  canonical_artist_id: number
  display_name: string
}

interface IdentityWrite extends IdentityDraft {
  expected_revision: number
  idempotency_key: string
  reason?: string
  confirm_external_id_conflict?: boolean
}

interface IdentityUpdate {
  add_ids?: number[]
  remove_ids?: number[]
  canonical_artist_id?: number
  display_name?: string
  provider_metadata_artist_id?: number
  expected_revision: number
  idempotency_key: string
  reason?: string
  confirm_external_id_conflict?: boolean
}

function idempotencyKey(prefix: string): string {
  const suffix = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `${prefix}-${suffix}`
}

export function useArtistIdentities(search: string) {
  const queryClient = useQueryClient()
  const overview = useQuery({
    queryKey: queryKeys.settings.artistIdentities(),
    queryFn: () => api.get<ArtistIdentityOverview>('/artist-identities'),
  })
  const candidates = useQuery({
    queryKey: queryKeys.settings.artistIdentityCandidates(search),
    queryFn: () => api.get<{ items: ArtistIdentityCandidate[] }>(
      `/artist-identities/candidates?q=${encodeURIComponent(search)}`,
    ),
    enabled: search.trim().length > 0,
  })
  const events = useQuery({
    queryKey: queryKeys.settings.artistIdentityEvents(),
    queryFn: () => api.get<{ items: ArtistIdentityEvent[] }>('/artist-identities/events'),
  })

  const invalidateIdentityChange = async () => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.home.all })
    await queryClient.invalidateQueries()
  }
  const preview = useMutation({
    mutationFn: (draft: IdentityDraft) =>
      api.post<ArtistIdentityPreview>('/artist-identities/preview', draft),
  })
  const create = useMutation({
    mutationFn: (payload: Omit<IdentityWrite, 'idempotency_key'>) =>
      api.post<ArtistIdentityMutation>('/artist-identities', {
        ...payload,
        idempotency_key: idempotencyKey('artist-identity-create'),
      }),
    onSuccess: invalidateIdentityChange,
  })
  const update = useMutation({
    mutationFn: ({ identityId, payload }: { identityId: number; payload: Omit<IdentityUpdate, 'idempotency_key'> }) =>
      api.put<ArtistIdentityMutation>(`/artist-identities/${identityId}`, {
        ...payload,
        idempotency_key: idempotencyKey('artist-identity-update'),
      }),
    onSuccess: invalidateIdentityChange,
  })
  const undo = useMutation({
    mutationFn: ({ eventId, revision }: { eventId: number; revision: number }) =>
      api.post<ArtistIdentityMutation>(`/artist-identities/events/${eventId}/undo`, {
        expected_revision: revision,
        idempotency_key: idempotencyKey('artist-identity-undo'),
      }),
    onSuccess: invalidateIdentityChange,
  })

  return {
    overview,
    candidates: candidates.data?.items ?? [],
    candidatesLoading: candidates.isFetching,
    events: events.data?.items ?? [],
    preview,
    create,
    update,
    undo,
  }
}
