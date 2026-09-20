import { act, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { SnapshotStatusNotice } from '@/components/shared/SnapshotStatusNotice'
import { HomeError } from '@/features/home/HomeStates'

function ObservedSnapshot() {
  useQuery({ queryKey: ['publication'], queryFn: async () => null, enabled: false })
  return <SnapshotStatusNotice />
}

describe('published snapshot presentation', () => {
  it('shows LKG freshness only for an observed query and clears it on exact publication', () => {
    const client = new QueryClient()
    client.setQueryData(['unobserved'], { snapshot: { freshness: 'last_known_good' } })
    render(<QueryClientProvider client={client}><ObservedSnapshot /></QueryClientProvider>)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    act(() => { client.setQueryData(['publication'], { snapshot: { freshness: 'last_known_good' }, archive: { total_plays: 17 } }) })
    expect(screen.getByRole('status')).toHaveTextContent('上次发布的数据')
    expect(client.getQueryData(['publication'])).toMatchObject({ archive: { total_plays: 17 } })
    act(() => { client.setQueryData(['publication'], { snapshot: { freshness: 'current' } }) })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it.each([false, true])('shows unpublished Home separately from an empty archive (phone=%s)', (phone) => {
    render(<MemoryRouter><HomeError phone={phone} unavailable onRetry={vi.fn()} /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: '音乐头版数据尚未发布' })).toBeInTheDocument()
    expect(screen.queryByText('导入 Spotify 数据')).not.toBeInTheDocument()
  })
})

it('reads infinite Community pages and reports a failed rebuild with LKG', () => {
  const client = new QueryClient()
  client.setQueryData(['publication'], { pages: [{ posts: [{ id: 'preserved' }], snapshot: { freshness: 'last_known_good', build_status: 'failed' } }] })
  render(<QueryClientProvider client={client}><ObservedSnapshot /></QueryClientProvider>)
  expect(screen.getByRole('status')).toHaveTextContent('最新数据构建失败')
  expect(client.getQueryData(['publication'])).toMatchObject({ pages: [{ posts: [{ id: 'preserved' }] }] })
})
