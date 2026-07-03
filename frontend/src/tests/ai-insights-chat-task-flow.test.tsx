import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ChatInterface } from '@/features/ai-insights/ChatInterface'
import { api } from '@/lib/api'

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

async function advanceTimers(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

function mockChatSessionGets(taskResponses: unknown[]) {
  return vi.spyOn(api, 'get').mockImplementation((path: string) => {
    if (path === '/ai-insights/suggested-questions') {
      return Promise.resolve({ questions: [] })
    }
    if (path === '/settings') {
      return Promise.resolve({
        spotify_profile: null,
        min_ms: 45000,
        music_only: false,
        merge_enabled: false,
        dynamic_threshold: false,
        max_merge_gap_minutes: 45,
        bb_top_n: 30,
        bb_album_top_n: 20,
        bb_artist_top_n: 20,
        bb_week_start_dow: 4,
        bb_week_start_hour: 0,
        include_compilations: false,
        db_record_count: 0,
        account_data_imported: false,
        spotify_connected: false,
        llm_enabled: true,
        llm_provider: 'openai',
        llm_model: 'gpt-test',
        has_llm_key: true,
        llm_active_profile_id: null,
        llm_active_profile_name: null,
        rebuild_pending: false,
      })
    }
    if (path === '/chat/sessions/7') {
      return Promise.resolve({
        success: true,
        data: {
          id: 7,
          title: '已有对话',
          created_at: '2026-06-28T00:00:00',
          updated_at: '2026-06-28T00:00:00',
          message_count: 0,
          messages: [],
        },
      })
    }
    if (path === '/ai/tasks/chat-task-1') {
      return Promise.resolve(taskResponses.shift() ?? taskResponses.at(-1))
    }
    if (path === '/ai/tasks/chat-task-1/events') {
      return Promise.resolve({
        found: true,
        events: [
          {
            event_id: 1,
            task_id: 'chat-task-1',
            event_type: 'stage_started',
            stage: 'querying_tools',
            message: '正在查询你的年度播放数据',
            payload: null,
            created_at: '2026-06-28T00:00:01',
          },
        ],
        tool_calls: [
          {
            tool_call_id: 1,
            task_id: 'chat-task-1',
            tool_name: 'analysis_charts',
            status: 'done',
            params_summary: '2026 artist plays top 10',
            result_summary: 'Artist A ranked #1',
            source_range: '2026-01-01 to 2026-06-28',
            error: null,
            started_at: '2026-06-28T00:00:01',
            completed_at: '2026-06-28T00:00:02',
          },
        ],
      })
    }
    return Promise.reject(new Error(`unexpected GET ${path}`))
  })
}

function mockChatPosts() {
  return vi.spyOn(api, 'post').mockImplementation((path: string, body?: unknown) => {
    if (path === '/chat/sessions/7/messages') {
      return Promise.resolve({ success: true, data: { id: 1, ...(body as object) } })
    }
    if (path === '/ai/tasks/chat') {
      return Promise.resolve({
        task_id: 'chat-task-1',
        status: 'queued',
        stage: 'planning_tools',
        progress_pct: 0,
        message: '正在规划可用数据工具',
        result: null,
      })
    }
    return Promise.reject(new Error(`unexpected POST ${path}`))
  })
}

function renderChat() {
  const client = createClient()
  render(
    <ChatInterface
      sessionId={7}
      onSessionCreated={() => {}}
    />,
    { wrapper: wrapperFor(client) },
  )
}

describe('ChatInterface task-based agent flow', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.setSystemTime(new Date('2026-07-02T08:43:01.554Z'))
    Element.prototype.scrollIntoView = vi.fn()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('starts chat through /ai/tasks/chat and renders running progress with tool trace', async () => {
    mockChatSessionGets([
      {
        found: true,
        task_id: 'chat-task-1',
        task_type: 'ai_chat_agent',
        status: 'running',
        stage: 'querying_tools',
        progress_pct: 0.5,
        message: '正在查询你的年度播放数据',
        result: null,
        error: null,
        created_at: '2026-06-28T00:00:00',
        updated_at: '2026-06-28T00:00:01',
      },
    ])
    const postSpy = mockChatPosts()

    renderChat()
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/chat/sessions/7'))

    fireEvent.change(screen.getByPlaceholderText('输入问题，如「我今年听最多的艺人是谁？」'), {
      target: { value: '我今年听最多的艺人是谁？' },
    })
    fireEvent.click(screen.getByRole('button', { name: '发送问题' }))

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/ai/tasks/chat', expect.objectContaining({
        question: '我今年听最多的艺人是谁？',
        conversation_history: [],
        question_time: expect.any(String),
        timezone: expect.any(String),
        thinking_mode: false,
        min_ms: 45000,
        music_only: false,
        merge_enabled: false,
        dynamic_threshold: false,
        max_merge_gap_minutes: 45,
        merge_level: 2,
      }))
    })
    const chatTaskPayload = postSpy.mock.calls.find(([path]) => path === '/ai/tasks/chat')?.[1]
    expect(new Date((chatTaskPayload as { question_time: string }).question_time).toISOString())
      .toMatch(/^2026-07-02T08:43:01\.\d{3}Z$/)
    expect(postSpy.mock.calls.some(([path]) => path === '/ai-insights/ask')).toBe(false)
    expect(await screen.findByText('AI 任务进度')).toBeInTheDocument()
    expect(screen.getAllByText('正在查询你的年度播放数据').length).toBeGreaterThan(0)
    expect(screen.getByText('数据查询轨迹')).toBeInTheDocument()
    expect(screen.getByText('analysis_charts')).toBeInTheDocument()
  })

  it('sends thinking_mode when the visible thinking toggle is enabled', async () => {
    mockChatSessionGets([
      {
        found: true,
        task_id: 'chat-task-1',
        task_type: 'ai_chat_agent',
        status: 'running',
        stage: 'planning_tools',
        progress_pct: 0.1,
        message: '正在规划可用数据工具',
        result: null,
        error: null,
        created_at: '2026-06-28T00:00:00',
        updated_at: '2026-06-28T00:00:01',
      },
    ])
    const postSpy = mockChatPosts()

    renderChat()
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/chat/sessions/7'))

    const thinkingSwitch = screen.getByRole('switch', { name: '思考模式' })
    expect(thinkingSwitch).toHaveAttribute('aria-checked', 'false')
    fireEvent.click(thinkingSwitch)
    expect(thinkingSwitch).toHaveAttribute('aria-checked', 'true')

    fireEvent.change(screen.getByPlaceholderText('输入问题，如「我今年听最多的艺人是谁？」'), {
      target: { value: '深度分析一下我今年的听歌变化' },
    })
    fireEvent.click(screen.getByRole('button', { name: '发送问题' }))

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/ai/tasks/chat', expect.objectContaining({
        question: '深度分析一下我今年的听歌变化',
        thinking_mode: true,
      }))
    })
  })

  it('adds the done task answer as an assistant message and preserves tool trace', async () => {
    mockChatSessionGets([
      {
        found: true,
        task_id: 'chat-task-1',
        task_type: 'ai_chat_agent',
        status: 'running',
        stage: 'querying_tools',
        progress_pct: 0.5,
        message: '正在查询你的年度播放数据',
        result: null,
        error: null,
        created_at: '2026-06-28T00:00:00',
        updated_at: '2026-06-28T00:00:01',
      },
      {
        found: true,
        task_id: 'chat-task-1',
        task_type: 'ai_chat_agent',
        status: 'done',
        stage: 'done',
        progress_pct: 1,
        message: 'Agent Chat 已完成',
        result: {
          answer: '你今年听最多的艺人是 Artist A。',
          tool_call_count: 1,
          tools: [{ tool_name: 'analysis_charts', status: 'done' }],
          evidence_cards: [
            {
              card_id: 'artist:Artist A:analysis_charts',
              title: 'Artist A 年度证据',
              entity_name: 'Artist A',
              entity_type: 'artist',
              source: { tool_name: 'analysis_charts', source_range: '2026' },
              metrics: [
                { name: 'plays', label: '播放次数', value: 128, unit: 'plays' },
              ],
              observations: ['Artist A ranked #1'],
              limitations: ['2026 上半年数据'],
            },
          ],
        },
        error: null,
        created_at: '2026-06-28T00:00:00',
        updated_at: '2026-06-28T00:00:02',
      },
    ])
    const postSpy = mockChatPosts()

    renderChat()
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/chat/sessions/7'))

    fireEvent.change(screen.getByPlaceholderText('输入问题，如「我今年听最多的艺人是谁？」'), {
      target: { value: '我今年听最多的艺人是谁？' },
    })
    fireEvent.click(screen.getByRole('button', { name: '发送问题' }))

    expect((await screen.findAllByText('正在查询你的年度播放数据')).length).toBeGreaterThan(0)
    await advanceTimers(1_000)

    expect(await screen.findByText('你今年听最多的艺人是 Artist A。')).toBeInTheDocument()
    expect(screen.getByText('证据卡片')).toBeInTheDocument()
    expect(screen.getByText('Artist A 年度证据')).toBeInTheDocument()
    expect(screen.getByText('播放次数')).toBeInTheDocument()
    expect(screen.getByText('128 plays')).toBeInTheDocument()
    expect(screen.getByText('2026 上半年数据')).toBeInTheDocument()
    expect(screen.getByText('数据查询轨迹')).toBeInTheDocument()
    expect(screen.getAllByText('analysis_charts').length).toBeGreaterThan(0)
    expect(postSpy.mock.calls).toEqual(
      expect.arrayContaining([
        ['/chat/sessions/7/messages', {
          role: 'assistant',
          content: '你今年听最多的艺人是 Artist A。',
          meta_json: expect.stringContaining('evidence_cards'),
        }],
      ]),
    )
  })

  it('shows task errors and retries the failed question through a new chat task', async () => {
    mockChatSessionGets([
      {
        found: true,
        task_id: 'chat-task-1',
        task_type: 'ai_chat_agent',
        status: 'error',
        stage: 'failed',
        progress_pct: 1,
        message: 'LLM 服务不可用',
        result: { error: 'LLM 服务不可用' },
        error: 'LLM 服务不可用',
        created_at: '2026-06-28T00:00:00',
        updated_at: '2026-06-28T00:00:01',
      },
    ])
    const postSpy = mockChatPosts()

    renderChat()
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/chat/sessions/7'))

    fireEvent.change(screen.getByPlaceholderText('输入问题，如「我今年听最多的艺人是谁？」'), {
      target: { value: '我今年听最多的艺人是谁？' },
    })
    fireEvent.click(screen.getByRole('button', { name: '发送问题' }))

    expect(await screen.findByText('LLM 服务不可用')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '重试' }))

    await waitFor(() => {
      expect(postSpy.mock.calls.filter(([path]) => path === '/ai/tasks/chat')).toHaveLength(2)
    })
    expect(postSpy.mock.calls.some(([path]) => path === '/ai-insights/ask')).toBe(false)
  })

  it('uses the backend cancel response instead of writing an optimistic cancelled message', async () => {
    mockChatSessionGets([
      {
        found: true,
        task_id: 'chat-task-1',
        task_type: 'ai_chat_agent',
        status: 'running',
        stage: 'querying_tools',
        progress_pct: 0.5,
        message: '正在查询你的年度播放数据',
        result: null,
        error: null,
        created_at: '2026-06-28T00:00:00',
        updated_at: '2026-06-28T00:00:01',
      },
    ])
    const postSpy = vi.spyOn(api, 'post').mockImplementation((path: string, body?: unknown) => {
      if (path === '/chat/sessions/7/messages') {
        return Promise.resolve({ success: true, data: { id: 1, ...(body as object) } })
      }
      if (path === '/ai/tasks/chat') {
        return Promise.resolve({
          task_id: 'chat-task-1',
          status: 'queued',
          stage: 'planning_tools',
          progress_pct: 0,
          message: '正在规划可用数据工具',
          result: null,
        })
      }
      if (path === '/ai/tasks/chat-task-1/cancel') {
        return Promise.resolve({
          found: true,
          task_id: 'chat-task-1',
          task_type: 'ai_chat_agent',
          status: 'done',
          stage: 'done',
          progress_pct: 1,
          message: 'Agent Chat 已完成',
          result: { answer: '取消前已经生成完成。', tool_call_count: 0, tools: [] },
          error: null,
          created_at: '2026-06-28T00:00:00',
          updated_at: '2026-06-28T00:00:02',
        })
      }
      return Promise.reject(new Error(`unexpected POST ${path}`))
    })

    renderChat()
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/chat/sessions/7'))

    fireEvent.change(screen.getByPlaceholderText('输入问题，如「我今年听最多的艺人是谁？」'), {
      target: { value: '我今年听最多的艺人是谁？' },
    })
    fireEvent.click(screen.getByRole('button', { name: '发送问题' }))
    fireEvent.click(await screen.findByRole('button', { name: '取消' }))

    expect(await screen.findByText('取消前已经生成完成。')).toBeInTheDocument()
    expect(screen.queryByText('回答已取消')).not.toBeInTheDocument()
    expect(postSpy.mock.calls).toEqual(
      expect.arrayContaining([
        ['/chat/sessions/7/messages', {
          role: 'assistant',
          content: '取消前已经生成完成。',
          meta_json: expect.stringContaining('chat-task-1'),
        }],
      ]),
    )
  })
})
