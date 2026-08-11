import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AlbumDetailExperience } from '@/features/music/details/AlbumDetailExperience'
import { ArtistDetailExperience } from '@/features/music/details/ArtistDetailExperience'
import { api } from '@/lib/api'
import type { AlbumDetailResponse, ArtistDetailResponse, ReleaseCycleAlbumDetailResponse } from '@/types/billboard'

vi.mock('@/components/charts/ReleaseTimelineChart', () => ({
  ReleaseTimelineChart: () => <div>release cycle chart ready</div>,
}))

function createClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity },
      mutations: { retry: false },
    },
  })
}

function wrapperFor(client: QueryClient, initialEntry: string) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={[initialEntry]}>
        <QueryClientProvider client={client}>
          <Routes>
            <Route path="/music/artists/:artistName" element={children} />
            <Route path="/music/albums/:albumName" element={children} />
          </Routes>
        </QueryClientProvider>
      </MemoryRouter>
    )
  }
}

async function advanceTimers(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

function artistDetail(): ArtistDetailResponse {
  return {
    found: true,
    artist_name: 'Taylor Swift',
    cover_url: null,
    meta: { followers: 1000, popularity: 95, genres: ['pop'] },
    info: {
      total_tracks: 1,
      best_peak: 1,
      total_weeks: 1,
      avg_weeks: 1,
      top1: 1,
      top5: 1,
      top10: 1,
      weeks_at_no1: 1,
      num_no1_albums: 1,
      total_albums: 1,
      album_top5: 1,
      album_no1_weeks: 1,
      total_album_weeks: 1,
      total_track_power: 10,
      total_album_power: 10,
      track_power_rank: 1,
      album_power_rank: 1,
    },
    chart_summary: {
      peak_position: 1,
      weeks_on_chart: 1,
      first_week: '2026-01-01',
      first_peak_week: '2026-01-01',
      latest_week: '2026-01-08',
      no1_weeks: 1,
      peak_weeks: 1,
      power_score: 10,
      power_rank: 1,
    },
    artist_weekly_history: [],
    artist_no1_by_week: [],
    week_no1_albums: [],
    best_singles_overlay: [],
    best_albums_overlay: [],
    tracks: [],
    albums: [],
  }
}

function albumDetail(): AlbumDetailResponse {
  return {
    found: true,
    album_name: 'Midnights',
    artist_name: 'Taylor Swift',
    cover_url: null,
    meta: {
      album_type: 'album',
      release_date: '2022-10-21',
      popularity: 90,
      label: 'Republic',
      total_tracks: 13,
    },
    info: {
      total_tracks: 1,
      best_peak: 1,
      total_weeks: 1,
      avg_weeks: 1,
      top1: 1,
      top5: 1,
      top10: 1,
      weeks_at_no1: 1,
      album_chart_no1_weeks: 1,
      total_track_power: 10,
      track_power_rank: 1,
    },
    chart_summary: {
      peak_position: 1,
      weeks_on_chart: 1,
      first_week: '2026-01-01',
      first_peak_week: '2026-01-01',
      latest_week: '2026-01-08',
      no1_weeks: 1,
      peak_weeks: 1,
      power_score: 10,
      power_rank: 1,
    },
    album_project: null,
    album_weekly_history: [
      {
        week: '2026-01-01',
        rank: 1,
        play_count: 10,
        tracks_count: 1,
        change: 'NEW',
        running_peak: 1,
        running_wks: 1,
        running_peak_wks: 1,
      },
    ],
    album_no1_by_week: [],
    best_singles_overlay: [],
    tracks: [],
  }
}

function albumReleaseCycle(): ReleaseCycleAlbumDetailResponse {
  return {
    error: null,
    album_name: 'Midnights',
    artist_name: 'Taylor Swift',
    album_type: 'album',
    release_date: '2022-10-21',
    release_date_iso: '2022-10-21',
    canonical_name: 'Midnights',
    primary_name: 'Midnights',
    group_albums: [],
    is_grouped: false,
    advance_singles: [],
    metrics: {
      debut_rank: 1,
      peak_rank: 1,
      weeks_to_peak: 0,
      weeks_on_chart: 1,
      artist_impact: null,
      market_impact: null,
      half_life: null,
      peak_play_count: 10,
      release_week_plays: 10,
      pre_release_avg: 0,
    },
    artist_timeline: [],
    album_timeline: [{ week_offset: 0, play_count: 10 }],
    track_timelines: [],
    artist_ranks: [],
    album_ranks: [{ billboard_week: '2026-01-01', week_offset: 0, rank: 1, play_count: 10 }],
    total_timeline: [],
    artist_all_time_median: null,
    clean_baseline_start: null,
    advance_single_ranks: [],
    best_track_ranks: null,
    catalog_reentries: [],
    bonus_tracks: [],
    track_matrix: null,
  }
}

describe('music detail enrichment task flow', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('starts artist enrichment as an AI task, shows progress, then renders wiki content', async () => {
    const taskResponses = [
      {
        found: true,
        task_id: 'artist-task-1',
        task_type: 'artist_enrichment',
        status: 'running',
        stage: 'fetching_wikipedia',
        progress_pct: 0.45,
        message: '正在整理艺人 Wikipedia 信息',
        result: null,
        error: null,
      },
      {
        found: true,
        task_id: 'artist-task-1',
        task_type: 'artist_enrichment',
        status: 'done',
        stage: 'done',
        progress_pct: 1,
        message: '艺人资料整理完成',
        result: {
          wiki: {
            lang: 'en',
            summary: 'Taylor Swift is an American singer-songwriter.',
            summary_zh: 'Taylor Swift 是美国创作歌手。',
            description: '',
            description_zh: '',
            thumbnail: '',
            url: 'https://example.test/taylor',
            sections: { early_life: '', discography: '' },
            sections_zh: { early_life: '', discography: '' },
          },
          genius: null,
        },
        error: null,
      },
    ]
    const getSpy = vi.spyOn(api, 'get').mockImplementation((path: string) => {
      if (path === '/billboard/artist/Taylor Swift') {
        return Promise.resolve(artistDetail())
      }
      if (path === '/ai/tasks/artist-task-1') {
        return Promise.resolve(taskResponses.shift() ?? taskResponses.at(-1))
      }
      if (path === '/ai/tasks/artist-task-1/events') {
        return Promise.resolve({
          found: true,
          events: [
            {
              event_id: 1,
              task_id: 'artist-task-1',
              event_type: 'stage_started',
              stage: 'fetching_wikipedia',
              message: '正在整理艺人 Wikipedia 信息',
              payload: null,
              created_at: '2026-06-28T00:00:00',
            },
          ],
          tool_calls: [],
        })
      }
      return Promise.reject(new Error(`unexpected GET ${path}`))
    })
    const postSpy = vi.spyOn(api, 'post').mockImplementation((path: string, body?: unknown) => {
      if (path === '/ai/tasks/enrichment/artist') {
        return Promise.resolve({
          task_id: 'artist-task-1',
          status: 'queued',
          stage: 'queued',
          progress_pct: 0,
          message: '准备整理艺人资料',
          result: null,
        })
      }
      return Promise.reject(new Error(`unexpected POST ${path} ${JSON.stringify(body)}`))
    })

    const client = createClient()
    render(<ArtistDetailExperience />, {
      wrapper: wrapperFor(client, '/music/artists/Taylor%20Swift'),
    })

    fireEvent.click(await screen.findByRole('button', { name: '艺人生涯' }))

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/ai/tasks/enrichment/artist', {
        artist_name: 'Taylor Swift',
      })
    })
    expect(await screen.findByText('AI 任务进度')).toBeInTheDocument()
    expect(screen.getAllByText('正在整理艺人 Wikipedia 信息').length).toBeGreaterThan(0)
    expect(getSpy.mock.calls.some(([path]) => String(path).startsWith('/billboard/enrichment/artist'))).toBe(false)

    fireEvent.click(screen.getByRole('button', { name: '播放统计' }))
    fireEvent.click(screen.getByRole('button', { name: '艺人生涯' }))
    expect(postSpy.mock.calls.filter(([path]) => path === '/ai/tasks/enrichment/artist')).toHaveLength(1)

    await advanceTimers(1_000)
    expect(await screen.findByText('Taylor Swift 是美国创作歌手。')).toBeInTheDocument()
  })

  it('starts album enrichment as an AI task without blocking release-cycle content', async () => {
    const taskResponses = [
      {
        found: true,
        task_id: 'album-task-1',
        task_type: 'album_enrichment',
        status: 'running',
        stage: 'fetching_wikipedia',
        progress_pct: 0.4,
        message: '正在整理专辑 Wikipedia 信息',
        result: null,
        error: null,
      },
      {
        found: true,
        task_id: 'album-task-1',
        task_type: 'album_enrichment',
        status: 'done',
        stage: 'done',
        progress_pct: 1,
        message: '专辑资料整理完成',
        result: {
          wiki: {
            lang: 'en',
            summary: 'Midnights is a studio album by Taylor Swift.',
            summary_zh: 'Midnights 是 Taylor Swift 的录音室专辑。',
            description: '',
            description_zh: '',
            thumbnail: '',
            url: 'https://example.test/midnights',
            infobox: {
              recorded: '',
              studio: '',
              genre: '',
              length: '',
              label: '',
              producer: '',
              singles: [],
            },
            sections: {
              background: 'Album background',
              reception: '',
              commercial: '',
            },
            sections_zh: {
              background: '专辑背景',
              reception: '',
              commercial: '',
            },
          },
          genius: null,
        },
        error: null,
      },
    ]
    const getSpy = vi.spyOn(api, 'get').mockImplementation((path: string) => {
      if (path === '/billboard/album/Midnights') {
        return Promise.resolve(albumDetail())
      }
      if (path === '/billboard/release-cycle/artist/Taylor%20Swift/album/Midnights') {
        return Promise.resolve(albumReleaseCycle())
      }
      if (path === '/ai/tasks/album-task-1') {
        return Promise.resolve(taskResponses.shift() ?? taskResponses.at(-1))
      }
      if (path === '/ai/tasks/album-task-1/events') {
        return Promise.resolve({
          found: true,
          events: [
            {
              event_id: 1,
              task_id: 'album-task-1',
              event_type: 'stage_started',
              stage: 'fetching_wikipedia',
              message: '正在整理专辑 Wikipedia 信息',
              payload: null,
              created_at: '2026-06-28T00:00:00',
            },
          ],
          tool_calls: [],
        })
      }
      return Promise.reject(new Error(`unexpected GET ${path}`))
    })
    const postSpy = vi.spyOn(api, 'post').mockImplementation((path: string, body?: unknown) => {
      if (path === '/ai/tasks/enrichment/album') {
        return Promise.resolve({
          task_id: 'album-task-1',
          status: 'queued',
          stage: 'queued',
          progress_pct: 0,
          message: '准备整理专辑资料',
          result: null,
        })
      }
      return Promise.reject(new Error(`unexpected POST ${path} ${JSON.stringify(body)}`))
    })

    const client = createClient()
    render(<AlbumDetailExperience />, {
      wrapper: wrapperFor(client, '/music/albums/Midnights?artist=Taylor%20Swift'),
    })

    fireEvent.click(await screen.findByRole('button', { name: '发行档案' }))

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith('/ai/tasks/enrichment/album', {
        album_name: 'Midnights',
        artist_name: 'Taylor Swift',
      })
    })
    expect(await screen.findByText('AI 任务进度')).toBeInTheDocument()
    expect(screen.getAllByText('正在整理专辑 Wikipedia 信息').length).toBeGreaterThan(0)
    expect(await screen.findByText('release cycle chart ready')).toBeInTheDocument()
    expect(getSpy.mock.calls.some(([path]) => String(path).startsWith('/billboard/enrichment/album'))).toBe(false)

    await advanceTimers(1_000)
    expect(await screen.findByText('专辑背景')).toBeInTheDocument()
  })
})
