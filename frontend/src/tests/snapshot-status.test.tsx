import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { SnapshotStatusNotice } from '@/components/shared/SnapshotStatusNotice'
import { HomeError } from '@/features/home/HomeStates'

describe('published snapshot presentation', () => {
  it('shows page-local LKG freshness without backend publication wording', () => {
    const view = render(<SnapshotStatusNotice snapshot={{ status: 'warming', freshness: 'last_known_good', target_revision: 'next' }} />)
    expect(screen.getByRole('status')).toHaveTextContent('数据正在更新')
    expect(screen.getByRole('status')).not.toHaveTextContent('发布')
    view.rerender(<SnapshotStatusNotice snapshot={{ status: 'ready', freshness: 'current', target_revision: 'next' }} />)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it.each([false, true])('shows unpublished Home separately from an empty archive (phone=%s)', (phone) => {
    render(<MemoryRouter><HomeError phone={phone} unavailable onRetry={vi.fn()} /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: '音乐头版数据正在准备' })).toBeInTheDocument()
    expect(screen.queryByText('导入 Spotify 数据')).not.toBeInTheDocument()
  })
})

it('reads infinite Community pages and reports a failed rebuild with LKG', () => {
  render(<SnapshotStatusNotice snapshot={{ status: 'warming', freshness: 'last_known_good', target_revision: 'next', build_status: 'failed' }} />)
  expect(screen.getByRole('status')).toHaveTextContent('数据更新暂未完成')
})
