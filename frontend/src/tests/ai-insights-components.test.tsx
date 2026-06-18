import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { AiInsightsTimeSelectors } from '@/features/ai-insights/AiInsightsTimeSelectors'
import { ChatSessionList } from '@/features/ai-insights/ChatSessionList'
import type { ChatSession } from '@/types/ai-insights'

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
