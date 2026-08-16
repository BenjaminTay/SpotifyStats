import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { apiClient } from '@/api/client'
import { ArtistLanguageReviewDialog } from '@/features/settings/components/ArtistLanguageReviewDialog'
import type { ArtistLanguageReviewItem } from '@/types/artist-language-metadata'

const { decideMock, saveSourceMock, useMusicSearchMock } = vi.hoisted(() => ({
  decideMock: vi.fn(),
  saveSourceMock: vi.fn(),
  useMusicSearchMock: vi.fn(),
}))

vi.mock('@/hooks/useArtistLanguageMetadata', () => ({
  useSaveArtistLanguageSource: () => ({ mutateAsync: saveSourceMock, isPending: false }),
  useDecideArtistLanguageReview: () => ({ mutateAsync: decideMock, isPending: false }),
}))

vi.mock('@/hooks/useAnalysis', () => ({
  useAnalysisFilters: () => ({
    filters: {
      min_ms: 30000,
      music_only: true,
      merge_enabled: true,
      dynamic_threshold: true,
      max_merge_gap_minutes: 5,
      merge_level: 2,
      include_compilations: false,
    },
    loading: false,
  }),
}))

vi.mock('@/features/music/search/useMusicSearch', () => ({
  useMusicSearchCandidates: useMusicSearchMock,
}))

const review: ArtistLanguageReviewItem = {
  review_id: 12,
  artist_id: 101,
  artist_name: 'Lana Del Rey',
  suggested_source_id: null,
  play_hours_snapshot: 42.5,
  reason: 'manual_research',
  status: 'open',
  resolution_note: null,
  reviewed_by: null,
  reviewed_at: null,
  created_at: '2026-07-11T00:00:00Z',
  updated_at: '2026-07-11T00:00:00Z',
  source: null,
}

function installSearchMock() {
  useMusicSearchMock.mockReturnValue({
    data: {
      response_version: 'music_search_v2',
      query: 'Video Games',
      normalized_query: 'video games',
      snapshot_status: 'ready',
      filter_fingerprint: null,
      kind: 'track',
      page: 1,
      page_size: 5,
      total: 1,
      total_by_kind: { track: 1, album: 0, artist: 0 },
      tracks: [
        {
          entity_key: 'track:77',
          kind: 'track',
          label: 'Video Games',
          subtitle: 'Lana Del Rey',
          href: '/music/tracks/77',
          track_id: 77,
          artist_id: 101,
          album_name: 'Born to Die',
          artist_name: 'Lana Del Rey',
          cover_url: null,
          match_field: 'label',
          match_quality: 'exact',
        },
      ],
      albums: [],
      artists: [],
    },
    initialLoading: false,
    updating: false,
    isPlaceholderData: false,
    error: null,
    refetch: vi.fn(),
  })
}

async function chooseOption(user: ReturnType<typeof userEvent.setup>, label: string, option: string) {
  await user.click(screen.getByRole('combobox', { name: label }))
  await user.click(await screen.findByRole('option', { name: option }))
}

async function fillEvidence(
  user: ReturnType<typeof userEvent.setup>,
  index = 1,
  languageCode = 'zh',
  languageVariant = 'mandarin',
) {
  const evidence = screen.getByLabelText(`证据 ${index}`)
  await user.type(within(evidence).getByLabelText('证据 URL'), 'https://www.lanadelrey.com/about')
  await user.type(within(evidence).getByLabelText('证据标题'), 'Official artist biography')
  await user.type(within(evidence).getByLabelText('证据摘要'), '官方资料说明其主要以普通话演唱。')
  await user.type(within(evidence).getByLabelText('语言代码'), languageCode)
  if (languageVariant) {
    await user.type(within(evidence).getByLabelText(`证据语言变体 ${index}`), languageVariant)
  }
}

describe('ArtistLanguageReviewDialog', () => {
  afterEach(() => {
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it('builds a single-language source with variant, track attribution, and multiple evidence rows', async () => {
    installSearchMock()
    saveSourceMock.mockResolvedValue({ source_id: 33 })
    decideMock.mockResolvedValue({ review_status: 'approved' })
    const onOpenChange = vi.fn()
    const user = userEvent.setup()
    render(<ArtistLanguageReviewDialog open review={review} onOpenChange={onOpenChange} />)

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '批准审核' })).toBeDisabled()
    await user.type(screen.getByLabelText('主要语言代码'), 'zh')
    await user.type(screen.getByLabelText('语言变体'), 'mandarin')
    await user.type(screen.getByLabelText('审核说明'), '官方资料与作品信息一致。')
    await fillEvidence(user)

    await user.type(screen.getByRole('searchbox', { name: '查找证据曲目 1' }), 'Video Games')
    await user.click(await screen.findByRole('button', { name: '选择曲目 Video Games' }))
    expect(screen.getByText(/本地曲目 #77/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '添加证据' }))
    expect(screen.getByLabelText('证据 2')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '移除证据 2' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '添加证据' })).toHaveAttribute('title')

    await user.click(screen.getByRole('button', { name: '批准审核' }))

    await waitFor(() => {
      expect(saveSourceMock).toHaveBeenCalledWith(expect.objectContaining({
        classification: 'single_language',
        primary_language_code: 'zh',
        language_variant: 'mandarin',
        evidence: [expect.objectContaining({
          local_track_id: 77,
          claimed_language_code: 'zh',
          claimed_language_variant: 'mandarin',
        })],
      }))
      expect(decideMock).toHaveBeenCalledWith({
        action: 'approve',
        resolution_note: '官方资料与作品信息一致。',
      })
    })
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('switches classification fields and supports multilingual or instrumental evidence shapes', async () => {
    installSearchMock()
    const user = userEvent.setup()
    render(<ArtistLanguageReviewDialog open review={review} onOpenChange={vi.fn()} />)

    await chooseOption(user, '语言分类', '多语言')
    expect(screen.queryByLabelText('主要语言代码')).not.toBeInTheDocument()
    expect(screen.getByLabelText('语言代码')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '添加证据' }))
    expect(screen.getAllByLabelText('语言代码')).toHaveLength(2)

    await chooseOption(user, '语言分类', '器乐为主')
    expect(screen.queryByLabelText('主要语言代码')).not.toBeInTheDocument()
    expect(screen.queryAllByLabelText('语言代码')).toHaveLength(0)
  })

  it('saves a minimal candidate before rejecting a new review without a source', async () => {
    installSearchMock()
    saveSourceMock.mockResolvedValue({ source_id: 33 })
    decideMock.mockResolvedValue({ review_status: 'rejected' })
    const user = userEvent.setup()
    render(<ArtistLanguageReviewDialog open review={review} onOpenChange={vi.fn()} />)

    await user.type(screen.getByLabelText('审核说明'), '当前来源不能支持艺人级结论。')
    expect(screen.getByRole('button', { name: '拒绝候选' })).toBeDisabled()

    await user.type(screen.getByLabelText('主要语言代码'), 'zh')
    await user.click(screen.getByRole('button', { name: '拒绝候选' }))
    await waitFor(() => {
      expect(saveSourceMock).toHaveBeenCalledWith({
        classification: 'single_language',
        primary_language_code: 'zh',
        language_variant: null,
        evidence: [],
      })
      expect(decideMock).toHaveBeenCalledWith({
        action: 'reject',
        resolution_note: '当前来源不能支持艺人级结论。',
      })
    })
    expect(saveSourceMock.mock.invocationCallOrder[0]).toBeLessThan(
      decideMock.mock.invocationCallOrder[0],
    )
  })

  it('rejects an existing suggested source directly and keeps insufficient-evidence source-optional', async () => {
    installSearchMock()
    decideMock.mockResolvedValue({ review_status: 'rejected' })
    const user = userEvent.setup()
    const reviewWithSource: ArtistLanguageReviewItem = {
      ...review,
      suggested_source_id: 33,
      source: {
        source_id: 33,
        artist_id: review.artist_id,
        classification: 'single_language',
        primary_language_code: 'zh',
        language_variant: 'mandarin',
        raw_language: null,
        origin: 'manual',
        source_key: 'manual:33',
        status: 'suggested',
        replaces_source_id: null,
        created_at: review.created_at,
        updated_at: review.updated_at,
        evidence: [],
      },
    }
    const { rerender } = render(
      <ArtistLanguageReviewDialog open review={reviewWithSource} onOpenChange={vi.fn()} />,
    )

    await user.type(screen.getByLabelText('审核说明'), '当前候选分类不准确。')
    await user.click(screen.getByRole('button', { name: '拒绝候选' }))
    await waitFor(() => {
      expect(decideMock).toHaveBeenCalledWith({
        action: 'reject',
        resolution_note: '当前候选分类不准确。',
      })
    })
    expect(saveSourceMock).not.toHaveBeenCalled()

    decideMock.mockClear()
    rerender(<ArtistLanguageReviewDialog open review={{ ...review, review_id: 13 }} onOpenChange={vi.fn()} />)
    await user.clear(screen.getByLabelText('审核说明'))
    await user.type(screen.getByLabelText('审核说明'), '需要更多权威资料。')
    await user.click(screen.getByRole('button', { name: '证据不足' }))
    await waitFor(() => {
      expect(decideMock).toHaveBeenCalledWith({
        action: 'insufficient_evidence',
        resolution_note: '需要更多权威资料。',
      })
    })
  })

  it('shows a readable structured 422 and keeps closing mutation-free', async () => {
    installSearchMock()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: {
        code: 'artist_language_validation_error',
        message: '多语言至少需要两个不同的艺人级演唱主张',
      },
    }), {
      status: 422,
      headers: { 'Content-Type': 'application/json' },
    })))
    saveSourceMock.mockImplementation((source: unknown) =>
      apiClient.put('/metadata/artist-languages/reviews/12/source', source),
    )
    const onOpenChange = vi.fn()
    const user = userEvent.setup()
    render(<ArtistLanguageReviewDialog open review={review} onOpenChange={onOpenChange} />)

    await user.type(screen.getByLabelText('主要语言代码'), 'zh')
    await user.type(screen.getByLabelText('审核说明'), '测试审核说明。')
    await fillEvidence(user)
    await user.click(screen.getByRole('button', { name: '批准审核' }))

    expect(await screen.findByText('多语言至少需要两个不同的艺人级演唱主张')).toBeInTheDocument()
    expect(decideMock).not.toHaveBeenCalled()

    saveSourceMock.mockClear()
    decideMock.mockClear()
    await user.click(screen.getByRole('button', { name: '关闭' }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(saveSourceMock).not.toHaveBeenCalled()
    expect(decideMock).not.toHaveBeenCalled()
  })

  it('renders terminal replacement and evidence audit details as read-only', () => {
    installSearchMock()
    const terminal: ArtistLanguageReviewItem = {
      ...review,
      status: 'approved',
      resolution_note: '已核对官方艺人资料。',
      reviewed_by: 'local_user',
      reviewed_at: '2026-07-11T02:00:00Z',
      suggested_source_id: 33,
      source: {
        source_id: 33,
        artist_id: 101,
        classification: 'single_language',
        primary_language_code: 'en',
        language_variant: null,
        raw_language: null,
        origin: 'manual',
        source_key: 'manual:33',
        status: 'approved',
        replaces_source_id: 21,
        created_at: '2026-07-11T01:00:00Z',
        updated_at: '2026-07-11T02:00:00Z',
        evidence: [{
          evidence_id: 44,
          source_id: 33,
          local_track_id: null,
          claimed_language_code: 'en',
          claimed_language_variant: null,
          evidence_kind: 'artist_profile',
          performer_attribution: 'artist_vocal_confirmed',
          evidence_url: 'https://www.lanadelrey.com/about',
          evidence_title: 'Official artist biography',
          evidence_accessed_at: '2026-07-11T01:00:00Z',
          evidence_summary: '官方资料说明其主要以英语演唱。',
          created_at: '2026-07-11T01:00:00Z',
        }],
      },
    }

    render(<ArtistLanguageReviewDialog open review={terminal} onOpenChange={vi.fn()} />)

    expect(screen.getByText(/替换来源 #21/)).toBeInTheDocument()
    expect(screen.getByText('Official artist biography')).toBeInTheDocument()
    expect(screen.getByText('已核对官方艺人资料。')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '批准审核' })).not.toBeInTheDocument()
  })
})
