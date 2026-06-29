import { createRef } from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ChatMessageList } from '@/features/ai-insights/ChatMessageList'
import { ReportCard } from '@/features/ai-insights/ReportCard'

const MARKDOWN_TABLE = [
  '| 维度 | GUTS | The Life of a Showgirl |',
  '| --- | ---: | ---: |',
  '| 播放次数 | 1749 | 1637 |',
  '| Power Score | 13566 | 10629 |',
].join('\n')

describe('AI markdown rendering', () => {
  it('renders assistant markdown tables as real tables in chat messages', () => {
    render(
      <ChatMessageList
        messages={[{ role: 'assistant', content: MARKDOWN_TABLE }]}
        asking={false}
        retryingIdx={null}
        onRetry={() => {}}
        onCancel={() => {}}
        bottomRef={createRef<HTMLDivElement>()}
      />,
    )

    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '维度' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: '13566' })).toBeInTheDocument()
  })

  it('renders report markdown tables as real tables', () => {
    render(
      <ReportCard
        title="周报"
        reportType="weekly"
        report={MARKDOWN_TABLE}
        cached={false}
        cachedAt={null}
        entities={null}
        loading={false}
        fetching={false}
        error={null}
        onRetry={vi.fn()}
      />,
    )

    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'The Life of a Showgirl' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: '10629' })).toBeInTheDocument()
  })
})
