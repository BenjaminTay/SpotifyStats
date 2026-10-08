import { render, screen, waitFor, within, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { apiClient } from '@/api/client'
import { VersusExperience } from '@/features/billboard/versus/VersusExperience'
import { METRIC_DEFS } from '@/features/billboard/versus/versusData'
import type { VersusResponse, EntityListItem } from '@/types/billboard'

vi.mock('@/hooks/useAnalysis', () => ({ useAnalysisFilters: () => ({ filters: { min_ms: 30000, music_only: true, merge_enabled: true, dynamic_threshold: true, merge_level: 2, include_compilations: false, max_merge_gap_minutes: 5 }, loading: false }) }))
vi.mock('@/hooks/useBillboard', async (importOriginal) => ({ ...await importOriginal<object>(), useEntityLists: () => ({ data: { tracks: [], albums: [], artists: [] } }) }))
vi.mock('@/features/billboard/versus/VersusSelectorSection', () => ({
  VersusSelectorSection: ({ onAdd }: { onAdd: (item: EntityListItem) => void }) => <div><button onClick={() => onAdd({ display: 'One', track_id: 1 })}>添加One</button><button onClick={() => onAdd({ display: 'Two', track_id: 2 })}>添加Two</button></div>,
}))
vi.mock('@/features/billboard/versus/VersusChartSection', () => ({ VersusChartSection: () => <div>走势已到达</div> }))

it('renders complete personal rows while the independent Billboard POST is still running', async () => {
  let resolveChart!: (data: VersusResponse) => void
  const slowChart = new Promise<VersusResponse>((resolve) => { resolveChart = resolve })
  const period = { period: 'lifetime', label: '全部', start_date: null, end_date: null }
  const context = { filter_fingerprint: 'fp', source_revision: 'rev', statistics_contract_version: 'versus_personal_v1' }
  const items = [1, 2].map((id) => ({ requested_key: JSON.stringify(['track', id]), entity_key: `track:${id}`, found: true, status: 'found', metrics: { total_plays: id * 10, total_hours: id, active_days: id, avg_daily_plays: 10, avg_daily_hours: 1, max_daily_plays: id }, ranks: { lifetime: id, last_6_months: id, last_4_weeks: id } }))
  const call = vi.spyOn(apiClient, 'postWithParams').mockImplementation((path) => {
    if (path.endsWith('/personal-stats')) return Promise.resolve({ ...context, period, entities: items }) as Promise<never>
    if (path.endsWith('/personal-ranks')) return Promise.resolve({ ...context, snapshot: { status: 'ready', freshness: 'current', source_revision: context.source_revision, target_revision: context.source_revision, builder_version: 'entity_rank_context_v2', request_key: 'context-key' }, periods: { lifetime: period, last_6_months: period, last_4_weeks: period }, entities: items }) as Promise<never>
    return slowChart as Promise<never>
  })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const user = userEvent.setup()
  render(<QueryClientProvider client={client}><MemoryRouter><VersusExperience /></MemoryRouter></QueryClientProvider>)
  await user.click(screen.getByRole('button', { name: '添加One' }))
  expect(call).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: '添加Two' }))
  await waitFor(() => expect(call).toHaveBeenCalledTimes(3))
  await waitFor(() => expect(within(screen.getByText('个人总播放').closest('tr')!).getByText('20')).toBeVisible())
  expect(screen.getByText('已完成指标得分')).toBeVisible()
  expect(screen.queryByText('走势已到达')).not.toBeInTheDocument()
  expect(call.mock.calls.map(([path]) => path).sort()).toEqual(['/billboard/versus/track', '/billboard/versus/track/personal-ranks', '/billboard/versus/track/personal-stats'])
  await act(async () => resolveChart({ found: true, entities: [1, 2].map((id) => ({ name: id === 1 ? 'One' : 'Two', cover_url: null, popularity: null, rank_history: [{ week: '2026-09-01', rank: id, play_count: id }], metrics: Object.fromEntries(METRIC_DEFS.filter((def) => !def.only || def.only === 'track').map((def) => [def.key, id])) })) }))
  await waitFor(() => expect(screen.getByText('总分 (胜出指标数)')).toBeVisible())
  expect(screen.getByText('走势已到达')).toBeVisible()
  vi.restoreAllMocks()
})
