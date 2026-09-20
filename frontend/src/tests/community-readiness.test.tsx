import { act, render, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useCommunityChartParams, useCommunityFeed } from '@/hooks/useCommunity'
import { queryKeys } from '@/api/query-keys'
import { CommunityExperience } from '@/features/community/CommunityExperience'
import { CommunityAccountExperience } from '@/features/community/CommunityAccountExperience'
import { PostDetailExperience } from '@/features/community/PostDetailExperience'
const mock = vi.hoisted(() => ({ settings: null as Record<string, unknown> | null, error: null as string | null, get: vi.fn() }))
vi.mock('@/hooks/useSettings', () => ({ useSettings: () => ({ settings: mock.settings, loading: !mock.settings && !mock.error, error: mock.error, refetch: vi.fn() }) }))
vi.mock('@/lib/api', () => ({ api: { get: mock.get } }))
vi.mock('@/features/community/CommunityTimeline', () => ({ CommunityTimeline: ({ loading, error }: { loading: boolean; error: string }) => <div>{error || (loading ? 'waiting' : 'ready')}</div> }))
vi.mock('@/features/community/CommunitySidebar', () => ({ CommunitySidebar: () => null }))
const settings = { min_ms: 45000, music_only: true, merge_enabled: true, include_compilations: false, max_merge_gap_minutes: 7, bb_top_n: 30, bb_album_top_n: 20, bb_artist_top_n: 20, bb_week_start_dow: 4, bb_week_start_hour: 12 }
function wrapper() { const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); return ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider> }
beforeEach(() => { mock.settings = null; mock.error = null; mock.get.mockReset(); localStorage.clear(); mock.get.mockImplementation(async (path: string) => path.endsWith('/feed') ? { posts: [], meta: { total: 0, offset: 0, returned: 0 } } : path.includes('/post/') ? { post: { id: 'one', account_handle: '@chartdata', content: 'test', posted_at: '2026-01-01', tags: [], metrics: {} }, replies: [] } : { artists: [], tracks: [] }) })
describe('Community final settings contract', () => {
  it.each([['/community', '/community', CommunityExperience, '/community/feed'], ['/community/account/@chartdata', '/community/account/:handle', CommunityAccountExperience, '/community/feed'], ['/community/post/one', '/community/post/:postId', PostDetailExperience, '/community/post/one']] as const)('gates %s and sends exactly one round', async (url, route, Component, endpoint) => {
    const Wrapper = wrapper(); const view = () => <Wrapper><MemoryRouter initialEntries={[url]}><Routes><Route path={route} element={<Component />} /></Routes></MemoryRouter></Wrapper>
    const result = render(view()); expect(mock.get).not.toHaveBeenCalled()
    mock.settings = settings; result.rerender(view())
    await waitFor(() => expect(mock.get).toHaveBeenCalledTimes(2))
    expect(mock.get.mock.calls.map(c => c[0]).sort()).toEqual([endpoint, '/community/trending'].sort())
    for (const call of mock.get.mock.calls) expect(call[1]).toMatchObject({ ...settings, merge_level: 2, dynamic_threshold: true })
    expect(mock.get.mock.calls.every(c => c[3] instanceof AbortSignal)).toBe(true)
  })
  it('surfaces settings failure without fallback requests', async () => {
    mock.error = 'settings failed'; const Wrapper = wrapper(); const view = render(<Wrapper><MemoryRouter><CommunityExperience /></MemoryRouter></Wrapper>)
    expect(view.getByText('settings failed')).toBeInTheDocument(); expect(mock.get).not.toHaveBeenCalled()
  })
  it('normalizes equivalent filters but retains all semantic dimensions', () => {
    expect(queryKeys.community.feed({ accounts: 'b,a,a', highlights_only: false, offset: 0, limit: 50, search: undefined, significance_min: 0 })).toEqual(queryKeys.community.feed({ accounts: 'a,b' }))
    for (const key of ['search','accounts','tags','date_from','date_to','highlights_only','merge_level','include_compilations','max_merge_gap_minutes','bb_week_start_hour']) expect(queryKeys.community.feed({ [key]: 'changed' })).not.toEqual(queryKeys.community.feed({}))
  })
  it('keeps pageParam pagination and isolates late responses for changed filters', async () => {
    mock.settings = settings; let oldResolve!: (v: unknown) => void
    mock.get.mockImplementation((_path, params) => params.search === 'old' ? new Promise(r => { oldResolve = r }) : Promise.resolve({ posts: [{ id: String(params.offset) }], meta: { total: 2, offset: params.offset, returned: 1 } }))
    const { result, rerender } = renderHook(({ search }) => { const chart = useCommunityChartParams(); return useCommunityFeed({ ...chart.params, search }, chart.ready) }, { wrapper: wrapper(), initialProps: { search: 'old' } })
    rerender({ search: 'new' }); await waitFor(() => expect(result.current.posts[0]?.id).toBe('0'))
    await act(async () => oldResolve({ posts: [{ id: 'old' }], meta: { total: 1, offset: 0, returned: 1 } })); expect(result.current.posts[0].id).toBe('0')
    act(() => result.current.loadMore()); await waitFor(() => expect(result.current.posts.map(p => p.id)).toEqual(['0','1']))
    expect(mock.get.mock.calls.at(-1)?.[1]).toMatchObject({ search: 'new', offset: 1, limit: 50 })
  })
})
