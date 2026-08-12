import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, renderHook, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { YearlyReviewV2Loading } from '@/features/yearly-review/YearlyReviewStates'
import {
  usePrewarmYearlyReviews,
  useYearlyReviewGenerationStatus,
  useYearlyReviewV2,
} from '@/hooks/useYearlyReviewV2'
import { api } from '@/lib/api'
import type { AnalysisFilters } from '@/types/analysis'
import type {
  YearlyReviewGenerationStatusResponse,
  YearlyReviewGenerationTaskStatus,
} from '@/types/yearly-review-v2'

const filters: AnalysisFilters = {
  min_ms: 30_000,
  music_only: true,
  merge_enabled: true,
  dynamic_threshold: true,
  max_merge_gap_minutes: 30,
  merge_level: 2,
  include_compilations: false,
  bb_top_n: 30,
  bb_album_top_n: 20,
  bb_artist_top_n: 20,
  bb_week_start_dow: 4,
  bb_week_start_hour: 0,
}

function createClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity },
      mutations: { retry: false },
    },
  })
}

function wrapperFor(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}

const runningTask: YearlyReviewGenerationTaskStatus = {
  year: 2024,
  state: 'running',
  requested_at: '2026-08-12T00:00:00.000Z',
  started_at: '2026-08-12T00:00:01.000Z',
  finished_at: null,
  error: null,
}

const runningResponse: YearlyReviewGenerationStatusResponse = {
  protocol_version: 'yearly_review_generation_v1',
  tasks: [runningTask],
}

describe('Yearly Review V2 generation flow', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('keeps elapsed time anchored to the server request after remounting', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-08-12T00:00:02.000Z'))

    const first = render(<YearlyReviewV2Loading year={2024} task={runningTask} />)
    expect(screen.getByText('已等待 2 秒')).toBeInTheDocument()
    first.unmount()

    vi.setSystemTime(new Date('2026-08-12T00:00:08.000Z'))
    render(<YearlyReviewV2Loading year={2024} task={runningTask} />)
    expect(screen.getByText('已等待 8 秒')).toBeInTheDocument()
  })

  it('shows a distinct queued state without starting a local stopwatch', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-08-12T00:00:05.000Z'))
    render(<YearlyReviewV2Loading
      year={2024}
      task={{ ...runningTask, state: 'queued', started_at: null }}
    />)

    expect(screen.getByText('正在等待整理这一年的音乐故事')).toBeInTheDocument()
    expect(screen.getByText('已等待 5 秒')).toBeInTheDocument()
  })

  it('loads generation status with the complete filter context and year set', async () => {
    const getSpy = vi.spyOn(api, 'get').mockResolvedValue(runningResponse)
    const client = createClient()
    const { result } = renderHook(
      () => useYearlyReviewGenerationStatus([2024, 2023, 2024], filters, true),
      { wrapper: wrapperFor(client) },
    )

    await waitFor(() => expect(result.current.tasks).toEqual([runningTask]))
    expect(getSpy).toHaveBeenCalledWith(
      '/yearly-review/generation-status',
      expect.objectContaining({ years: '2023,2024', min_ms: 30_000, merge_level: 2 }),
      undefined,
      expect.any(AbortSignal),
    )
  })

  it('cancels only the report HTTP waiter when its query observer leaves', async () => {
    let reportSignal: AbortSignal | undefined
    vi.spyOn(api, 'get').mockImplementation((_path, _params, _timeout, signal) => {
      reportSignal = signal
      return new Promise(() => undefined)
    })
    const client = createClient()
    const { unmount } = renderHook(() => useYearlyReviewV2(2024, filters, true), {
      wrapper: wrapperFor(client),
    })

    await waitFor(() => expect(reportSignal).toBeDefined())
    expect(reportSignal?.aborted).toBe(false)
    unmount()
    expect(reportSignal?.aborted).toBe(true)
  })

  it('submits one normalized batch and marks the selected year as foreground', async () => {
    const postSpy = vi.spyOn(api, 'postWithParams').mockResolvedValue(runningResponse)
    const client = createClient()
    const { result } = renderHook(() => usePrewarmYearlyReviews(filters), {
      wrapper: wrapperFor(client),
    })

    await act(async () => {
      await result.current.mutateAsync({ years: [2025, 2023, 2024, 2023], foreground_year: 2024 })
    })

    expect(postSpy).toHaveBeenCalledWith(
      '/yearly-review/prewarm',
      { years: [2023, 2024, 2025], foreground_year: 2024 },
      expect.objectContaining({ min_ms: 30_000, bb_top_n: 30 }),
    )
  })
})
