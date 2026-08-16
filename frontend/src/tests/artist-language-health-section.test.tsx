import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ArtistLanguageHealthSection } from '@/features/settings/components/ArtistLanguageHealthSection'

const {
  coverageQueryMock,
  reviewsQueryMock,
  startReviewHookMock,
  startReviewMock,
  useMusicSearchMock,
} = vi.hoisted(() => ({
  coverageQueryMock: vi.fn(),
  reviewsQueryMock: vi.fn(),
  startReviewHookMock: vi.fn(),
  startReviewMock: vi.fn(),
  useMusicSearchMock: vi.fn(),
}))

vi.mock('@/hooks/useArtistLanguageMetadata', () => ({
  useArtistLanguageCoverage: coverageQueryMock,
  useArtistLanguageReviews: reviewsQueryMock,
  useStartArtistLanguageReview: startReviewHookMock,
}))

vi.mock('@/hooks/useAnalysis', () => ({
  useAnalysisFilters: () => ({
    filters: {
      min_ms: 30000,
      music_only: true,
      merge_enabled: true,
      dynamic_threshold: true,
      max_merge_gap_minutes: 45,
    },
    loading: false,
  }),
}))

vi.mock('@/features/music/search/useMusicSearch', () => ({
  useMusicSearchCandidates: useMusicSearchMock,
}))

vi.mock('@/features/settings/components/ArtistLanguageReviewDialog', () => ({
  ArtistLanguageReviewDialog: ({
    open,
    review,
  }: {
    open: boolean
    review: { artist_name: string } | null
  }) => open && review ? <div role="dialog">审核 {review.artist_name}</div> : null,
}))

const openReview = {
  review_id: 12,
  artist_id: 101,
  artist_name: 'Unknown Artist 1',
  suggested_source_id: null,
  play_hours_snapshot: 42.5,
  reason: 'manual_research',
  status: 'open' as const,
  resolution_note: null,
  reviewed_by: null,
  reviewed_at: null,
  created_at: '2026-07-11T00:00:00Z',
  updated_at: '2026-07-11T00:00:00Z',
  source: null,
}

const terminalReview = {
  ...openReview,
  review_id: 13,
  artist_id: 202,
  artist_name: 'Reviewed Artist',
  status: 'approved' as const,
  resolution_note: '官方资料确认常用英语演唱。',
  reviewed_by: 'local_user',
  reviewed_at: '2026-07-11T01:00:00Z',
}

function installMocks() {
  startReviewHookMock.mockReturnValue({
    mutateAsync: startReviewMock,
    isPending: false,
  })
  coverageQueryMock.mockReturnValue({
    data: {
      eligible_hours: 100,
      excluded_unattributed_hours: 0,
      classified_hours: 60,
      unknown_hours: 40,
      classified_pct: 60,
      unknown_pct: 40,
      buckets: [
        { key: 'en', label: '英语', classification: 'single_language', hours: 60, share_pct: 60, artist_count: 4 },
        { key: 'unknown', label: '未知', classification: 'unknown', hours: 40, share_pct: 40, artist_count: 11 },
      ],
      source_hours: { manual: 60 },
      top_missing: Array.from({ length: 11 }, (_, index) => ({
        artist_id: 101 + index,
        artist_name: `Unknown Artist ${index + 1}`,
        hours: 42.5 - index,
      })),
      caveat: '语言统计来自已审核艺人事实。',
    },
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  })
  reviewsQueryMock.mockImplementation((status: string) => ({
    data: {
      items: status === 'open' ? [openReview] : status === 'approved' ? [terminalReview] : [],
      total: status === 'open' ? 93 : status === 'approved' ? 1 : 0,
    },
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  }))
  startReviewMock.mockResolvedValue(openReview)
  useMusicSearchMock.mockReturnValue({
    data: {
      response_version: 'music_search_v2',
      query: 'search',
      normalized_query: 'search',
      snapshot_status: 'ready',
      filter_fingerprint: null,
      kind: 'artist',
      page: 1,
      page_size: 5,
      total: 1,
      total_by_kind: { track: 0, album: 0, artist: 1 },
      tracks: [],
      albums: [],
      artists: [
        {
          kind: 'artist',
          entity_key: 'artist:909',
          label: 'Search Artist',
          subtitle: null,
          href: '/music/artists/Search%20Artist',
          track_id: null,
          artist_id: 909,
          album_name: null,
          artist_name: 'Search Artist',
          cover_url: null,
          match_field: 'label',
          match_quality: 'exact',
        },
      ],
    },
    initialLoading: false,
    updating: false,
    isPlaceholderData: false,
    error: null,
    refetch: vi.fn(),
  })
}

describe('ArtistLanguageHealthSection', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('keeps a compact collapsed summary and limits expanded missing artists to ten', async () => {
    installMocks()
    const user = userEvent.setup()
    render(<ArtistLanguageHealthSection />)

    expect(screen.getByText(/已分类 60%/)).toBeInTheDocument()
    expect(screen.getByText(/未知 40%/)).toBeInTheDocument()
    expect(screen.getByText(/待审核 93/)).toBeInTheDocument()
    expect(screen.queryByText('Unknown Artist 1')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /艺人语言数据/ }))

    const missingArtists = await screen.findByLabelText('Top 未知艺人')
    expect(within(missingArtists).getByText('Unknown Artist 1')).toBeInTheDocument()
    expect(within(missingArtists).getByText('Unknown Artist 10')).toBeInTheDocument()
    expect(within(missingArtists).queryByText('Unknown Artist 11')).not.toBeInTheDocument()
    expect(screen.queryByText(/campaign|AI|批量补全/i)).not.toBeInTheDocument()
  })

  it('starts or reuses a review from a missing artist and opens the dialog', async () => {
    installMocks()
    const user = userEvent.setup()
    render(<ArtistLanguageHealthSection />)

    await user.click(screen.getByRole('button', { name: /艺人语言数据/ }))
    const missingArtists = await screen.findByLabelText('Top 未知艺人')
    await user.click(within(missingArtists).getByRole('button', { name: '审核 Unknown Artist 1' }))

    await waitFor(() => {
      expect(startReviewMock).toHaveBeenCalledWith({ artist_id: 101, reason: 'manual_research' })
    })
    expect(startReviewHookMock).toHaveBeenCalledWith({
      min_ms: 30000,
      music_only: true,
      merge_enabled: true,
      dynamic_threshold: true,
      max_merge_gap_minutes: 45,
    })
    expect(await screen.findByRole('dialog')).toHaveTextContent('审核 Unknown Artist 1')
  })

  it('supports artist search and terminal review history without batch controls', async () => {
    installMocks()
    const user = userEvent.setup()
    render(<ArtistLanguageHealthSection />)

    await user.click(screen.getByRole('button', { name: /艺人语言数据/ }))
    await user.type(screen.getByRole('searchbox', { name: '查找待审核艺人' }), 'Search Artist')
    await waitFor(() => expect(useMusicSearchMock).toHaveBeenLastCalledWith(expect.objectContaining({ eligibility: 'any_local' })))
    await user.click(await screen.findByRole('button', { name: '选择艺人 Search Artist' }))
    await user.click(screen.getByRole('button', { name: '开始审核 Search Artist' }))

    await waitFor(() => {
      expect(startReviewMock).toHaveBeenCalledWith({ artist_id: 909, reason: 'manual_research' })
    })

    const statusSelect = screen.getByRole('combobox', { name: '审核状态' })
    await user.click(statusSelect)
    await user.click(await screen.findByRole('option', { name: '已批准' }))

    const history = await screen.findByLabelText('艺人语言审核记录')
    expect(within(history).getByText('Reviewed Artist')).toBeInTheDocument()
    expect(within(history).getByText(/官方资料确认/)).toBeInTheDocument()
  })
})
