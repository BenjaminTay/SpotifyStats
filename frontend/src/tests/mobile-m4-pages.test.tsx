import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { MobileSectionSwitcher } from '@/components/mobile'
import { ChartWeeksValue, MiniRankTable as BillboardMiniRankTable, PeakNum, RecordCard as BillboardRecordCard, SectionHeader as BillboardSectionHeader, TrackAlbumToggle } from '@/features/billboard/records/RecordsPrimitives'
import { ChampionshipSection } from '@/features/billboard/records/ChampionshipSection'
import { CuriositiesSection } from '@/features/billboard/records/CuriositiesSection'
import { MiniRankTable as PlaybackMiniRankTable } from '@/features/analysis/records/PlaybackRecordsPrimitives'
import { MobileAllTime } from '@/features/mobile/billboard/MobileAllTime'
import { MobileNumberOnes } from '@/features/mobile/billboard/MobileNumberOnes'
import { MobileVersusScoreboard } from '@/features/mobile/billboard/MobileVersusScoreboard'
import { MobileYearEnd } from '@/features/mobile/billboard/MobileYearEnd'
import { YearlyPeriodNotice } from '@/features/mobile/yearly/YearlyPeriodNotice'
import type { NumberOnesComputed, YearFilteredNumberOnes } from '@/features/billboard/number-ones/numberOnesData'
import type { ArtistTrackCounts, BillboardRecords, BillboardYearEndResponse, TrackSummary, VersusEntityData } from '@/types/billboard'
import type { PlaybackRecordRow } from '@/types/analysis'

beforeEach(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('max-width'),
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
})

describe('M4 mobile page presentations', () => {
  it('shows the effective cutoff for a partial current year and stays silent for a full year', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-08-06T00:00:00Z'))
    const { rerender } = render(<YearlyPeriodNotice period={{ year: 2026, start_date: '2026-01-01', end_date: '2026-07-24', latest_data_date: '2026-07-24', active_days: 205, days_covered: 205, is_partial_year: true, label: '2026 年截至 2026-07-24' }} />)
    expect(screen.getByRole('complementary', { name: '年度数据范围' })).toHaveTextContent('年度进行中')
    expect(screen.getByText('数据截至 2026-07-24')).toBeInTheDocument()

    rerender(<YearlyPeriodNotice period={{ year: 2025, start_date: '2025-01-01', end_date: '2025-12-31', latest_data_date: '2025-12-31', active_days: 300, days_covered: 365, is_partial_year: false, label: '2025 年全年' }} />)
    expect(screen.queryByRole('complementary', { name: '年度数据范围' })).not.toBeInTheDocument()
    vi.useRealTimers()
  })

  it('switches record families through the shared section sheet', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<MobileSectionSwitcher value="highlights" options={[{ value: 'highlights', label: '高光时刻' }, { value: 'reigns', label: '个人王朝' }]} onChange={onChange} />)
    await user.click(screen.getByRole('button', { name: /当前栏目/ }))
    const dialog = screen.getByRole('dialog', { name: '选择栏目' })
    await user.click(within(dialog).getByRole('option', { name: '个人王朝' }))
    expect(onChange).toHaveBeenCalledWith('reigns')
  })

  it('shows only a record Top 3 on phone until the full list is requested', async () => {
    const user = userEvent.setup()
    const rows = Array.from({ length: 5 }, (_, index) => ({ name: `纪录 ${index + 1}`, value: 10 - index })) as PlaybackRecordRow[]
    render(
      <MemoryRouter>
        <PlaybackMiniRankTable rows={rows} columns={[
          { header: '#', render: (_row, index) => index + 1 },
          { header: '名称', render: (row) => row.name },
          { header: '纪录值', render: (row) => row.value },
        ]} />
      </MemoryRouter>,
    )
    expect(screen.getAllByRole('article')).toHaveLength(3)
    await user.click(screen.getByRole('button', { name: /查看完整榜单/ }))
    expect(within(screen.getByRole('dialog', { name: '完整榜单' })).getAllByRole('article')).toHaveLength(5)
  })

  it('opens Billboard record lists in a bounded full-screen sheet', async () => {
    const user = userEvent.setup()
    const rows = Array.from({ length: 45 }, (_, index) => ({
      name: `榜单纪录 ${index + 1}`,
      value: 100 - index,
    }))

    render(
      <MemoryRouter initialEntries={['/billboard/records?family=market']}>
        <BillboardRecordCard title="每周播放量排行 · Weekly Total Plays" subtitle="桌面说明文字">
          <BillboardMiniRankTable rows={rows} columns={[
            { header: '#', render: (_row, index) => String(index + 1).padStart(2, '0') },
            { header: '周次', render: (row) => row.name },
            { header: '总播放', render: (row) => row.value },
          ]} />
        </BillboardRecordCard>
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '每周播放量排行' })).toBeInTheDocument()
    expect(screen.queryByText('Weekly Total Plays')).not.toBeInTheDocument()
    expect(screen.queryByText('桌面说明文字')).not.toBeInTheDocument()
    expect(screen.getAllByRole('article')).toHaveLength(3)

    await user.click(screen.getByRole('button', { name: /查看完整榜单/ }))
    const dialog = screen.getByRole('dialog', { name: '每周播放量排行' })
    expect(within(dialog).getAllByRole('article')).toHaveLength(20)
    expect(within(dialog).getByRole('button', { name: /加载更多/ })).toBeInTheDocument()

    await user.click(within(dialog).getByRole('button', { name: /加载更多/ }))
    expect(within(dialog).getAllByRole('article')).toHaveLength(40)
  })

  it('allows Billboard record section headers to omit subtitles', () => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
    const Icon = () => null

    render(<BillboardSectionHeader icon={Icon} title="冠军圣殿" />)

    expect(screen.getByRole('heading', { name: '冠军圣殿' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '冠军圣殿' }).nextElementSibling).toBeNull()
  })

  it('keeps record entity controls compact and pairs two headline metrics on the right', () => {
    render(
      <MemoryRouter>
        <BillboardRecordCard
          title="冠军名人堂"
          toggle={<TrackAlbumToggle value="track" onChange={vi.fn()} />}
        >
          <BillboardMiniRankTable
            rows={[{ artist: 'Artist', count: 9, weeks: 15 }]}
            columns={[
              { header: '#', render: () => '04' },
              { header: '艺人', render: (row) => row.artist },
              { header: '冠军单曲', mobileRole: 'primary', render: (row) => row.count },
              { header: '单曲冠周', mobileRole: 'secondary', render: (row) => `${row.weeks} 周` },
            ]}
          />
        </BillboardRecordCard>
      </MemoryRouter>,
    )

    expect(screen.getByRole('tablist', { name: '榜单实体类型' })).toHaveClass('mobile-record-entity-toggle')
    expect(document.querySelector('.mobile-record-card-header .mobile-record-card-actions')).not.toBeNull()
    expect(document.querySelector('.mobile-record-rank-primary')).toHaveTextContent('冠军单曲9')
    expect(document.querySelector('.mobile-record-rank-secondary')).toHaveTextContent('单曲冠周15 周')
    expect(document.querySelector('.mobile-record-rank-metrics')).toHaveClass('mobile-record-rank-metrics-paired')
  })

  it('shows natural Peak numbers and reuses the standard record week metric on phone', () => {
    render(
      <MemoryRouter>
        <BillboardRecordCard title="全时段单曲排行">
          <BillboardMiniRankTable
            rows={[{ name: 'Song', peak: 3, weeks: 7 }]}
            columns={[
              { header: '#', render: () => '01' },
              { header: '单曲', render: (row) => row.name },
              { header: 'Peak', render: (row) => <PeakNum rank={row.peak} /> },
              { header: '在榜', render: (row) => <ChartWeeksValue value={row.weeks} /> },
            ]}
          />
        </BillboardRecordCard>
      </MemoryRouter>,
    )

    const row = screen.getByRole('article')
    expect(within(row).getByText('3')).toBeInTheDocument()
    expect(within(row).queryByText('03')).not.toBeInTheDocument()
    expect(row.querySelector('.mobile-record-value')).toHaveTextContent('7周')
    expect(row.querySelector('.mobile-record-chart-weeks')).toBeNull()
  })

  it('allows selected record lists to preview four rows before opening the full sheet', () => {
    const rows = Array.from({ length: 6 }, (_, index) => ({ name: `阻挡纪录 ${index + 1}`, value: 6 - index }))
    render(
      <MemoryRouter>
        <BillboardRecordCard title="阻挡王">
          <BillboardMiniRankTable
            rows={rows}
            mobilePreviewCount={4}
            columns={[
              { header: '#', render: (_row, index) => index + 1 },
              { header: '歌曲', render: (row) => row.name },
              { header: '阻挡数', render: (row) => row.value },
            ]}
          />
        </BillboardRecordCard>
      </MemoryRouter>,
    )

    expect(screen.getAllByRole('article')).toHaveLength(4)
    expect(screen.getByRole('button', { name: /查看完整榜单/ })).toBeInTheDocument()
  })

  it('shows artists on replacement tracks and covers on blocked-track links', () => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
    const records = {
      artist_most_no1: [],
      artist_most_no1_album: [],
      debut_no1: [],
      debut_no1_album: [],
      return_to_no1: [],
      return_to_no1_album: [],
      return_to_no1_artist: [],
      self_replacement_no1: [{ '艺人': 'Artist', '前冠单_id': 1, '前冠单': 'Previous Song', '新冠单_id': 3, '新冠单': 'New Song' }],
      self_replacement_no1_album: [],
      blocker_king: [{ track_id: 1, track_name: 'Champion', artist_name: 'Artist', '阻挡数': 1, '走势评分': 0 }],
      blocked_tracks_map: { 1: [{ track_id: 2, track_name: 'Blocked Song', artist_name: 'Challenger' }] },
      blocker_king_album: [],
      blocked_albums_map: {},
      blocker_king_artist: [],
      blocked_artists_map: {},
      longest_to_no1: [],
      longest_to_no1_album: [],
      longest_to_no1_artist: [],
    } as unknown as BillboardRecords

    const covers = {
      track: new Map([[1, '/previous.jpg'], [2, '/blocked.jpg'], [3, '/new.jpg']]),
      album: new Map(),
      artist: new Map(),
    }
    const { container } = render(<MemoryRouter><ChampionshipSection rec={records} covers={covers} /></MemoryRouter>)

    expect(screen.getByRole('link', { name: 'Previous Song' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'New Song' })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Artist' })).toHaveLength(4)
    expect(container.querySelectorAll('.championship-replacement-arrow')).toHaveLength(1)
    expect(container.querySelector('.championship-replacement-arrow')?.closest('td')).toHaveStyle({ width: '72px' })
    const blockedLink = screen.getByRole('link', { name: 'Blocked Song' })
    expect(blockedLink).toHaveAttribute('href', expect.stringContaining('/music/tracks/2'))
    expect(blockedLink.querySelector('img')).toHaveAttribute('src', '/blocked.jpg')
  })

  it('renders double and triple chart events as equal aligned achievement rows on phone', () => {
    const records = {
      week_total_plays: [
        { billboard_week: '2026-06-12', total_plays: 126 },
        { billboard_week: '2026-07-17', total_plays: 177 },
      ],
      double_debut: [{
        debut_track_id: 1,
        debut_track: 'stupid song',
        debut_artist: 'Olivia Rodrigo',
        debut_week: '2026-06-12',
        debut_album: 'you seem pretty sad for a girl so in love',
      }],
      triple_no1: [{
        billboard_week: '2026-07-17',
        '艺人': '单依纯',
        track_id: 2,
        '歌曲': '我表示理解',
        '专辑': '纯妹妹',
      }],
    } as unknown as BillboardRecords

    render(
      <MemoryRouter>
        <CuriositiesSection
          rec={records}
          covers={{
            track: new Map([[1, '/track-1.jpg'], [2, '/track-2.jpg']]),
            album: new Map([['you seem pretty sad for a girl so in love', '/album-1.jpg'], ['纯妹妹', '/album-2.jpg']]),
            artist: new Map([['单依纯', '/artist-1.jpg']]),
          }}
          trackSummary={[
            {
              track_id: 10, track_name: 'A', artist_name: 'First Artist', album_name: 'First Album',
              peak_position: 1, weeks_on_chart: 3, weeks_at_peak: 1, first_week: '2022-01-07', last_week: '2022-01-21',
              total_chart_plays: 20, total_plays: 20, weeks_at_no1: 1, first_peak_week: '2022-01-07', is_debut_no1: true,
            },
            {
              track_id: 11, track_name: 'A very long track name', artist_name: 'Latest Artist', album_name: 'Latest Album',
              peak_position: 2, weeks_on_chart: 2, weeks_at_peak: 1, first_week: '2026-07-17', last_week: '2026-07-24',
              total_chart_plays: 10, total_plays: 10, weeks_at_no1: 0, first_peak_week: '2026-07-17', is_debut_no1: false,
            },
          ] satisfies TrackSummary[]}
          artistTrackCounts={[
            {
              artist_name: 'Taylor Swift', total_tracks: 301, best_peak: 1, total_weeks: 1849, avg_weeks: 6,
              top1: 34, top5: 80, top10: 120, best_peak_track: 'Opalite', weeks_at_no1: 50,
              num_no1_albums: 10, album_no1_weeks: 30, artist_chart_no1_weeks: 20,
            },
          ] satisfies ArtistTrackCounts[]}
        />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: '双榜空降' })).toBeInTheDocument()
    expect(screen.queryByText('同张专辑有两首歌曲空降入榜')).not.toBeInTheDocument()
    const events = document.querySelectorAll('.mobile-curiosity-event')
    expect(events).toHaveLength(2)
    expect(events[0]?.querySelectorAll('.mobile-curiosity-achievement-row')).toHaveLength(2)
    expect(events[1]?.querySelectorAll('.mobile-curiosity-achievement-row')).toHaveLength(3)
    expect(events[0]?.querySelectorAll('.mobile-curiosity-chart-rank')).toHaveLength(2)
    expect(events[1]?.querySelectorAll('.mobile-curiosity-chart-rank')).toHaveLength(3)
    expect(within(events[1] as HTMLElement).getByRole('link', { name: '单曲榜冠军：我表示理解' })).toBeInTheDocument()
    expect(within(events[1] as HTMLElement).getByRole('link', { name: '专辑榜冠军：纯妹妹' })).toBeInTheDocument()
    expect(within(events[1] as HTMLElement).getByRole('link', { name: '艺人榜冠军：单依纯' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '最早上榜' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '最新上榜' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '最长歌名' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '最短歌名' })).not.toBeInTheDocument()
    expect(screen.getByText('最早入榜')).toBeInTheDocument()
    expect(screen.getByText('最新入榜')).toBeInTheDocument()
    expect(screen.getByText('最长歌名')).toBeInTheDocument()
    expect(screen.getByText('最短歌名')).toBeInTheDocument()
    const extremes = screen.getByRole('region', { name: '榜单极值纪录' })
    expect(within(extremes).getAllByRole('link')).toHaveLength(4)
    const prolificRow = screen.getByRole('link', { name: 'Taylor Swift' }).closest('article')
    expect(prolificRow).not.toBeNull()
    expect(prolificRow?.querySelectorAll('.mobile-record-value')).toHaveLength(3)
    expect(prolificRow).toHaveTextContent('34')
    expect(prolificRow).toHaveTextContent('1,849周')
  })

  it('renders Number Ones as a year-scoped timeline plus fixed Top 10 ranks', () => {
    const computed = {
      trackNo1WeeksSorted: [{ track_id: 1, track_name: 'Champion', artist_name: 'Artist', cover_url: null, weeks_at_no1: 4, power_score: 10, total_no1_plays: 40, longest_streak: 3, no1_weeks: [] }],
      albumNo1WeeksSorted: [], artistNo1WeeksSorted: [], trackNo1List: [], albumNo1List: [], artistNo1List: [],
      trackLongest: { name: 'Champion', artist: 'Artist', streak: 3 }, albumLongest: { name: '', artist: '', streak: 0 }, artistLongest: { name: '', streak: 0 },
      albumNo1WithPkWks: [], artistNo1WithPkWks: [], trackMaxPlays: 20, albumMaxPlays: 1, artistMaxPlays: 1,
    } as NumberOnesComputed
    const yearFiltered = {
      tracks: [{ billboard_week: '2026-08-03', track_id: 1, track_name: 'Champion', artist_name: 'Artist', album_name: 'Album', play_count: 20, total_ms: 1, rank: 1, running_peak: 1, running_wks: 3, running_peak_wks: 2, cover_url: '/covers/tracks/1.jpg' }],
      albums: [], artists: [], trackMaxPlays: 20, albumMaxPlays: 1, artistMaxPlays: 1, uniqueTrackCount: 1, uniqueAlbumCount: 0, uniqueArtistCount: 0,
    } as YearFilteredNumberOnes
    render(<MemoryRouter><MobileNumberOnes activeTab="tracks" onTabChange={vi.fn()} computed={computed} yearFiltered={yearFiltered} availableYears={[2026]} selectedYear={2026} onYearChange={vi.fn()} /></MemoryRouter>)
    const timeline = screen.getByRole('heading', { name: '每周冠军' }).closest('section')
    expect(timeline).not.toBeNull()
    expect(within(timeline!).getByText('2026 独特冠军')).toBeInTheDocument()
    expect(within(timeline!).getByLabelText('选择冠军年份')).toBeInTheDocument()
    expect(screen.getByText(/2026\/8\/3/)).toBeInTheDocument()
    expect(screen.getByText('最长连冠 3周')).toBeInTheDocument()
    expect(screen.queryByText('全时段冠军')).not.toBeInTheDocument()
    expect(document.querySelector('.mobile-number-one-timeline .mobile-entity-artwork-track img')).toHaveAttribute('src', '/covers/tracks/1.jpg')
  })

  it('keeps Year-End original rank while sorting controls live in a sheet', async () => {
    const user = userEvent.setup()
    const row = { track_id: 2, track_name: 'Year Song', artist_name: 'Artist', cover_url: null, year_end_rank: 41, year_end_score: 800, peak_position: 2, weeks_on_chart: 12, weeks_at_no1: 0, weeks_at_peak: 1, weeks_top5: 3, weeks_top10: 6, chart_plays: 99, annual_plays: 120, first_week: '2026-01-05', last_week: '2026-08-03', is_true_debut_no1: false }
    const data = { meta: { observed_weeks: 20, expected_weeks: 52, is_complete_year: false }, honors: {}, tracks: [row], albums: [], artists: [] } as unknown as BillboardYearEndResponse
    const onSort = vi.fn()
    render(<MemoryRouter><MobileYearEnd data={data} selectedYear={2026} availableYears={[2026]} coverageMessage="截至当前的阶段年榜" activeTab="tracks" rows={[row]} sortKey="year_end_score" sortDir="desc" page={1} pageSize={20} onYearChange={vi.fn()} onTabChange={vi.fn()} onSortChange={onSort} onPageChange={vi.fn()} /></MemoryRouter>)
    expect(screen.getByText('41')).toBeInTheDocument()
    expect(screen.getByText('截至当前的阶段年榜')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /年度积分 · 降序/ }))
    await user.click(within(screen.getByRole('dialog', { name: '选择年榜排序' })).getByRole('option', { name: /年度最高排名/ }))
    expect(onSort).toHaveBeenCalledWith('peak_position')
  })

  it('uses field presets for All-Time and a comparison matrix for Versus', () => {
    const row = { track_id: 9, track_name: 'Fixed Rank', artist_name: 'Artist', album_name: 'Album', cover_url: null, weeks_on_chart: 7, peak_position: 3, weeks_at_peak: 1, weeks_top5: 3, weeks_top10: 5, power_score: 120, power_rank: 41, total_chart_plays: 90, is_debut_no1: false }
    const { rerender } = render(<MemoryRouter><MobileAllTime activeTab="tracks" rows={[row]} total={99} searchQuery="" peakFilter="all" sortKey="power_score" sortDir="desc" visibleColumnIds={['power_score', 'power_rank', 'weeks_on_chart']} page={1} pageSize={20} onTabChange={vi.fn()} onSearchChange={vi.fn()} onPeakFilterChange={vi.fn()} onSortChange={vi.fn()} onVisibleColumnsChange={vi.fn()} onPageChange={vi.fn()} /></MemoryRouter>)
    expect(screen.getByText('41')).toBeInTheDocument()
    expect(screen.getByText('走势排名 #41')).toBeInTheDocument()

    const entities = [{ name: 'Winner', cover_url: null }, { name: 'Runner-up', cover_url: null }] as VersusEntityData[]
    rerender(<MemoryRouter><MobileVersusScoreboard entities={entities} detailLinks={['/one', '/two']} groups={[{ label: '榜单成绩', metrics: [{ label: '走势点数', values: ['120', '90'], winners: [0] }] }]} personalMetrics={[]} wins={[1, 0]} personalLoading={false} /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Winner' })).toBeInTheDocument()
    const matrix = screen.getByRole('table', { name: '移动端对决指标矩阵' })
    expect(within(matrix).getByText('走势点数')).toBeInTheDocument()
    expect(within(matrix).getByText('120')).toBeInTheDocument()
    expect(within(matrix).getByText('90')).toBeInTheDocument()
    expect(screen.queryByText('实体详情')).not.toBeInTheDocument()
  })
})
