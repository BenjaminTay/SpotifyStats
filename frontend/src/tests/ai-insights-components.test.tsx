import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AiInsightsTimeSelectors } from '@/features/ai-insights/AiInsightsTimeSelectors'
import { ChatInterface } from '@/features/ai-insights/ChatInterface'
import { ChatSessionList } from '@/features/ai-insights/ChatSessionList'
import { SuggestedQuestions } from '@/features/ai-insights/SuggestedQuestions'
import type { ChatSession } from '@/types/ai-insights'

vi.mock('@/hooks/useAiInsights', () => ({
  useSuggestedQuestions: () => ({ questions: [], isLoading: false }),
  useChatSession: () => ({ data: null }),
  useCreateSession: () => ({ mutateAsync: vi.fn() }),
  useAddMessage: () => ({ mutate: vi.fn() }),
}))

vi.mock('@/hooks/useSettings', () => ({
  useSettings: () => ({
    settings: {
      min_ms: 30000,
      music_only: true,
      merge_enabled: true,
      dynamic_threshold: true,
      max_merge_gap_minutes: null,
    },
  }),
}))

vi.mock('@/hooks/useAiTasks', () => ({
  useAiTask: () => ({
    task: null,
    events: [],
    toolCalls: [],
    loading: false,
    fetching: false,
    error: null,
    refetch: vi.fn(),
  }),
  useStartChatAgentTask: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useCancelAiTask: () => ({ mutate: vi.fn() }),
}))

function makeSession(overrides: Partial<ChatSession> = {}): ChatSession {
  return {
    id: 1,
    title: '我的周报追问',
    created_at: '2026-06-01T12:00:00',
    updated_at: '2026-06-01T12:30:00',
    message_count: 3,
    ...overrides,
  }
}

describe('ChatSessionList', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders session actions without nesting buttons', () => {
    const { container } = render(
      <ChatSessionList
        sessions={[makeSession()]}
        activeId={null}
        onSelect={() => {}}
        onDelete={() => {}}
        onNew={() => {}}
        loading={false}
      />,
    )

    expect(container.querySelector('button button')).toBeNull()
  })

  it('keeps session selection and delete confirmation independent', () => {
    const onSelect = vi.fn()
    const onDelete = vi.fn()

    render(
      <ChatSessionList
        sessions={[makeSession()]}
        activeId={null}
        onSelect={onSelect}
        onDelete={onDelete}
        onNew={() => {}}
        loading={false}
      />,
    )

    fireEvent.click(screen.getByText('我的周报追问'))
    expect(onSelect).toHaveBeenCalledWith(1)

    fireEvent.click(screen.getByLabelText('删除对话'))
    expect(onSelect).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByText('删除'))
    expect(onDelete).toHaveBeenCalledWith(1)
  })

  it('treats SQLite chat timestamps as UTC when rendering relative time', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-06-29T06:16:40Z'))

    render(
      <ChatSessionList
        sessions={[makeSession({ updated_at: '2026-06-29 06:16:29' })]}
        activeId={null}
        onSelect={() => {}}
        onDelete={() => {}}
        onNew={() => {}}
        loading={false}
      />,
    )

    expect(screen.getByText('刚刚')).toBeInTheDocument()
    expect(screen.queryByText('8 小时前')).not.toBeInTheDocument()
  })
})

describe('ChatInterface', () => {
  it('gives the icon-only send button an accessible name', () => {
    render(
      <ChatInterface
        sessionId={null}
        onSessionCreated={() => {}}
      />,
    )

    fireEvent.change(screen.getByPlaceholderText('输入问题，如「我今年听最多的艺人是谁？」'), {
      target: { value: '我今年听最多的艺人是谁？' },
    })

    expect(screen.getByRole('button', { name: '发送问题' })).toBeEnabled()
  })

  it('presents starter questions as a labelled mobile-friendly group', () => {
    const onSelect = vi.fn()
    render(
      <SuggestedQuestions
        questions={['我今年听最多的艺人是谁？', '最近一个月的听歌习惯有什么变化？']}
        onSelect={onSelect}
        disabled={false}
      />,
    )

    expect(screen.getByText('可以这样问')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '最近一个月的听歌习惯有什么变化？' }))
    expect(onSelect).toHaveBeenCalledWith('最近一个月的听歌习惯有什么变化？')
  })
})

describe('AiInsightsTimeSelectors', () => {
  it('does not emit duplicate key errors when quick options share a date range', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

    render(
      <AiInsightsTimeSelectors
        reportType="weekly"
        weekStart="2026-06-13"
        weekEnd="2026-06-19"
        onWeekChange={() => {}}
        weekPickerOpen={false}
        onWeekPickerOpenChange={() => {}}
        latestDate={null}
        weeklyQuickOptions={[
          { label: '前 7 天', value: '2026-06-13_2026-06-19' },
          { label: '近 7 天', value: '2026-06-13_2026-06-19' },
        ]}
        weeklyQuickValue="2026-06-13_2026-06-19"
        onWeeklyQuick={() => {}}
        month="2026-06"
        onMonthChange={() => {}}
        monthPickerOpen={false}
        onMonthPickerOpenChange={() => {}}
        monthlyQuickOptions={[]}
        onMonthlyQuick={() => {}}
        year={2026}
        onYearChange={() => {}}
        nowYear={2026}
        yearlyQuickOptions={[]}
        onYearlyQuick={() => {}}
      />,
    )

    expect(consoleError).not.toHaveBeenCalledWith(
      expect.stringContaining('Encountered two children with the same key'),
      expect.anything(),
    )
    consoleError.mockRestore()
  })
})
