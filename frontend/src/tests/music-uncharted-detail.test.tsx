import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AlbumDetailExperience } from '@/features/music/details/AlbumDetailExperience'
import { ArtistDetailExperience } from '@/features/music/details/ArtistDetailExperience'
import { MusicChartOverviewSection } from '@/features/music/details/MusicChartOverviewSection'
import { TrackOverviewSection } from '@/features/music/details/track/TrackOverviewSection'
import { TrackDetailExperience } from '@/features/music/details/TrackDetailExperience'
import { api } from '@/lib/api'
import type { TrackDetailResponse } from '@/types/billboard'
import { RuntimeCapabilitiesProvider } from '@/hooks/useRuntimeCapabilities'
import { FULL_CAPABILITIES } from '@/hooks/runtimeCapabilities'

vi.mock('@/hooks/useAnalysis', () => ({
  useAnalysisFilters: () => ({
    filters: {
      min_ms: 30_000,
      music_only: true,
      merge_enabled: true,
      dynamic_threshold: true,
      merge_level: 2,
      include_compilations: false,
      bb_top_n: 30,
      bb_album_top_n: 20,
      bb_artist_top_n: 20,
      bb_week_start_dow: 4,
      bb_week_start_hour: 12,
    },
    loading: false,
  }),
}))

vi.mock('@/components/shared/EntityStatsPanel', () => ({
  EntityStatsPanel: () => <div>播放统计内容</div>,
  EntityStatsPrefetch: () => null,
}))

function detailWrapper(initialEntry: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  client.setQueryData(['runtime', 'capabilities'], FULL_CAPABILITIES)
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={[initialEntry]}>
        <QueryClientProvider client={client}>
          <RuntimeCapabilitiesProvider>
            <Routes>
              <Route path="/music/albums/:albumName" element={children} />
              <Route path="/music/artists/:artistName" element={children} />
              <Route path="/music/tracks/:trackId" element={children} />
            </Routes>
          </RuntimeCapabilitiesProvider>
        </QueryClientProvider>
      </MemoryRouter>
    )
  }
}

afterEach(() => vi.restoreAllMocks())

describe('未入榜实体详情', () => {
  it('单曲标题区提供精准管理深链并保留返回路径', async () => {
    vi.spyOn(api, 'get').mockImplementation((path: string) => {
      if (path === '/billboard/track/canonical/175') {
        return Promise.resolve({
          found: true,
          chart_status: 'not_charted',
          effective_play_count: 35,
          track_id: 175,
          track_name: 'Hold Me Closer',
          artist_name: 'Elton John',
          artist_names: ['Elton John', 'Britney Spears'],
          primary_artist_name: 'Elton John',
          cover_url: null,
          meta: null,
          summary: null,
          history: [],
          chart_data: { x: [], y: [], texts: [], top_n: 30, peak_position: 0 },
        })
      }
      if (path.startsWith('/billboard/enrichment/track/')) return Promise.resolve(null)
      return Promise.reject(new Error(`unexpected GET ${path}`))
    })

    render(<TrackDetailExperience />, {
      wrapper: detailWrapper('/music/tracks/175'),
    })
    const trigger = await screen.findByRole('button', { name: '编辑 Hold Me Closer 的曲目信息' })
    fireEvent.click(trigger)
    const mergeLink = await screen.findByRole('link', { name: /归并歌曲版本/ })
    expect(mergeLink).toHaveAttribute('href', expect.stringContaining('metadata=merge'))
    expect(mergeLink).toHaveAttribute('href', expect.stringContaining('track_id=175'))
    const creditLink = screen.getByRole('link', { name: /调整曲目署名/ })
    expect(creditLink).toHaveAttribute('href', expect.stringContaining('metadata=track-credits'))
    expect(creditLink).toHaveAttribute('href', expect.stringContaining('#music-metadata-management'))
  })

  it('单曲显示有效播放空态且不伪造排名', () => {
    const data: TrackDetailResponse = {
      found: true,
      chart_status: 'not_charted',
      effective_play_count: 7,
      track_id: 42,
      track_name: 'Quiet Track',
      artist_name: 'Quiet Artist',
      artist_names: ['Quiet Artist'],
      cover_url: null,
      meta: null,
      summary: null,
      history: [],
      chart_data: { x: [], y: [], texts: [], top_n: 30, peak_position: 0 },
    }

    render(<TrackOverviewSection data={data} />)

    expect(screen.getByRole('status')).toHaveTextContent('暂未进入单曲榜')
    expect(screen.getByRole('status')).toHaveTextContent('已有 7 次有效播放')
    expect(screen.queryByText('#0')).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it.each([
    ['专辑', 1],
    ['艺人', 1_234],
  ])('%s使用独立未入榜空态', (_kind, effectivePlayCount) => {
    render(
      <MusicChartOverviewSection
        kind={_kind === '专辑' ? 'album' : 'artist'}
        chartSummary={null}
        weeklyHistory={[]}
        bestSinglesOverlay={[]}
        effectivePlayCount={effectivePlayCount}
      />,
    )

    expect(screen.getByRole('status')).toHaveTextContent(
      _kind === '专辑' ? '暂未进入专辑榜' : '暂未进入艺人榜',
    )
    expect(screen.getByRole('status')).toHaveTextContent(
      `已有 ${new Intl.NumberFormat('zh-CN').format(effectivePlayCount)} 次有效播放`,
    )
    expect(screen.queryByText(/最高排名/)).not.toBeInTheDocument()
  })

  it('CONFESSIONS II 保留三个当前 Tab，并分开显示专辑榜与单曲榜成绩', async () => {
    vi.spyOn(api, 'get').mockImplementation((path: string) => {
      if (path === '/billboard/album/CONFESSIONS II') {
        return Promise.resolve({
          found: true,
          chart_status: 'charted',
          track_chart_status: 'not_charted',
          effective_play_count: 18,
          album_name: 'CONFESSIONS II',
          artist_name: 'Madonna',
          cover_url: null,
          meta: { album_type: 'album', release_date: '2026-07-03', popularity: 87, label: 'Warner', total_tracks: 16 },
          info: null,
          chart_summary: {
            peak_position: 4,
            weeks_on_chart: 2,
            first_week: '2026-07-03',
            first_peak_week: '2026-07-17',
            latest_week: '2026-07-17',
            no1_weeks: 0,
            peak_weeks: 1,
            power_score: 288,
            power_rank: 256,
          },
          album_project: null,
          album_weekly_history: [],
          album_no1_by_week: [],
          best_singles_overlay: [],
          tracks: [],
        })
      }
      return Promise.reject(new Error(`unexpected GET ${path}`))
    })

    render(<AlbumDetailExperience />, {
      wrapper: detailWrapper('/music/albums/CONFESSIONS%20II?artist=Madonna'),
    })

    for (const name of ['播放统计', '榜单成绩', '单曲成绩']) {
      expect(await screen.findByRole('button', { name })).toBeInTheDocument()
    }
    expect(screen.queryByRole('button', { name: '发行档案' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '榜单成绩' }))
    expect(await screen.findByText('#4')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '单曲成绩' }))
    expect(await screen.findByRole('status')).toHaveTextContent('暂无歌曲进入单曲榜')
  })

  it('未入榜艺人仍保留四个当前 Tab，并分别显示三类成绩空态', async () => {
    vi.spyOn(api, 'get').mockImplementation((path: string) => {
      if (path === '/billboard/artist/Quiet Artist') {
        return Promise.resolve({
          found: true,
          chart_status: 'not_charted',
          track_chart_status: 'not_charted',
          album_chart_status: 'not_charted',
          effective_play_count: 3,
          artist_name: 'Quiet Artist',
          cover_url: null,
          meta: null,
          info: null,
          chart_summary: null,
          artist_weekly_history: [],
          artist_no1_by_week: [],
          week_no1_albums: [],
          best_singles_overlay: [],
          best_albums_overlay: [],
          tracks: [],
          albums: [],
        })
      }
      return Promise.reject(new Error(`unexpected GET ${path}`))
    })

    render(<ArtistDetailExperience />, {
      wrapper: detailWrapper('/music/artists/Quiet%20Artist'),
    })

    for (const name of ['播放统计', '榜单成绩', '单曲成绩', '专辑成绩']) {
      expect(await screen.findByRole('button', { name })).toBeInTheDocument()
    }
    expect(screen.queryByRole('button', { name: '发行周期' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '艺人生涯' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '榜单成绩' }))
    expect(await screen.findByRole('status')).toHaveTextContent('暂未进入艺人榜')
    fireEvent.click(screen.getByRole('button', { name: '单曲成绩' }))
    expect(await screen.findByRole('status')).toHaveTextContent('暂无歌曲进入单曲榜')
    fireEvent.click(screen.getByRole('button', { name: '专辑成绩' }))
    expect(await screen.findByRole('status')).toHaveTextContent('暂无专辑进入专辑榜')
  })

  it('艺人单曲成绩按页向后端请求，不在浏览器一次挂载完整列表', async () => {
    const get = vi.spyOn(api, 'get').mockImplementation((path: string, params?: Record<string, unknown>) => {
      if (path !== '/billboard/artist/Paged Artist') {
        return Promise.reject(new Error(`unexpected GET ${path}`))
      }
      const common = {
        found: true,
        chart_status: 'charted',
        track_chart_status: null,
        album_chart_status: null,
        effective_play_count: 100,
        artist_name: 'Paged Artist',
        cover_url: null,
        meta: null,
        info: {
          total_tracks: 51,
          top1: 0,
          top5: 1,
          top10: 1,
          weeks_at_no1: 0,
        },
        chart_summary: { peak_position: 5, weeks_on_chart: 2 },
        artist_weekly_history: [],
        artist_no1_by_week: [],
        week_no1_albums: [],
        best_singles_overlay: [],
        best_albums_overlay: [],
        albums: [],
      }
      if (params?.view === 'tracks') {
        const offset = Number(params.offset ?? 0)
        return Promise.resolve({
          ...common,
          track_chart_status: 'charted',
          album_chart_status: 'not_charted',
          tracks_total: 51,
          tracks_limit: 50,
          tracks_offset: offset,
          tracks_max_chart_plays: 100,
          tracks: [{
            track_id: offset + 1,
            track_name: `分页歌曲 ${offset + 1}`,
            artist_names: ['Paged Artist'],
            cover_url: null,
            peak_position: 5,
            weeks_on_chart: 2,
            weeks_at_peak: 1,
            first_week: '2026-01-01',
            first_peak_week: '2026-01-08',
            last_week: '2026-01-08',
            total_chart_plays: 100 - offset,
            power_score: 10,
            power_rank: offset + 1,
          }],
        })
      }
      return Promise.resolve({ ...common, tracks: [] })
    })

    render(<ArtistDetailExperience />, {
      wrapper: detailWrapper('/music/artists/Paged%20Artist?tab=tracks'),
    })

    expect(await screen.findByText('分页歌曲 1')).toBeInTheDocument()
    expect(get).toHaveBeenCalledWith(
      '/billboard/artist/Paged Artist',
      expect.objectContaining({ view: 'tracks', limit: 50, offset: 0 }),
    )
    fireEvent.click(screen.getByRole('button', { name: '下一页' }))
    await waitFor(() => expect(get).toHaveBeenCalledWith(
      '/billboard/artist/Paged Artist',
      expect.objectContaining({ view: 'tracks', limit: 50, offset: 50 }),
    ))
    expect(await screen.findByText('分页歌曲 51')).toBeInTheDocument()
  })

  it('专辑摘要未知子榜状态时，以单曲页签响应展示真实成绩', async () => {
    vi.spyOn(api, 'get').mockImplementation((path: string, params?: Record<string, unknown>) => {
      if (path !== '/billboard/album/Charted Album') {
        return Promise.reject(new Error(`unexpected GET ${path}`))
      }
      const common = {
        found: true,
        chart_status: 'charted',
        track_chart_status: null,
        effective_play_count: 90,
        album_name: 'Charted Album',
        artist_name: 'Charted Artist',
        cover_url: null,
        meta: null,
        info: null,
        chart_summary: { peak_position: 2, weeks_on_chart: 3 },
        album_weekly_history: [],
        album_no1_by_week: [],
        best_singles_overlay: [],
        tracks: [],
      }
      if (params?.view === 'tracks') {
        return Promise.resolve({
          ...common,
          track_chart_status: 'charted',
          info: { total_tracks: 1, top1: 0, top5: 1, top10: 1, weeks_at_no1: 0 },
          tracks: [{
            track_id: 77,
            track_name: 'Real Chart Song',
            artist_names: ['Charted Artist'],
            cover_url: null,
            peak_position: 3,
            weeks_on_chart: 2,
            weeks_at_peak: 1,
            first_week: '2026-01-01',
            first_peak_week: '2026-01-08',
            last_week: '2026-01-08',
            total_chart_plays: 80,
            power_score: 20,
            power_rank: 5,
          }],
        })
      }
      return Promise.resolve(common)
    })

    render(<AlbumDetailExperience />, {
      wrapper: detailWrapper('/music/albums/Charted%20Album?artist=Charted%20Artist&tab=tracks'),
    })

    expect(await screen.findByText('Real Chart Song')).toBeInTheDocument()
    expect(screen.queryByText('暂无歌曲进入单曲榜')).not.toBeInTheDocument()
  })

  it('艺人摘要未知子榜状态时，以专辑页签响应展示真实成绩', async () => {
    vi.spyOn(api, 'get').mockImplementation((path: string, params?: Record<string, unknown>) => {
      if (path !== '/billboard/artist/Charted Artist') {
        return Promise.reject(new Error(`unexpected GET ${path}`))
      }
      const common = {
        found: true,
        chart_status: 'charted',
        track_chart_status: null,
        album_chart_status: null,
        effective_play_count: 120,
        artist_name: 'Charted Artist',
        cover_url: null,
        meta: null,
        info: null,
        chart_summary: { peak_position: 1, weeks_on_chart: 4 },
        artist_weekly_history: [],
        artist_no1_by_week: [],
        week_no1_albums: [],
        best_singles_overlay: [],
        best_albums_overlay: [],
        tracks: [],
        albums: [],
      }
      if (params?.view === 'albums') {
        return Promise.resolve({
          ...common,
          album_chart_status: 'charted',
          info: {
            total_albums: 1,
            num_no1_albums: 0,
            album_no1_weeks: 0,
          },
          albums: [{
            album_name: 'Real Chart Album',
            cover_url: null,
            peak: 4,
            pk_wks: 1,
            weeks: 2,
            total_plays: 100,
            power_score: 30,
            power_rank: 7,
            first_week: '2026-01-01',
            first_peak_week: '2026-01-08',
            last_week: '2026-01-08',
          }],
        })
      }
      return Promise.resolve(common)
    })

    render(<ArtistDetailExperience />, {
      wrapper: detailWrapper('/music/artists/Charted%20Artist?tab=albums'),
    })

    expect(await screen.findByText('Real Chart Album')).toBeInTheDocument()
    expect(screen.queryByText('暂无专辑进入专辑榜')).not.toBeInTheDocument()
  })
})
