import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/api/query-keys";
import { api } from "@/lib/api";
import type {
  ArtistIdentityCandidate,
  TrackCreditAction,
  TrackCreditDetail,
  TrackCreditEvent,
  TrackCreditMutation,
  TrackCreditManualChange,
  TrackCreditPreview,
  TrackCreditRole,
  TrackCreditState,
  TrackCreditTrackCandidate,
} from "@/types/settings";

export interface TrackCreditDraft {
  track_id: number;
  artist_id: number;
  action: TrackCreditAction;
  role: TrackCreditRole | null;
}

interface TrackCreditWrite extends TrackCreditDraft {
  expected_revision: number;
  reason?: string;
  evidence_type?: string;
  evidence_source?: string | null;
  confirm_duplicate_identity?: boolean;
}

function idempotencyKey(prefix: string): string {
  const suffix =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${suffix}`;
}

export function useTrackCredits(
  trackSearch: string,
  artistSearch: string,
  trackId: number | null,
) {
  const queryClient = useQueryClient();
  const status = useQuery({
    queryKey: queryKeys.settings.trackCredits(),
    queryFn: () =>
      api.get<{ state: TrackCreditState }>(
        "/music-metadata/track-credits/status",
      ),
  });
  const tracks = useQuery({
    queryKey: queryKeys.settings.trackCreditTracks(trackSearch),
    queryFn: () =>
      api.get<{ items: TrackCreditTrackCandidate[] }>(
        `/music-metadata/track-credits/tracks?q=${encodeURIComponent(trackSearch)}`,
      ),
    enabled: trackSearch.trim().length > 0,
  });
  const detail = useQuery({
    queryKey: queryKeys.settings.trackCreditDetail(trackId),
    queryFn: () =>
      api.get<TrackCreditDetail>(
        `/music-metadata/track-credits/tracks/${trackId}`,
      ),
    enabled: trackId != null,
  });
  const artists = useQuery({
    queryKey: queryKeys.settings.trackCreditArtistCandidates(artistSearch),
    queryFn: () =>
      api.get<{ items: ArtistIdentityCandidate[] }>(
        `/music-metadata/track-credits/artist-candidates?q=${encodeURIComponent(artistSearch)}`,
      ),
    enabled: artistSearch.trim().length > 0,
  });
  const events = useQuery({
    queryKey: queryKeys.settings.trackCreditEvents(trackId),
    queryFn: () =>
      api.get<{ items: TrackCreditEvent[] }>(
        `/music-metadata/track-credits/events${trackId == null ? "" : `?track_id=${trackId}`}`,
      ),
  });
  const manualChanges = useQuery({
    queryKey: queryKeys.settings.trackCreditManualChanges(),
    queryFn: () =>
      api.get<{ items: TrackCreditManualChange[] }>(
        "/music-metadata/track-credits/manual-changes",
      ),
  });

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.home.all });
    await queryClient.invalidateQueries();
  };
  const preview = useMutation({
    mutationFn: (draft: TrackCreditDraft) =>
      api.post<TrackCreditPreview>(
        "/music-metadata/track-credits/preview",
        draft,
      ),
  });
  const create = useMutation({
    mutationFn: (payload: TrackCreditWrite) =>
      api.post<TrackCreditMutation>("/music-metadata/track-credits/overrides", {
        ...payload,
        idempotency_key: idempotencyKey("track-credit-create"),
      }),
    onSuccess: invalidate,
  });
  const updateRole = useMutation({
    mutationFn: ({
      overrideId,
      role,
      revision,
    }: {
      overrideId: number;
      role: TrackCreditRole;
      revision: number;
    }) =>
      api.put<TrackCreditMutation>(
        `/music-metadata/track-credits/overrides/${overrideId}`,
        {
          role,
          expected_revision: revision,
          idempotency_key: idempotencyKey("track-credit-role"),
        },
      ),
    onSuccess: invalidate,
  });
  const remove = useMutation({
    mutationFn: ({
      overrideId,
      revision,
    }: {
      overrideId: number;
      revision: number;
    }) =>
      api.post<TrackCreditMutation>(
        `/music-metadata/track-credits/overrides/${overrideId}/remove`,
        {
          expected_revision: revision,
          idempotency_key: idempotencyKey("track-credit-remove"),
        },
      ),
    onSuccess: invalidate,
  });
  const undo = useMutation({
    mutationFn: ({
      eventId,
      revision,
    }: {
      eventId: number;
      revision: number;
    }) =>
      api.post<TrackCreditMutation>(
        `/music-metadata/track-credits/events/${eventId}/undo`,
        {
          expected_revision: revision,
          idempotency_key: idempotencyKey("track-credit-undo"),
        },
      ),
    onSuccess: invalidate,
  });
  const rebuild = useMutation({
    mutationFn: () =>
      api.post<{ revision: number; rebuild_job_id: string | null }>(
        "/music-metadata/track-credits/rebuild",
      ),
    onSuccess: invalidate,
  });

  return {
    state: detail.data?.state ?? status.data?.state,
    tracks: tracks.data?.items ?? [],
    tracksLoading: tracks.isFetching,
    detail,
    artists: artists.data?.items ?? [],
    artistsLoading: artists.isFetching,
    events: events.data?.items ?? [],
    manualChanges: manualChanges.data?.items ?? [],
    preview,
    create,
    updateRole,
    remove,
    undo,
    rebuild,
  };
}
