import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AiInsightsExperience } from '@/features/ai-insights/AiInsightsExperience'
import { api } from '@/lib/api'

type MockSettings = {
  llm_enabled: boolean
  has_llm_key: boolean
  min_ms: number
  music_only: boolean
  merge_enabled: boolean
  dynamic_threshold?: boolean
}

const settingsState = vi.hoisted((): { settings: MockSettings } => ({
  settings: {
    llm_enabled: true,
    has_llm_key: true,
    min_ms: 30000,
    music_only: true,
    merge_enabled: true,
  },
}))

vi.mock('@/hooks/useSettings', () => ({
  useSettings: () => ({
    settings: settingsState.settings,
    loading: false,
    error: null,
    refetch: vi.fn(),
  }),
}))

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
    return (
      <MemoryRouter>
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      </MemoryRouter>
    )
  }
}

function mockCommonGet(taskReport = '生成后的周报') {
  return vi.spyOn(api, 'get').mockImplementation((path: string) => {
    if (path === '/analysis/stats') {
      return Promise.resolve({
        period: { start_date: '2026-01-01', end_date: '2026-06-23' },
      })
    }
    if (path === '/chat/sessions') {
      return Promise.resolve({ success: true, data: [] })
    }
    if (path === '/ai/tasks/task-generate') {
      return Promise.resolve({
        found: true,
        task_id: 'task-generate',
        task_type: 'ai_report_weekly',
        status: 'done',
        stage: 'done',
        progress_pct: 1,
        message: '报告生成完成',
        result: {
          success: true,
          report: taskReport,
          cached: false,
          cached_at: null,
          entities: { artists: [], tracks: [] },
        },
        error: null,
        created_at: '2026-06-28T00:00:00',
        updated_at: '2026-06-28T00:00:01',
      })
    }
    if (path === '/ai/tasks/task-generate/events') {
      return Promise.resolve({ found: true, events: [], tool_calls: [] })
    }
    return Promise.reject(new Error(`unexpected GET ${path}`))
  })
}

function calledLegacyReportEndpoint(getSpy: ReturnType<typeof mockCommonGet>): boolean {
  return getSpy.mock.calls.some(([path]) => {
    const value = String(path)
    return value === '/ai-insights/weekly-digest'
      || value === '/ai-insights/monthly-personality'
      || value === '/ai-insights/yearly-story'
  })
}

describe('AiInsightsExperience report task flow', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.setSystemTime(new Date('2026-06-28T12:00:00'))
    settingsState.settings = {
      llm_enabled: true,
      has_llm_key: true,
      min_ms: 30000,
      music_only: true,
      merge_enabled: true,
    }
    localStorage.clear()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('checks cache once on load and starts generation only after clicking generate', async () => {
    const client = createClient()
    const getSpy = mockCommonGet()
    const postSpy = vi.spyOn(api, 'post').mockImplementation((path: string, body?: unknown) => {
      if (path !== '/ai/tasks/report') {
        return Promise.reject(new Error(`unexpected POST ${path}`))
      }
      const payload = body as { action?: string }
      if (payload.action === 'cache_only') {
        return Promise.resolve({
          task_id: 'task-cache',
          status: 'done',
          stage: 'done',
          progress_pct: 1,
          message: '缓存检查完成',
          result: {
            cached: false,
            report: null,
            cached_at: null,
            entities: null,
            needs_generation: true,
          },
        })
      }
      if (payload.action === 'generate') {
        return Promise.resolve({
          task_id: 'task-generate',
          status: 'queued',
          stage: 'checking_cache',
          progress_pct: 0,
          message: '准备生成 AI 报告',
          result: null,
        })
      }
      return Promise.reject(new Error(`unexpected action ${payload.action}`))
    })

    render(<AiInsightsExperience />, { wrapper: wrapperFor(client) })

    await screen.findByRole('button', { name: '生成报告' })
    expect(screen.queryByText('该时间段暂无听歌数据')).not.toBeInTheDocument()
    expect(postSpy).toHaveBeenCalledTimes(1)
    expect(postSpy).toHaveBeenLastCalledWith('/ai/tasks/report', {
      report_type: 'weekly',
      action: 'cache_only',
      week_start: '2026-06-17',
      week_end: '2026-06-23',
      min_ms: 30000,
      music_only: true,
      merge_enabled: true,
      dynamic_threshold: true,
      max_merge_gap_minutes: null,
    })
    expect(calledLegacyReportEndpoint(getSpy)).toBe(false)

    fireEvent.click(screen.getByRole('button', { name: '生成报告' }))

    await waitFor(() => expect(postSpy).toHaveBeenCalledTimes(2))
    expect(postSpy).toHaveBeenLastCalledWith('/ai/tasks/report', {
      report_type: 'weekly',
      action: 'generate',
      force: true,
      week_start: '2026-06-17',
      week_end: '2026-06-23',
      min_ms: 30000,
      music_only: true,
      merge_enabled: true,
      dynamic_threshold: true,
      max_merge_gap_minutes: null,
    })
    expect(getSpy).toHaveBeenCalledWith('/ai/tasks/task-generate')
    expect(await screen.findByText('生成后的周报')).toBeInTheDocument()
    expect(calledLegacyReportEndpoint(getSpy)).toBe(false)
  })

  it('renders cached report directly without showing the manual generate action', async () => {
    const client = createClient()
    mockCommonGet()
    vi.spyOn(api, 'post').mockResolvedValue({
      task_id: 'task-cache-hit',
      status: 'done',
      stage: 'done',
      progress_pct: 1,
      message: '缓存检查完成',
      result: {
        cached: true,
        report: '缓存命中的周报',
        cached_at: '2026-06-28T00:00:00',
        entities: { artists: [], tracks: [] },
        needs_generation: false,
      },
    })

    render(<AiInsightsExperience />, { wrapper: wrapperFor(client) })

    expect(await screen.findByText('缓存命中的周报')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '生成报告' })).not.toBeInTheDocument()
  })

  it('refreshes an existing cached report with a forced generate task', async () => {
    const client = createClient()
    mockCommonGet('刷新后的周报')
    const postSpy = vi.spyOn(api, 'post').mockImplementation((path: string, body?: unknown) => {
      if (path !== '/ai/tasks/report') {
        return Promise.reject(new Error(`unexpected POST ${path}`))
      }
      const payload = body as { action?: string }
      if (payload.action === 'cache_only') {
        return Promise.resolve({
          task_id: 'task-cache-hit',
          status: 'done',
          stage: 'done',
          progress_pct: 1,
          message: '缓存检查完成',
          result: {
            cached: true,
            report: '缓存命中的周报',
            cached_at: '2026-06-28T00:00:00',
            entities: { artists: [], tracks: [] },
            needs_generation: false,
          },
        })
      }
      if (payload.action === 'generate') {
        return Promise.resolve({
          task_id: 'task-generate',
          status: 'queued',
          stage: 'checking_cache',
          progress_pct: 0,
          message: '准备生成 AI 报告',
          result: null,
        })
      }
      return Promise.reject(new Error(`unexpected action ${payload.action}`))
    })

    render(<AiInsightsExperience />, { wrapper: wrapperFor(client) })

    expect(await screen.findByText('缓存命中的周报')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '刷新报告' }))

    await waitFor(() => expect(postSpy).toHaveBeenCalledTimes(2))
    expect(postSpy).toHaveBeenLastCalledWith('/ai/tasks/report', {
      report_type: 'weekly',
      action: 'generate',
      force: true,
      week_start: '2026-06-17',
      week_end: '2026-06-23',
      min_ms: 30000,
      music_only: true,
      merge_enabled: true,
      dynamic_threshold: true,
      max_merge_gap_minutes: null,
    })
    expect(await screen.findByText('刷新后的周报')).toBeInTheDocument()
  })

  it('cancels an in-flight report generation task', async () => {
    const client = createClient()
    const getSpy = vi.spyOn(api, 'get').mockImplementation((path: string) => {
      if (path === '/analysis/stats') {
        return Promise.resolve({
          period: { start_date: '2026-01-01', end_date: '2026-06-23' },
        })
      }
      if (path === '/chat/sessions') {
        return Promise.resolve({ success: true, data: [] })
      }
      if (path === '/ai/tasks/task-generate') {
        return Promise.resolve({
          found: true,
          task_id: 'task-generate',
          task_type: 'ai_report_weekly',
          status: 'running',
          stage: 'calling_llm',
          progress_pct: 0.7,
          message: '正在调用 LLM 生成报告',
          result: null,
          error: null,
          created_at: '2026-06-28T00:00:00',
          updated_at: '2026-06-28T00:00:01',
        })
      }
      if (path === '/ai/tasks/task-generate/events') {
        return Promise.resolve({
          found: true,
          events: [{
            event_id: 1,
            task_id: 'task-generate',
            event_type: 'stage_started',
            stage: 'calling_llm',
            message: '正在调用 LLM 生成报告',
            payload: null,
            created_at: '2026-06-28T00:00:00',
          }],
          tool_calls: [],
        })
      }
      return Promise.reject(new Error(`unexpected GET ${path}`))
    })
    const postSpy = vi.spyOn(api, 'post').mockImplementation((path: string, body?: unknown) => {
      if (path === '/ai/tasks/task-generate/cancel') {
        return Promise.resolve({
          found: true,
          task_id: 'task-generate',
          task_type: 'ai_report_weekly',
          status: 'cancelled',
          stage: 'cancelled',
          progress_pct: 0.35,
          message: '任务已取消',
          result: null,
          error: null,
        })
      }
      if (path !== '/ai/tasks/report') {
        return Promise.reject(new Error(`unexpected POST ${path}`))
      }
      const payload = body as { action?: string }
      if (payload.action === 'cache_only') {
        return Promise.resolve({
          task_id: 'task-cache',
          status: 'done',
          stage: 'done',
          progress_pct: 1,
          message: '缓存检查完成',
          result: {
            cached: false,
            report: null,
            cached_at: null,
            entities: null,
            needs_generation: true,
          },
        })
      }
      return Promise.resolve({
        task_id: 'task-generate',
        status: 'queued',
        stage: 'checking_cache',
        progress_pct: 0,
        message: '准备生成 AI 报告',
        result: null,
      })
    })

    render(<AiInsightsExperience />, { wrapper: wrapperFor(client) })

    fireEvent.click(await screen.findByRole('button', { name: '生成报告' }))
    const cancelButton = await screen.findByRole('button', { name: '取消' })
    fireEvent.click(cancelButton)

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/ai/tasks/task-generate/cancel')
    })
    expect(await screen.findByText('报告生成已取消')).toBeInTheDocument()
    expect(calledLegacyReportEndpoint(getSpy)).toBe(false)
  })

  it('uses settings dynamic_threshold=false for cache-only report payload', async () => {
    settingsState.settings = {
      ...settingsState.settings,
      dynamic_threshold: false,
    }
    const client = createClient()
    mockCommonGet()
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
      task_id: 'task-cache',
      status: 'done',
      stage: 'done',
      progress_pct: 1,
      message: '缓存检查完成',
      result: {
        cached: false,
        report: null,
        cached_at: null,
        entities: null,
        needs_generation: true,
      },
    })

    render(<AiInsightsExperience />, { wrapper: wrapperFor(client) })

    await screen.findByRole('button', { name: '生成报告' })
    expect(postSpy).toHaveBeenCalledTimes(1)
    expect(postSpy).toHaveBeenLastCalledWith('/ai/tasks/report', expect.objectContaining({
      action: 'cache_only',
      dynamic_threshold: false,
    }))
  })

  it.each(['false', '0'])(
    'falls back to localStorage dynamic threshold %s for cache-only report payload',
    async (storedValue) => {
      localStorage.setItem('spotify_stats_dynamic_threshold', storedValue)
      const client = createClient()
      mockCommonGet()
      const postSpy = vi.spyOn(api, 'post').mockResolvedValue({
        task_id: 'task-cache',
        status: 'done',
        stage: 'done',
        progress_pct: 1,
        message: '缓存检查完成',
        result: {
          cached: false,
          report: null,
          cached_at: null,
          entities: null,
          needs_generation: true,
        },
      })

      render(<AiInsightsExperience />, { wrapper: wrapperFor(client) })

      await screen.findByRole('button', { name: '生成报告' })
      expect(postSpy).toHaveBeenCalledTimes(1)
      expect(postSpy).toHaveBeenLastCalledWith('/ai/tasks/report', expect.objectContaining({
        action: 'cache_only',
        dynamic_threshold: false,
      }))
    },
  )

  it('retries a failed cache-only check without starting generation', async () => {
    const client = createClient()
    mockCommonGet()
    const actions: string[] = []
    const postSpy = vi.spyOn(api, 'post').mockImplementation((path: string, body?: unknown) => {
      if (path !== '/ai/tasks/report') {
        return Promise.reject(new Error(`unexpected POST ${path}`))
      }
      const payload = body as { action?: string }
      actions.push(payload.action ?? 'missing')
      if (payload.action === 'cache_only' && actions.length === 1) {
        return Promise.reject(new Error('cache check failed'))
      }
      if (payload.action === 'cache_only') {
        return Promise.resolve({
          task_id: 'task-cache-retry',
          status: 'done',
          stage: 'done',
          progress_pct: 1,
          message: '缓存检查完成',
          result: {
            cached: false,
            report: null,
            cached_at: null,
            entities: null,
            needs_generation: true,
          },
        })
      }
      return Promise.reject(new Error('generate should not run during cache retry'))
    })

    render(<AiInsightsExperience />, { wrapper: wrapperFor(client) })

    expect(await screen.findByText('cache check failed')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '重试' }))

    await waitFor(() => expect(postSpy).toHaveBeenCalledTimes(2))
    expect(await screen.findByRole('button', { name: '生成报告' })).toBeInTheDocument()
    expect(actions).toEqual(['cache_only', 'cache_only'])
    expect(actions).not.toContain('generate')
  })

  it('keeps the LLM not configured state without requesting report tasks', async () => {
    settingsState.settings = {
      ...settingsState.settings,
      llm_enabled: false,
      has_llm_key: false,
    }
    const client = createClient()
    mockCommonGet()
    const postSpy = vi.spyOn(api, 'post').mockResolvedValue({})

    render(<AiInsightsExperience />, { wrapper: wrapperFor(client) })

    expect(await screen.findByText('AI 功能尚未配置')).toBeInTheDocument()
    await vi.advanceTimersByTimeAsync(100)
    expect(postSpy.mock.calls.some(([path]) => path === '/ai/tasks/report')).toBe(false)
  })

  it('rechecks cache when report type or selected range changes', async () => {
    const client = createClient()
    mockCommonGet()
    const postSpy = vi.spyOn(api, 'post').mockImplementation((path: string) => {
      if (path !== '/ai/tasks/report') {
        return Promise.reject(new Error(`unexpected POST ${path}`))
      }
      return Promise.resolve({
        task_id: `task-cache-${postSpy.mock.calls.length}`,
        status: 'done',
        stage: 'done',
        progress_pct: 1,
        message: '缓存检查完成',
        result: {
          cached: false,
          report: null,
          cached_at: null,
          entities: null,
          needs_generation: true,
        },
      })
    })

    render(<AiInsightsExperience />, { wrapper: wrapperFor(client) })

    await screen.findByRole('button', { name: '生成报告' })
    expect(postSpy).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('button', { name: '月报' }))
    await waitFor(() => expect(postSpy).toHaveBeenCalledTimes(2))
    expect(postSpy).toHaveBeenLastCalledWith('/ai/tasks/report', {
      report_type: 'monthly',
      action: 'cache_only',
      month: '2026-06',
      year: 2026,
      min_ms: 30000,
      music_only: true,
      merge_enabled: true,
      dynamic_threshold: true,
      max_merge_gap_minutes: null,
    })

    fireEvent.click(screen.getByRole('button', { name: '上月' }))
    await waitFor(() => expect(postSpy).toHaveBeenCalledTimes(3))
    expect(postSpy).toHaveBeenLastCalledWith('/ai/tasks/report', {
      report_type: 'monthly',
      action: 'cache_only',
      month: '2026-05',
      year: 2026,
      min_ms: 30000,
      music_only: true,
      merge_enabled: true,
      dynamic_threshold: true,
      max_merge_gap_minutes: null,
    })
  })
})
