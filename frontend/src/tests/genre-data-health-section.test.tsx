import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'
import { GenreDataHealthSection } from '@/features/settings/components/GenreDataHealthSection'

function createClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity },
      mutations: { retry: false },
    },
  })
}

function renderWithClient(ui: ReactNode) {
  const client = createClient()
  render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
  return client
}

const coveragePayload = {
  known_hours: 3553.2,
  unknown_hours: 492.7,
  known_pct: 87.8,
  unknown_pct: 12.2,
  source_hours: {
    spotify: 2037.2,
    curated_seed: 1210.7,
    llm: 305.3,
  },
  top_missing: [
    { artist_name: 'Conan Gray', hours: 42.5 },
    { artist_name: 'Gracie Abrams', hours: 35.2 },
  ],
  artist_count: 128,
  total_hours: 4045.9,
  excluded_unattributed_hours: 0,
}

const reviewPayload = {
  items: [
    {
      review_id: 1,
      artist_name: 'Lana Del Rey',
      play_hours: 96.4,
      reason: 'llm_artist_genre_suggestion',
      source_id: 11,
      source: 'llm',
      source_key: 'llm:Lana Del Rey',
      source_status: 'suggested',
      genres: ['art pop', 'dream pop'],
      primary_genre: 'art pop',
      language: 'english',
      region: '美国',
      confidence: 0.82,
      evidence_summary: 'Matched official biographies and public metadata.',
      evidence_url: 'https://example.com/lana-del-rey',
      review_status: 'open',
      reviewed_by: null,
      reviewed_at: null,
      resolution_note: null,
      created_at: '2026-07-01T00:00:00Z',
      updated_at: '2026-07-01T00:00:00Z',
    },
  ],
  total: 1,
}

const styleGapPayload = {
  axis: 'style',
  total: 2,
  unknown_hours: 77.7,
  items: [
    {
      artist_name: 'Conan Gray',
      hours: 42.5,
      axis: 'style',
      raw_genres: ['singer-songwriter'],
      raw_source: 'spotify',
      resolved_axes: { role: ['singer-songwriter'] },
      review_id: null,
      review_status: null,
      pre_review_recommendation: null,
    },
    {
      artist_name: 'Gracie Abrams',
      hours: 35.2,
      axis: 'style',
      raw_genres: [],
      raw_source: 'unknown',
      resolved_axes: {},
      review_id: null,
      review_status: null,
      pre_review_recommendation: null,
    },
  ],
}

const taxonomyPayload = {
  raw_genre_count: 230,
  canonical_genre_count: 24,
  noncanonical_passthrough_count: 0,
  unknown_hours: 30.9,
  caveat: '流派统计使用标准化统计标签；Spotify 与本地原始标签保留用于审计。',
  axis_summary: [
    {
      axis: 'style',
      label: '风格',
      hours: 1588.3,
      share_pct: 39.3,
      coverage_pct: 39.3,
      unknown_hours: 2457.6,
      unknown_pct: 60.7,
      canonical_count: 2,
      interpretation: '声音/风格偏好，可作为主要流派分析。',
    },
    {
      axis: 'scene',
      label: '场景',
      hours: 1062.6,
      share_pct: 26.3,
      coverage_pct: 26.3,
      unknown_hours: 2983.3,
      unknown_pct: 73.7,
      canonical_count: 1,
      interpretation: '语言、地区或音乐市场场景，不等同于声音风格。',
    },
    {
      axis: 'role',
      label: '身份',
      hours: 431.3,
      share_pct: 10.7,
      coverage_pct: 10.7,
      unknown_hours: 3614.6,
      unknown_pct: 89.3,
      canonical_count: 1,
      interpretation: '创作或表演身份标签，不等同于声音风格。',
    },
  ],
  top_canonical_genres: [
    {
      name: 'pop',
      axis: 'style',
      label: 'Pop',
      interpretation: '声音/风格偏好，可作为主要流派分析。',
      confidence_tier: 'high',
      hours: 1335.2,
      share_pct: 33.0,
      overall_share_pct: 33.0,
      source_mix: [{ source: 'spotify', hours: 910.4, share_pct: 68.2, confidence: 1, evidence_pct: 100 }],
      top_artists: [],
      dominance_warning: null,
      risk_flags: [],
    },
    {
      name: 'c-pop',
      axis: 'scene',
      label: 'C-Pop',
      interpretation: '语言、地区或音乐市场场景，不等同于声音风格。',
      confidence_tier: 'high',
      hours: 1062.6,
      share_pct: 26.3,
      overall_share_pct: 26.3,
      source_mix: [{ source: 'spotify', hours: 1062.6, share_pct: 100, confidence: 1, evidence_pct: 100 }],
      top_artists: [],
      dominance_warning: null,
      risk_flags: [],
    },
    {
      name: 'singer-songwriter',
      axis: 'role',
      label: 'Singer-Songwriter',
      interpretation: '创作或表演身份标签，不等同于声音风格。',
      confidence_tier: 'medium',
      hours: 431.3,
      share_pct: 10.7,
      overall_share_pct: 10.7,
      source_mix: [{ source: 'curated_seed', hours: 343.4, share_pct: 79.6, confidence: 0.95, evidence_pct: 0 }],
      top_artists: [
        {
          artist_name: 'Taylor Swift',
          hours: 343.4,
          share_pct: 79.6,
          source: 'curated_seed',
          raw_genres: ['pop', 'country pop', 'singer-songwriter'],
        },
      ],
      dominance_warning: 'Taylor Swift contributes 79.6% of this label',
      risk_flags: [
        {
          code: 'single_artist_dominance',
          severity: 'medium',
          message: 'Taylor Swift contributes 79.6% of this label',
        },
      ],
    },
    {
      name: 'electronic/dance',
      axis: 'style',
      label: 'Electronic / Dance',
      interpretation: '声音/风格偏好，可作为主要流派分析。',
      confidence_tier: 'low',
      hours: 66.8,
      share_pct: 1.6,
      overall_share_pct: 1.6,
      source_mix: [{ source: 'llm', hours: 62.6, share_pct: 93.7, confidence: 0.72, evidence_pct: 0 }],
      top_artists: [],
      dominance_warning: null,
      risk_flags: [
        {
          code: 'source_confidence',
          severity: 'high',
          message:
            'LLM 占该标签 93.7%，当前只能按 low 置信度解读',
        },
      ],
    },
  ],
  top_raw_genres: [
    {
      raw_genre: 'mandopop',
      canonical_genres: ['c-pop'],
      hours: 1279.2,
      artist_count: 186,
    },
    {
      raw_genre: 'chinese r&b',
      canonical_genres: ['c-pop', 'r&b/soul'],
      hours: 181.7,
      artist_count: 37,
    },
  ],
  mapping_examples: [
    {
      raw_genre: 'mandopop',
      canonical_genres: ['c-pop'],
      hours: 1279.2,
      artist_count: 186,
    },
    {
      raw_genre: 'chinese r&b',
      canonical_genres: ['c-pop', 'r&b/soul'],
      hours: 181.7,
      artist_count: 37,
    },
  ],
  noncanonical_passthrough: [],
}

function mockArtistGenreApi() {
  const getSpy = vi.spyOn(api, 'get').mockImplementation((path: string) => {
    if (path === '/metadata/artist-genres/coverage') {
      return Promise.resolve(coveragePayload)
    }
    if (path === '/metadata/artist-genres/taxonomy') {
      return Promise.resolve(taxonomyPayload)
    }
    if (path === '/metadata/artist-genres/axis-gaps') {
      return Promise.resolve(styleGapPayload)
    }
    if (path === '/metadata/artist-genres/reviews') {
      return Promise.resolve(reviewPayload)
    }
    if (path === '/ai/tasks/genre-task-1') {
      return Promise.resolve({
        found: true,
        task_id: 'genre-task-1',
        task_type: 'artist_genre_backfill',
        status: 'done',
        stage: 'done',
        progress_pct: 1,
        message: '已生成 1 条建议',
        result: { suggested_count: 1 },
        error: null,
        created_at: '2026-07-04T00:00:00',
        updated_at: '2026-07-04T00:00:01',
      })
    }
    if (path === '/ai/tasks/genre-task-1/events') {
      return Promise.resolve({ found: true, events: [], tool_calls: [] })
    }
    return Promise.reject(new Error(`Unhandled GET ${path}`))
  })

  const postSpy = vi.spyOn(api, 'post').mockImplementation((path: string, body?: unknown) => {
    if (path === '/metadata/artist-genres/reviews/1/approve') {
      return Promise.resolve({
        review_id: 1,
        artist_name: 'Lana Del Rey',
        decision: 'approve',
        source_id: 11,
        source_status: 'approved',
        review_status: 'approved',
      })
    }
    if (path === '/metadata/artist-genres/reviews/1/reject') {
      return Promise.resolve({
        review_id: 1,
        artist_name: 'Lana Del Rey',
        decision: 'reject',
        source_id: 11,
        source_status: 'rejected',
        review_status: 'rejected',
      })
    }
    if (path === '/ai/tasks/metadata/artist-genres') {
      expect(body).toEqual({
        limit: 10,
        min_hours: 8,
        include_ai: true,
        approve_high_confidence_external: true,
      })
      return Promise.resolve({
        task_id: 'genre-task-1',
        status: 'queued',
        stage: 'selecting_artists',
        progress_pct: 0,
        message: '正在选择待补全艺人',
      })
    }
    return Promise.reject(new Error(`Unhandled POST ${path}`))
  })

  return { getSpy, postSpy }
}

describe('GenreDataHealthSection', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows genre coverage, source mix, and missing artists in the overview tab', async () => {
    mockArtistGenreApi()
    renderWithClient(<GenreDataHealthSection />)

    expect(await screen.findByText(/流派与语言数据健康/)).toBeInTheDocument()
    expect(screen.getByText(/艺人语言数据/)).toBeInTheDocument()
    expect((await screen.findAllByText('87.8%')).length).toBeGreaterThan(0)
    expect(screen.getByText('12.2%')).toBeInTheDocument()
    expect(screen.getByText('Spotify')).toBeInTheDocument()
    expect(screen.getByText('人工种子')).toBeInTheDocument()
    expect(screen.getByText('Conan Gray')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '审核' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '分类审计' })).toBeInTheDocument()
  })

  it('shows canonical taxonomy audit without terminal commands', async () => {
    const user = userEvent.setup()
    mockArtistGenreApi()
    renderWithClient(<GenreDataHealthSection />)

    await user.click(await screen.findByRole('tab', { name: '分类审计' }))

    expect(await screen.findByText('统计口径审计')).toBeInTheDocument()
    const auditPanel = screen.getByLabelText('统计口径审计')
    expect(within(auditPanel).getByText('Raw 标签')).toBeInTheDocument()
    expect(within(auditPanel).getByText('230')).toBeInTheDocument()
    expect(within(auditPanel).getByText('Canonical 标签')).toBeInTheDocument()
    expect(within(auditPanel).getByText('24')).toBeInTheDocument()
    expect(within(auditPanel).getByText('非标准透传')).toBeInTheDocument()
    expect(within(auditPanel).getByText('0')).toBeInTheDocument()
    expect(within(auditPanel).getByText('pop')).toBeInTheDocument()
    expect(within(auditPanel).getAllByText('c-pop')).toHaveLength(3)
    expect(within(auditPanel).getAllByText('role').length).toBeGreaterThan(0)
    expect(within(auditPanel).getByText('Singer-Songwriter')).toBeInTheDocument()
    expect(within(auditPanel).getByText('Taylor Swift')).toBeInTheDocument()
    expect(within(auditPanel).getAllByText(/79.6%/).length).toBeGreaterThan(0)
    expect(within(auditPanel).getByText(/curated_seed/)).toBeInTheDocument()
    expect(within(auditPanel).getByText(/Taylor Swift contributes 79.6%/)).toBeInTheDocument()
    expect(within(auditPanel).getByText('mandopop')).toBeInTheDocument()
    expect(within(auditPanel).getByText('chinese r&b')).toBeInTheDocument()
    expect(within(auditPanel).getByText('r&b/soul')).toBeInTheDocument()
    expect(within(auditPanel).getByText(/Spotify 与本地原始标签保留用于审计/)).toBeInTheDocument()
  })

  it('groups canonical genres by axis and shows confidence risks', async () => {
    const user = userEvent.setup()
    mockArtistGenreApi()
    renderWithClient(<GenreDataHealthSection />)

    await user.click(await screen.findByRole('tab', { name: '分类审计' }))

    const auditPanel = await screen.findByLabelText('统计口径审计')
    const styleSection = within(auditPanel).getByLabelText('genre axis 风格')
    const sceneSection = within(auditPanel).getByLabelText('genre axis 场景')
    const roleSection = within(auditPanel).getByLabelText('genre axis 身份')

    expect(within(styleSection).getByText('Pop')).toBeInTheDocument()
    expect(within(styleSection).getByText('Electronic / Dance')).toBeInTheDocument()
    expect(within(styleSection).queryByText('C-Pop')).not.toBeInTheDocument()
    expect(within(sceneSection).getByText('C-Pop')).toBeInTheDocument()
    expect(within(sceneSection).getByText(/不等同于声音风格/)).toBeInTheDocument()
    expect(within(roleSection).getByText('Singer-Songwriter')).toBeInTheDocument()
    expect(within(roleSection).getByText(/Taylor Swift contributes 79.6%/)).toBeInTheDocument()
    expect(within(styleSection).getByText(/当前只能按 low 置信度解读/)).toBeInTheDocument()
    expect(within(styleSection).getByText('低可信')).toBeInTheDocument()
  })

  it('approves and rejects review suggestions from the UI', async () => {
    const { postSpy } = mockArtistGenreApi()
    const user = userEvent.setup()
    renderWithClient(<GenreDataHealthSection />)

    await user.click(await screen.findByRole('tab', { name: '审核' }))

    const reviewRow = await screen.findByLabelText('审核 Lana Del Rey 的 genre 建议')

    await user.click(within(reviewRow).getByRole('button', { name: '通过 Lana Del Rey 的 genre 建议' }))
    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/metadata/artist-genres/reviews/1/approve', {
        resolution_note: '已在 Settings 核对标签与证据后批准。',
      })
    })

    await user.click(within(reviewRow).getByRole('button', { name: '拒绝 Lana Del Rey 的 genre 建议' }))
    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/metadata/artist-genres/reviews/1/reject', {
        resolution_note: '已在 Settings 核对后拒绝该建议。',
      })
    })
  })

  it('starts a small artist genre backfill task', async () => {
    const { postSpy } = mockArtistGenreApi()
    const user = userEvent.setup()
    renderWithClient(<GenreDataHealthSection />)

    await user.click(await screen.findByRole('button', { name: '小批量补全 genre' }))

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/ai/tasks/metadata/artist-genres', {
        limit: 10,
        min_hours: 8,
        include_ai: true,
        approve_high_confidence_external: true,
      })
    })
    expect(await screen.findByText('AI 任务进度')).toBeInTheDocument()
  })
})
