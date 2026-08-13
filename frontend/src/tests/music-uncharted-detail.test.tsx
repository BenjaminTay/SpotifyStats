import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
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
      if (path === '/billboard/track/175') {
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
    const link = await screen.findByRole('link', { name: '编辑 Hold Me Closer 的曲目信息' })
    expect(link).toHaveAttribute('href', expect.stringContaining('metadata=track-credits'))
    expect(link).toHaveAttribute('href', expect.stringContaining('track_id=175'))
    expect(link).toHaveAttribute('href', expect.stringContaining('#music-metadata-management'))
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

  it('CONFESSIONS II 保留四个固定 Tab，并分开显示专辑榜与单曲榜成绩', async () => {
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

    for (const name of ['播放统计', '发行档案', '榜单成绩', '单曲成绩']) {
      expect(await screen.findByRole('button', { name })).toBeInTheDocument()
    }
    fireEvent.click(screen.getByRole('button', { name: '榜单成绩' }))
    expect(await screen.findByText('#4')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '单曲成绩' }))
    expect(await screen.findByRole('status')).toHaveTextContent('暂无歌曲进入单曲榜')
  })

  it('未入榜艺人仍保留六个固定 Tab，并分别显示三类成绩空态', async () => {
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

    for (const name of ['播放统计', '发行周期', '艺人生涯', '榜单成绩', '单曲成绩', '专辑成绩']) {
      expect(await screen.findByRole('button', { name })).toBeInTheDocument()
    }
    fireEvent.click(screen.getByRole('button', { name: '榜单成绩' }))
    expect(await screen.findByRole('status')).toHaveTextContent('暂未进入艺人榜')
    fireEvent.click(screen.getByRole('button', { name: '单曲成绩' }))
    expect(await screen.findByRole('status')).toHaveTextContent('暂无歌曲进入单曲榜')
    fireEvent.click(screen.getByRole('button', { name: '专辑成绩' }))
    expect(await screen.findByRole('status')).toHaveTextContent('暂无专辑进入专辑榜')
  })
})
