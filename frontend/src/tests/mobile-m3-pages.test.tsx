import { useState } from 'react'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MobileAnalysisStats } from '@/features/mobile/analysis/MobileAnalysisStats'
import { MobileAnalysisTimeControl } from '@/features/mobile/analysis/MobileAnalysisTimeControl'
import { MobilePersonalRankList } from '@/features/mobile/analysis/MobilePersonalRankList'
import { MobileBillboardWeekly } from '@/features/mobile/billboard/MobileBillboardWeekly'
import { MobileDashboard } from '@/features/mobile/dashboard/MobileDashboard'
import { computeWeeklyRankChange } from '@/features/billboard/weekly/weeklyPresentation'
import type { AnalysisChartsResponse, AnalysisMetric, LeaderboardEntity } from '@/types/analysis'
import type { DashboardFullResponse } from '@/types/dashboard'
import type { BillboardWeeklyResponse, WeeklyAlbumEntry, WeeklyTrackEntry } from '@/types/billboard'

vi.mock('@/components/charts/MonthlyTrendChart', () => ({
  MonthlyTrendChart: () => <div data-testid="monthly-trend-chart" />,
}))
vi.mock('@/components/charts/PlatformDistChart', () => ({
  PlatformDistChart: () => <div data-testid="platform-chart" />,
}))
vi.mock('@/components/charts/AnalysisCharts', () => ({
  AnalysisTrendChart: ({ data }: { data: unknown[] }) => <div data-testid="analysis-trend-chart">{data.length}</div>,
}))
vi.mock('@/components/charts/ListeningClock', () => ({
  ListeningClock: () => <div data-testid="listening-clock" />,
}))
vi.mock('@/components/shared/RecentPlaysSection', () => ({
  RecentPlaysSection: ({ mobile }: { mobile?: boolean }) => <div data-testid="recent-plays">{mobile ? 'mobile' : 'desktop'}</div>,
}))

afterEach(() => {
  document.body.style.overflow = ''
})

function PersonalRankHarness({ data }: { data: AnalysisChartsResponse }) {
  const [entity, setEntity] = useState<LeaderboardEntity>('track')
  const metric: AnalysisMetric = 'plays'
  const [search, setSearch] = useState('')
  return (
    <MobilePersonalRankList
      data={data}
      loading={false}
      entity={entity}
      metric={metric}
      searchQuery={search}
      onEntityChange={setEntity}
      onSearchChange={setSearch}
    />
  )
}

describe('M3 mobile page presentations', () => {
  it('renders the dashboard as four KPIs, one monthly chart, and mobile quick links', () => {
    const data = {
      summary: {
        total_plays: 1234,
        total_hours: 88,
        total_tracks: 321,
        total_artists: 42,
        total_days: 120,
      },
      monthly_trend: [],
      platform_dist: [],
    } as unknown as DashboardFullResponse

    render(
      <MemoryRouter>
        <MobileDashboard data={data} monthlyInsight="春天之后播放明显增加" peakHour={22} peakHourText="夜间是最集中的聆听窗口" />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '你的聆听概览' })).toBeInTheDocument()
    expect(screen.getAllByRole('article')).toHaveLength(6)
    expect(screen.getByTestId('monthly-trend-chart')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /播放排行/ })).toHaveAttribute('href', '/analysis/charts')
  })

  it('keeps original personal-chart ranks after mobile search filters the visible rows', async () => {
    const user = userEvent.setup()
    const data = {
      period: { label: '全部时间' },
      total: 2,
      rows: [
        { rank: 1, track_id: 1, track_name: 'Popular Song', artist_name: 'A', plays: 100, hours: 5, share_pct: 20 },
        { rank: 41, track_id: 41, track_name: 'Rare Song', artist_name: 'B', plays: 8, hours: 1, share_pct: 1.6, first_played: '2023-02-26' },
      ],
    } as unknown as AnalysisChartsResponse

    render(<MemoryRouter><PersonalRankHarness data={data} /></MemoryRouter>)
    await user.type(screen.getByRole('searchbox', { name: '在当前播放排行中搜索' }), 'Rare')

    const result = screen.getByRole('link', { name: /Rare Song/ })
    expect(within(result).getByText('41')).toBeInTheDocument()
    expect(result).not.toHaveTextContent('始于 2023-02-26')
    expect(result).toHaveClass('mobile-personal-rank-row')
    expect(screen.queryByText('Popular Song')).not.toBeInTheDocument()
  })

  it('uses 20 items per page and exposes pagination above and below the mobile ranking list', async () => {
    const user = userEvent.setup()
    const data = {
      period: { label: '全部时间' },
      total: 21,
      rows: Array.from({ length: 21 }, (_, index) => ({
        rank: index + 1,
        track_id: index + 1,
        track_name: `Song ${index + 1}`,
        artist_name: 'Artist',
        plays: 100 - index,
        hours: 5,
        share_pct: 1,
      })),
    } as unknown as AnalysisChartsResponse

    render(<MemoryRouter><PersonalRankHarness data={data} /></MemoryRouter>)

    expect(screen.queryByText('20 项')).not.toBeInTheDocument()
    const rankHeader = screen.getByRole('heading', { name: '歌曲榜' }).closest('header')
    expect(within(rankHeader!).getByRole('navigation', { name: '列表分页' })).toBeInTheDocument()
    expect(within(rankHeader!).getByRole('navigation', { name: '列表分页' })).not.toHaveTextContent('/')
    expect(screen.getAllByRole('navigation', { name: '列表分页' })).toHaveLength(2)
    expect(screen.getAllByRole('button', { name: '下一页' })).toHaveLength(2)
    await user.click(screen.getAllByRole('button', { name: '下一页' })[0])
    expect(screen.getByText('Song 21')).toBeInTheDocument()
    expect(screen.queryByText('Song 1')).not.toBeInTheDocument()
  })

  it('shows the mobile stats hierarchy and switches trend views without refetching', async () => {
    const user = userEvent.setup()
    const onRangeChange = vi.fn()
    const data = {
      period: { label: '2026 年' },
      summary: {
        total_plays: 100,
        total_hours: 9.5,
        unique_tracks: 40,
        active_days: 12,
        unique_albums: 20,
        unique_artists: 10,
      },
      daily_metrics: { avg_daily_plays: 8.3, avg_daily_hours: 0.8 },
      daily_trend: [{ date: '2026-08-01', plays: 10, hours: 1 }],
      cumulative_trend: [{ date: '2026-08-01', cumulative_plays: 10, cumulative_hours: 1 }],
      weekday_distribution: [{ day: '周一', plays: 10, hours: 1 }],
      month_distribution: [{ month: 8, plays: 10, hours: 1 }],
      year_distribution: [{ year: 2026, plays: 10, hours: 1 }],
      hourly_distribution: [{ hour: 22, plays: 10, hours: 1 }],
    }

    render(
      <MobileAnalysisStats
        data={data as never}
        metric="plays"
        timeControl={(
          <MobileAnalysisTimeControl
            compact
            period="lifetime"
            periodValue={null}
            startDate=""
            endDate=""
            metric="plays"
            onChange={onRangeChange}
          />
        )}
        filters={{} as never}
        apiParams={{ period: 'year' }}
        fetchPage={vi.fn()}
        fetchPlayDates={vi.fn()}
      />,
    )

    expect(screen.queryByRole('heading', { name: '播放统计' })).not.toBeInTheDocument()
    expect(screen.queryByText('Playback Stats')).not.toBeInTheDocument()
    expect(screen.getAllByRole('article')).toHaveLength(8)
    expect(screen.getByText('已听歌曲')).toBeInTheDocument()
    expect(screen.getByText('已听专辑')).toBeInTheDocument()
    expect(screen.getByText('已听艺人')).toBeInTheDocument()
    expect(screen.queryByText('更多数据')).not.toBeInTheDocument()
    expect(screen.queryByText('有效事件')).not.toBeInTheDocument()
    const timeTrigger = screen.getByRole('button', { name: '选择时间范围，当前全部时间' })
    expect(timeTrigger).toHaveClass('mobile-time-range-trigger-compact')
    expect(timeTrigger.closest('.mobile-analysis-floating-time-control')).not.toBeNull()
    expect(screen.getByRole('heading', { name: '时间分布' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '星期分布' })).not.toBeInTheDocument()
    const dailyChart = screen.getByRole('heading', { name: '每日播放' }).closest('.mobile-chart-card')
    const page = document.querySelector('[data-mobile-page="analysis-stats"]')
    expect([...page!.children].indexOf(dailyChart!)).toBeGreaterThan(0)
    await user.click(screen.getByRole('button', { name: '选择时间范围，当前全部时间' }))
    const timeDialog = screen.getByRole('dialog', { name: '时间范围' })
    expect(within(timeDialog).getByRole('radiogroup', { name: '统计口径' })).toBeInTheDocument()
    await user.click(within(timeDialog).getByRole('radio', { name: '播放时长' }))
    await user.click(within(timeDialog).getByRole('button', { name: '应用时间范围' }))
    expect(onRangeChange).toHaveBeenCalledWith(expect.objectContaining({ metric: 'hours' }))
    expect(screen.getByTestId('recent-plays')).toHaveTextContent('mobile')
    await user.click(screen.getByRole('switch', { name: '累计' }))
    expect(screen.getByRole('heading', { name: '累计播放' })).toBeInTheDocument()

    const fullscreenTrigger = screen.getByRole('button', { name: '全屏查看累计播放' })
    await user.click(fullscreenTrigger)
    expect(screen.getByRole('dialog', { name: '累计播放' })).toBeInTheDocument()
    expect(document.body.style.overflow).toBe('hidden')
    await user.click(screen.getByRole('button', { name: '关闭累计播放全屏图表' }))
    expect(screen.queryByRole('dialog', { name: '累计播放' })).not.toBeInTheDocument()
    await waitFor(() => expect(fullscreenTrigger).toHaveFocus())
  })

  it('keeps same-named albums by different artists separate when computing movement', () => {
    const current = { album_name: 'Home', artist_name: 'Artist A', rank: 4, play_count: 10 } as WeeklyAlbumEntry
    const differentArtistPrevious = { album_name: 'Home', artist_name: 'Artist B', rank: 3, play_count: 11 } as WeeklyAlbumEntry
    const sameArtistHistorical = { album_name: 'Home', artist_name: 'Artist A', rank: 8, play_count: 6 } as WeeklyAlbumEntry

    expect(computeWeeklyRankChange(current, [differentArtistPrevious], [], 'albums')).toEqual({ type: 'new' })
    expect(computeWeeklyRankChange(current, [differentArtistPrevious], [sameArtistHistorical], 'albums')).toEqual({ type: 're' })
  })

  it('exposes weekly PK and chart weeks and selects a historical week from the sheet', async () => {
    const user = userEvent.setup()
    const onGoToWeek = vi.fn()
    const entry: WeeklyTrackEntry = {
      billboard_week: '2026-08-03',
      track_id: 7,
      track_name: 'Current Song',
      artist_name: 'Current Artist',
      album_name: 'Current Album',
      play_count: 28,
      total_ms: 1,
      rank: 4,
      running_peak: 2,
      running_wks: 7,
      running_peak_wks: 1,
      cover_url: null,
    }
    const secondEntry: WeeklyTrackEntry = {
      ...entry,
      track_id: 8,
      track_name: 'Second Song',
      play_count: 12,
      rank: 5,
      running_peak: 5,
      running_wks: 1,
    }
    const data = {
      meta: { all_weeks_desc: ['2026-08-03', '2026-07-27'] },
      weekly: [entry, secondEntry],
      weekly_album: [],
      weekly_artist: [],
    } as unknown as BillboardWeeklyResponse

    render(
      <MemoryRouter>
        <MobileBillboardWeekly
          data={data}
          activeTab="tracks"
          onTabChange={vi.fn()}
          selectedWeek="2026-08-03"
          currentIndex={0}
          totalWeeks={2}
          onPreviousWeek={vi.fn()}
          onNextWeek={vi.fn()}
          onGoToWeek={onGoToWeek}
          entries={[entry, secondEntry]}
          previousEntries={[]}
          historicalEntries={[]}
          summary={{ maxPlays: 28, totalPlays: 40, newCount: 2, reCount: 0, total: 2 }}
        />
      </MemoryRouter>,
    )

    const row = screen.getByRole('link', { name: /Current Song/ })
    expect(screen.getByRole('link', { name: /Second Song/ })).toBeInTheDocument()
    expect(within(row).getByText('Peak 2')).toBeInTheDocument()
    expect(within(row).getByText('在榜 7周')).toBeInTheDocument()
    expect(within(row).getByText('峰值 1周')).toBeInTheDocument()
    expect(within(row).getByText('NEW')).toHaveClass('text-[#3B5998]')
    expect(document.querySelector('.mobile-billboard-summary-compact')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 2, name: '完整周榜' })).not.toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: '列表分页' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Week 32, 2026' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 1, name: '本周榜单' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /选择榜单周次：Week 32, 2026/ }))
    const dialog = screen.getByRole('dialog', { name: '选择榜单周次' })
    await user.click(within(dialog).getByRole('button', { name: '上一个月' }))
    await user.click(within(dialog).getByRole('button', { name: 'Monday, July 27th, 2026' }))
    expect(onGoToWeek).toHaveBeenCalledWith('2026-07-27')
    expect(screen.queryByRole('dialog', { name: '选择榜单周次' })).not.toBeInTheDocument()
  })

  it('uses the selected week as the historical weekly-chart title too', () => {
    const data = {
      meta: { all_weeks_desc: ['2026-08-03', '2026-07-27'] },
      weekly: [],
      weekly_album: [],
      weekly_artist: [],
    } as unknown as BillboardWeeklyResponse
    render(
      <MemoryRouter>
        <MobileBillboardWeekly
          data={data}
          activeTab="tracks"
          onTabChange={vi.fn()}
          selectedWeek="2026-07-27"
          currentIndex={1}
          totalWeeks={2}
          onPreviousWeek={vi.fn()}
          onNextWeek={vi.fn()}
          onGoToWeek={vi.fn()}
          entries={[]}
          previousEntries={[]}
          historicalEntries={[]}
          summary={{ maxPlays: 0, totalPlays: 0, newCount: 0, reCount: 0, total: 0 }}
        />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { level: 1, name: 'Week 31, 2026' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 1, name: '本周榜单' })).not.toBeInTheDocument()
  })
})
