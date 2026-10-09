import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { TrackDetailExperience } from '@/features/music/details/TrackDetailExperience'
import { AlbumDetailExperience } from '@/features/music/details/AlbumDetailExperience'
import { ArtistDetailExperience } from '@/features/music/details/ArtistDetailExperience'
import { RuntimeCapabilitiesProvider } from '@/hooks/useRuntimeCapabilities'
import { FULL_CAPABILITIES } from '@/hooks/runtimeCapabilities'
import { SnapshotUnavailableError, CancelError } from '@/api/errors'
import { api } from '@/lib/api'
import { installDeferredObserver } from './deferred-observer'

vi.mock('@/hooks/useAnalysis', () => ({ useAnalysisFilters: () => ({
  filters: { min_ms: 30000, music_only: true, merge_enabled: true, merge_level: 2, dynamic_threshold: true }, loading: false,
}) }))
vi.mock('@/hooks/useViewportMode', () => ({ useViewportMode: () => 'desktop' }))
vi.mock('@/components/shared/EntityStatsPanel', () => ({ EntityStatsPanel: () => <div>播放统计内容</div>, EntityStatsPrefetch: () => null }))

const track = { found: true, chart_status: 'not_charted', track_id: 101, track_name: 'Track', artist_name: 'Artist',
  effective_play_count: 8, meta: null, summary: null, history: [], chart_data: { x: [], y: [], texts: [], top_n: 30, peak_position: 0 } }
const album = { found: true, chart_status: 'not_charted', album_project_id: 3, album_name: 'Album', artist_name: 'Artist',
  effective_play_count: 8, unique_canonical_songs: 7, meta: null, info: null, chart_summary: null, album_project: null,
  album_weekly_history: [], album_no1_by_week: [], best_singles_overlay: [], tracks: [] }
const artist = { found: true, chart_status: 'not_charted', artist_name: 'Artist', effective_play_count: 8,
  meta: null, info: null, chart_summary: null, artist_weekly_history: [], artist_no1_by_week: [], week_no1_albums: [],
  best_singles_overlay: [], best_albums_overlay: [], tracks: [], albums: [] }
const unavailable = () => new SnapshotUnavailableError({ error: 'snapshot_unavailable', message: '当前范围尚无已发布榜单。' } as never)

function mount(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 300000 } } })
  client.setQueryData(['runtime', 'capabilities'], FULL_CAPABILITIES)
  const router = createMemoryRouter([
    { path: '/music/tracks/:trackId', element: <TrackDetailExperience /> },
    { path: '/music/albums/:albumName', element: <AlbumDetailExperience /> },
    { path: '/music/album-projects/:albumProjectId', element: <AlbumDetailExperience /> },
    { path: '/music/artists/:artistName', element: <ArtistDetailExperience /> },
  ], { initialEntries: [path] })
  render(<QueryClientProvider client={client}><RuntimeCapabilitiesProvider><RouterProvider router={router} /></RuntimeCapabilitiesProvider></QueryClientProvider>)
  return { client, router }
}
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('音乐详情榜单独立请求生命周期', () => {
  it('overview 自带完整身份事实时不等待摘要请求完成', async () => {
    vi.spyOn(api, 'get').mockImplementation((_path, params) => params?.view === 'summary'
      ? new Promise(() => {}) : Promise.resolve(track))
    mount('/music/tracks/101?tab=overview')
    expect(await screen.findByText('暂未进入单曲榜')).toBeInTheDocument()
    expect(screen.queryByLabelText('正在加载榜单成绩')).not.toBeInTheDocument()
  })

  it.each([
    ['/music/tracks/101', track, '暂未进入单曲榜'],
    ['/music/album-projects/3', album, '暂未进入专辑榜'],
    ['/music/artists/Artist', artist, '暂未进入艺人榜'],
  ] as const)('%s 快照不可用停止加载且只由用户重试', async (path, detail, readyTitle) => {
    let ready = false
    const get = vi.spyOn(api, 'get').mockImplementation((_path, params) => params?.view === 'overview' && !ready
      ? Promise.reject(unavailable()) : Promise.resolve(detail))
    mount(`${path}?tab=overview`)
    expect(await screen.findByRole('alert')).toHaveTextContent('榜单成绩暂时不可用')
    expect(screen.queryByLabelText('正在加载榜单成绩')).not.toBeInTheDocument()
    expect(get.mock.calls.filter(([, params]) => params?.view === 'overview')).toHaveLength(1)
    ready = true
    fireEvent.click(screen.getByRole('button', { name: '重新加载' }))
    expect(await screen.findByText(readyTitle)).toBeInTheDocument()
  })

  it('切走榜单页签中止请求，迟到响应不能覆盖当前视图', async () => {
    let overviewSignal: AbortSignal | undefined
    vi.spyOn(api, 'get').mockImplementation((_path, params, _timeout, signal) => {
      if (params?.view !== 'overview') return Promise.resolve(track)
      overviewSignal = signal
      return new Promise((_resolve, reject) => signal?.addEventListener('abort', () => reject(new CancelError()), { once: true }))
    })
    mount('/music/tracks/101?tab=overview')
    await waitFor(() => expect(overviewSignal).toBeDefined())
    fireEvent.click(await screen.findByRole('button', { name: '播放统计' }))
    await waitFor(() => expect(overviewSignal?.aborted).toBe(true))
    expect(await screen.findByText('播放统计内容')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('刷新时保留上一帧，失败后仍可看到已加载结果', async () => {
    let refresh = false
    let rejectRefresh!: (error: Error) => void
    vi.spyOn(api, 'get').mockImplementation((_path, params) => params?.view === 'overview' && refresh
      ? new Promise((_resolve, reject) => { rejectRefresh = reject }) : Promise.resolve(track))
    const { client } = mount('/music/tracks/101?tab=overview')
    await screen.findByText('暂未进入单曲榜')
    refresh = true
    await act(async () => { void client.invalidateQueries({ predicate: (query) => JSON.stringify(query.queryKey).includes('overview') }) })
    expect(await screen.findByText('正在更新榜单成绩…')).toHaveAttribute('role', 'status')
    expect(screen.getByText('暂未进入单曲榜')).toBeInTheDocument()
    await act(async () => rejectRefresh(unavailable()))
    expect(await screen.findByRole('alert')).toHaveTextContent('仍显示上次成功加载的结果')
    expect(screen.getByText('暂未进入单曲榜')).toBeInTheDocument()
  })

  it('名称深链只读一次身份摘要，榜单只用规范 ID 请求一次', async () => {
    let resolveSummary!: (value: typeof album) => void
    const get = vi.spyOn(api, 'get').mockImplementation((_path, params) => params?.view === 'summary'
      ? new Promise(resolve => { resolveSummary = resolve }) : Promise.resolve(album))
    const { router } = mount('/music/albums/Album?artist=Artist&tab=overview&merge_level=3#history')
    await waitFor(() => expect(resolveSummary).toBeDefined())
    expect(get.mock.calls.filter(([, params]) => params?.view === 'overview')).toHaveLength(0)
    await act(async () => resolveSummary(album))
    expect(await screen.findByText('暂未进入专辑榜')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/music/album-projects/3')
    expect(router.state.location.search).toContain('merge_level=3')
    expect(router.state.location.hash).toBe('#history')
    expect(get.mock.calls.filter(([, params]) => params?.view === 'summary')).toHaveLength(1)
    expect(get.mock.calls.filter(([, params]) => params?.view === 'overview')).toHaveLength(1)
    expect(get.mock.calls.find(([, params]) => params?.view === 'overview')?.[0]).toBe('/billboard/album-project/3')
    expect(get.mock.calls.filter(([, params]) => params?.view === 'project')).toHaveLength(0)
  })

  it('header 已听首数来自摘要，来源归属滚入视口后才请求', async () => {
    const observer = installDeferredObserver()
    const get = vi.spyOn(api, 'get').mockResolvedValue(album)
    mount('/music/album-projects/3')
    expect(await screen.findByText('已听 7 首')).toBeInTheDocument()
    expect(get.mock.calls.filter(([, params]) => params?.view === 'project')).toHaveLength(0)
    observer.enter('[aria-label="专辑版本与来源归属"]')
    await waitFor(() => expect(get.mock.calls.filter(([, params]) => params?.view === 'project')).toHaveLength(1))
  })
})
