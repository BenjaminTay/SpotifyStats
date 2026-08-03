import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ArtistIdentitySection } from '@/features/settings/components/ArtistIdentitySection'

const { hookMock, previewMutate, createMutate, updateMutate, undoMutate } = vi.hoisted(() => ({
  hookMock: vi.fn(),
  previewMutate: vi.fn(),
  createMutate: vi.fn(),
  updateMutate: vi.fn(),
  undoMutate: vi.fn(),
}))

vi.mock('@/hooks/useArtistIdentities', () => ({ useArtistIdentities: hookMock }))

const candidates = [
  { artist_id: 532, artist_name: 'Jolin Tsai', play_count: 189, first_play_date: '2023-01-01', last_play_date: '2026-07-31', cover_url: null, identity_id: 3, canonical_artist_id: 532, canonical_display_name: 'Jolin Tsai', external_ids: [] },
  { artist_id: 765, artist_name: 'JOLIN', play_count: 111, first_play_date: '2024-01-01', last_play_date: '2026-06-01', cover_url: null, identity_id: 3, canonical_artist_id: 532, canonical_display_name: 'Jolin Tsai', external_ids: [] },
]

function mockHook() {
  hookMock.mockReturnValue({
    overview: { data: { state: { current_revision: 1, active_aggregate_revision: 0, rebuild_status: 'pending', last_error: null }, groups: [{ identity_id: 3, canonical_artist_id: 532, display_artist_id: 532, display_name: 'Jolin Tsai', display_source: 'canonical_artist', revision: 1, members: candidates.map((item, index) => ({ artist_id: item.artist_id, artist_name: item.artist_name, role: index === 0 ? 'canonical' : 'alias', evidence_type: 'legacy_alias', evidence_json: '{}', confidence: 1, cover_url: null })) }] }, isLoading: false },
    candidates,
    candidatesLoading: false,
    events: [{ event_id: 9, identity_id: 3, action: 'set_display', actor: 'local_user', reason: '使用用户选择的名称', revision: 2, undo_of_event_id: null, created_at: '2026-08-03' }],
    preview: { data: null, error: null, isPending: false, mutate: previewMutate, reset: vi.fn() },
    create: { error: null, isPending: false, mutateAsync: createMutate },
    update: { isPending: false, mutateAsync: updateMutate },
    undo: { isPending: false, mutateAsync: undoMutate },
  })
}

describe('ArtistIdentitySection', () => {
  beforeEach(() => { vi.clearAllMocks(); mockHook() })

  it('presents raw ids, evidence context and keeps canonical separate from display name', () => {
    render(<ArtistIdentitySection />)
    fireEvent.click(screen.getByRole('button', { name: /06 · 艺人身份/ }))
    fireEvent.change(screen.getByLabelText('搜索本地艺人'), { target: { value: 'JOLIN' } })
    fireEvent.click(screen.getByRole('button', { name: /Jolin Tsai/ }))
    fireEvent.click(screen.getAllByText('JOLIN')[0].closest('button')!)

    expect(screen.getAllByText(/raw #532/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/raw #765/).length).toBeGreaterThan(0)
    expect(screen.getByLabelText('最终显示名')).toHaveValue('Jolin Tsai')
    expect(screen.getByText(/选择 canonical 只决定身份主键/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '预览全局影响' }))
    expect(previewMutate).toHaveBeenCalledWith({ artist_ids: [532, 765], canonical_artist_id: 532, display_name: 'Jolin Tsai' })
  })

  it('shows saved groups and append-only audit with undo control without a wide table', () => {
    const { container } = render(<ArtistIdentitySection />)
    fireEvent.click(screen.getByRole('button', { name: /06 · 艺人身份/ }))
    fireEvent.click(screen.getByRole('tab', { name: '已合并身份' }))
    expect(screen.getByText('身份组 #3 · canonical raw #532')).toBeInTheDocument()
    expect(screen.getByText('2 个成员')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: '操作记录' }))
    expect(screen.getByText(/set_display · revision 2/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '撤销' })).toBeInTheDocument()
    expect(container.querySelector('table')).toBeNull()
  })
})
