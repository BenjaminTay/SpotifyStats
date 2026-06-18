import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

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
