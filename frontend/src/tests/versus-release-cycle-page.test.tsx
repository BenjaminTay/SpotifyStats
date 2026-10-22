import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { apiClient } from '@/api/client'
import { SnapshotUnavailableError } from '@/api/errors'
import { VersusExperience } from '@/features/billboard/versus/VersusExperience'
import type { EntityListItem } from '@/types/billboard'

vi.mock('@/hooks/useAnalysis', () => ({ useAnalysisFilters: () => ({ filters: { min_ms: 30000, music_only: true, merge_enabled: true, dynamic_threshold: true, merge_level: 2, include_compilations: false, max_merge_gap_minutes: 5 }, loading: false }) }))
vi.mock('@/hooks/useBillboard', async (importOriginal) => ({ ...await importOriginal<object>(), useEntityLists: () => ({ data: { tracks: [], albums: [], artists: [] } }) }))
vi.mock('@/features/billboard/versus/VersusSelectorSection', () => ({
  VersusSelectorSection: ({ onAdd, onKindChange }: { onAdd: (item: EntityListItem) => void; onKindChange: (kind: 'album') => void }) => <div>
    <button onClick={() => onKindChange('album')}>选择专辑</button>
    <button onClick={() => onAdd({ display: 'One — A', album_name: 'One', artist_name: 'A' })}>添加One</button>
    <button onClick={() => onAdd({ display: 'Two — B', album_name: 'Two', artist_name: 'B' })}>添加Two</button>
  </div>,
}))
vi.mock('@/features/billboard/versus/VersusScoreboardSection', () => ({ VersusScoreboardSection: () => null }))
vi.mock('@/features/billboard/versus/VersusChartSection', () => ({ VersusChartSection: () => <div>走势已到达</div> }))

afterEach(() => vi.restoreAllMocks())

it('keeps the original six-row table and correct values when upstream chart reads fail', async () => {
  let rejectPersonal!: (error: Error) => void
  const personal = new Promise((_, reject) => { rejectPersonal = reject })
  const unavailable = new SnapshotUnavailableError({ status: 'snapshot_unavailable', message: 'not ready' } as never)
  let releaseCalls = 0
  const call = vi.spyOn(apiClient, 'postWithParams').mockImplementation((path) => {
    if (path.endsWith('/personal-stats') || path.endsWith('/personal-ranks')) return personal as Promise<never>
    if (path.endsWith('/release-cycle/compare')) {
      releaseCalls += 1
      return Promise.resolve({ comparisons: [
        { artist_name: 'A', album_name: 'One', release_date: '2000-01-01', metrics: { release_week_plays: 0 } },
        { artist_name: 'B', album_name: 'Two', release_date: '2001-02-03', metrics: { release_week_plays: 12 } },
      ], unavailable: [] }) as Promise<never>
    }
    return Promise.reject(unavailable)
  })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter><VersusExperience /></MemoryRouter></QueryClientProvider>)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: '选择专辑' }))
  await user.click(screen.getByRole('button', { name: '添加One' }))
  await user.click(screen.getByRole('button', { name: '添加Two' }))
  await waitFor(() => expect(call).toHaveBeenCalledTimes(3))
  expect(screen.getByRole('table', { name: '发行周期对比' })).toBeVisible()
  expect(screen.getByText('加载中...')).toBeVisible()
  expect(releaseCalls).toBe(0)

  await act(async () => rejectPersonal(unavailable))
  await waitFor(() => expect(screen.getByRole('row', { name: '发行周播放 0 12' })).toBeVisible())
  expect(screen.getAllByRole('row')).toHaveLength(7)
  expect(screen.getAllByRole('columnheader')).toHaveLength(3)
  expect(screen.queryByText('走势已到达')).not.toBeInTheDocument()
  expect(screen.queryByText('发行日期')).not.toBeInTheDocument()
  expect(screen.queryByText('计算状态')).not.toBeInTheDocument()
  expect(screen.queryByText('2000-01-01')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '重新加载' })).not.toBeInTheDocument()
  expect(releaseCalls).toBe(1)
})
