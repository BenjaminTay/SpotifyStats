import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { TrackCreditManager } from '@/features/settings/components/TrackCreditManager'
import type { TrackCreditState } from '@/types/settings'

const { useTrackCreditsMock, previewMutateAsync, createMutateAsync } = vi.hoisted(() => ({
  useTrackCreditsMock: vi.fn(),
  previewMutateAsync: vi.fn(),
  createMutateAsync: vi.fn(),
}))

vi.mock('@/hooks/useTrackCredits', () => ({
  useTrackCredits: useTrackCreditsMock,
}))

const eltonCredit = {
  track_id: 175,
  artist_id: 42,
  artist_name: 'Elton John',
  raw_artist_ids: [42],
  role: 'primary' as const,
  source: 'raw' as const,
  override_id: null,
}

function hookResult() {
  return {
    state: {
      current_revision: 0,
      active_aggregate_revision: 0,
      rebuild_status: 'ready',
      last_error: null,
    },
    tracks: [],
    tracksLoading: false,
    detail: {
      data: {
        track: {
          track_id: 175,
          track_name: 'Hold Me Closer',
          spotify_track_id: '72yP0DUlWPyH8P7IoxskwN',
          album_id: 80,
          album_name: 'Hold Me Closer',
          raw_primary_artist_id: 42,
          raw_primary_artist_name: 'Elton John',
        },
        state: {
          current_revision: 0,
          active_aggregate_revision: 0,
          rebuild_status: 'ready',
          last_error: null,
        },
        raw_credits: [
          {
            track_id: 175,
            artist_id: 42,
            artist_name: 'Elton John',
            role: 'primary',
            source: 'raw',
            canonical_artist_id: 42,
            canonical_display_name: 'Elton John',
          },
        ],
        manual_overrides: [],
        effective_credits: [eltonCredit],
      },
    },
    artists: [
      {
        artist_id: 53,
        artist_name: 'Britney Spears',
        canonical_artist_id: 53,
        canonical_display_name: 'Britney Spears',
        identity_id: null,
        play_count: 1200,
        first_play_date: '2012-01-01',
        last_play_date: '2026-01-01',
        cover_url: null,
        external_ids: [
          {
            provider: 'spotify',
            external_id: '26dSoYclwsYLMAKD3tpOr4',
            evidence_type: 'provider_metadata',
            confidence: 1,
            verified: true,
          },
        ],
      },
    ],
    artistsLoading: false,
    events: [],
    manualChanges: [],
    preview: {
      data: null,
      isPending: false,
      mutateAsync: previewMutateAsync,
      reset: vi.fn(),
      error: null,
    },
    create: { mutateAsync: createMutateAsync, isPending: false, error: null },
    updateRole: { mutateAsync: vi.fn(), isPending: false },
    remove: { mutateAsync: vi.fn(), isPending: false },
    undo: { mutateAsync: vi.fn(), isPending: false },
    rebuild: { mutate: vi.fn(), isPending: false },
  }
}

describe('TrackCreditManager', () => {
  beforeEach(() => {
    previewMutateAsync.mockReset()
    createMutateAsync.mockReset()
    previewMutateAsync.mockResolvedValue({
      no_change: false,
      duplicate_canonical_identity: false,
    })
    useTrackCreditsMock.mockImplementation(() => hookResult())
  })

  it('shows raw, manual and effective credits without rewriting the track fact', () => {
    render(<TrackCreditManager initialTrackId={175} />)

    expect(screen.queryByRole('heading', { name: '曲目署名' })).not.toBeInTheDocument()
    expect(screen.getByText('自动署名')).toBeInTheDocument()
    expect(screen.getByText('人工修改')).toBeInTheDocument()
    expect(screen.getByText('最终有效署名')).toBeInTheDocument()
    expect(screen.getAllByText('Elton John').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText(/Spotify 72yP0DUlWPyH8P7IoxskwN/)).toBeInTheDocument()
  })

  it('applies a featured artist using the stable local artist id without reason fields', async () => {
    render(<TrackCreditManager initialTrackId={175} />)

    fireEvent.change(screen.getByLabelText('搜索署名艺人候选'), {
      target: { value: 'Britney' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Britney Spears/ }))
    expect(screen.getByText(/raw #53 → canonical #53/)).toBeInTheDocument()
    expect(screen.getByText(/spotify:26dSoYclwsYLMAKD3tpOr4/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '应用修改' }))

    await waitFor(() => expect(createMutateAsync).toHaveBeenCalledWith({
      track_id: 175, artist_id: 53, action: 'add', role: 'featured',
      expected_revision: 0, confirm_duplicate_identity: false,
    }))
    expect(screen.queryByText('操作理由')).not.toBeInTheDocument()
    expect(screen.queryByText(/证据来源/)).not.toBeInTheDocument()
  })

  it('keeps role and action controls keyboard-addressable', () => {
    render(<TrackCreditManager initialTrackId={175} />)

    expect(screen.getByRole('combobox', { name: '署名操作' })).toBeEnabled()
    expect(screen.getByRole('combobox', { name: '署名角色' })).toBeEnabled()
    expect(screen.getByRole('tab', { name: '编辑署名' })).toHaveAttribute('aria-selected', 'true')
  })

  it('separates candidate serving from statistics maintenance and allows pending recovery', () => {
    const result = hookResult() as Omit<ReturnType<typeof hookResult>, 'state'> & {
      state: TrackCreditState
    }
    result.state = {
      ...result.state,
      current_revision: 35,
      active_aggregate_revision: 33,
      rebuild_status: 'pending',
      serving_revision: 33,
      target_revision: 35,
      candidate_maintenance_status: 'building',
      statistics_variant_statuses: [{
        merge_level: 2,
        dynamic_threshold: true,
        maintenance_status: 'building',
        freshness: 'last_known_good',
      }],
      retry_allowed: true,
    }
    useTrackCreditsMock.mockReturnValue(result)

    render(<TrackCreditManager initialTrackId={175} />)

    expect(screen.getByText('搜索候选 · 上一版本可用')).toBeInTheDocument()
    expect(screen.getByText('播放统计 · 上一版本可用')).toBeInTheDocument()
    expect(screen.getByText('服务 revision 33 → 目标 35')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '恢复维护' }))
    expect(result.rebuild.mutate).toHaveBeenCalledTimes(1)
  })

  it('keeps the serving candidate version visible when statistics maintenance failed', () => {
    const result = hookResult() as Omit<ReturnType<typeof hookResult>, 'state'> & {
      state: TrackCreditState
    }
    result.state = {
      ...result.state,
      current_revision: 35,
      active_aggregate_revision: 33,
      rebuild_status: 'failed',
      serving_revision: 33,
      target_revision: 35,
      candidate_maintenance_status: 'failed',
      statistics_variant_statuses: [{
        maintenance_status: 'failed',
        freshness: 'last_known_good',
      }],
      retry_allowed: true,
    }
    useTrackCreditsMock.mockReturnValue(result)

    render(<TrackCreditManager initialTrackId={175} />)

    expect(screen.getByText('搜索候选 · 上一版本可用')).toBeInTheDocument()
    expect(screen.getByText('播放统计 · 部分更新失败')).toBeInTheDocument()
    expect(screen.queryByText(result.state.last_error ?? 'internal error')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重试维护' })).toBeInTheDocument()
  })
})
