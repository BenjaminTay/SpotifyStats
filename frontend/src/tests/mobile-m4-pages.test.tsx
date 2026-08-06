import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { MobileSectionSwitcher } from '@/components/mobile'
import { MiniRankTable as PlaybackMiniRankTable } from '@/features/analysis/records/PlaybackRecordsPrimitives'
import { MobileAllTime } from '@/features/mobile/billboard/MobileAllTime'
import { MobileNumberOnes } from '@/features/mobile/billboard/MobileNumberOnes'
import { MobileVersusScoreboard } from '@/features/mobile/billboard/MobileVersusScoreboard'
import { MobileYearEnd } from '@/features/mobile/billboard/MobileYearEnd'
import { YearlyPeriodNotice } from '@/features/mobile/yearly/YearlyPeriodNotice'
import type { NumberOnesComputed, YearFilteredNumberOnes } from '@/features/billboard/number-ones/numberOnesData'
import type { BillboardYearEndResponse, VersusEntityData } from '@/types/billboard'
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
    await user.click(screen.getByRole('button', { name: /展开完整榜单/ }))
    expect(screen.getAllByRole('article')).toHaveLength(5)
  })

  it('renders Number Ones as a year-scoped timeline plus fixed Top 10 ranks', () => {
    const computed = {
      trackNo1WeeksSorted: [{ track_id: 1, track_name: 'Champion', artist_name: 'Artist', cover_url: null, weeks_at_no1: 4, power_score: 10, total_no1_plays: 40, longest_streak: 3, no1_weeks: [] }],
      albumNo1WeeksSorted: [], artistNo1WeeksSorted: [], trackNo1List: [], albumNo1List: [], artistNo1List: [],
      trackLongest: { name: 'Champion', artist: 'Artist', streak: 3 }, albumLongest: { name: '', artist: '', streak: 0 }, artistLongest: { name: '', streak: 0 },
      trackAnnualNo1: [], albumAnnualNo1: [], albumNo1WithPkWks: [], artistNo1WithPkWks: [], trackMaxPlays: 20, albumMaxPlays: 1, artistMaxPlays: 1,
    } as NumberOnesComputed
    const yearFiltered = {
      tracks: [{ billboard_week: '2026-08-03', track_id: 1, track_name: 'Champion', artist_name: 'Artist', album_name: 'Album', play_count: 20, total_ms: 1, rank: 1, running_peak: 1, running_wks: 3, running_peak_wks: 2, cover_url: null }],
      albums: [], artists: [], trackMaxPlays: 20, albumMaxPlays: 1, artistMaxPlays: 1, uniqueTrackCount: 1, uniqueAlbumCount: 0, uniqueArtistCount: 0,
    } as YearFilteredNumberOnes
    render(<MemoryRouter><MobileNumberOnes activeTab="tracks" onTabChange={vi.fn()} computed={computed} yearFiltered={yearFiltered} availableYears={[2026]} selectedYear={2026} onYearChange={vi.fn()} /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: '每周冠军时间线' })).toBeInTheDocument()
    expect(screen.getByText(/2026\/8\/3/)).toBeInTheDocument()
    expect(screen.getByText('最长连冠 3周')).toBeInTheDocument()
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

  it('uses field presets for All-Time and vertical entity cards for Versus', () => {
    const row = { track_id: 9, track_name: 'Fixed Rank', artist_name: 'Artist', album_name: 'Album', cover_url: null, weeks_on_chart: 7, peak_position: 3, weeks_at_peak: 1, weeks_top5: 3, weeks_top10: 5, power_score: 120, power_rank: 41, total_chart_plays: 90, is_debut_no1: false }
    const { rerender } = render(<MemoryRouter><MobileAllTime activeTab="tracks" rows={[row]} total={99} searchQuery="" peakFilter="all" sortKey="power_score" sortDir="desc" visibleColumnIds={['power_score', 'power_rank', 'weeks_on_chart']} page={1} pageSize={20} onTabChange={vi.fn()} onSearchChange={vi.fn()} onPeakFilterChange={vi.fn()} onSortChange={vi.fn()} onVisibleColumnsChange={vi.fn()} onPageChange={vi.fn()} /></MemoryRouter>)
    expect(screen.getByText('41')).toBeInTheDocument()
    expect(screen.getByText('走势排名 #41')).toBeInTheDocument()

    const entities = [{ name: 'Winner', cover_url: null }, { name: 'Runner-up', cover_url: null }] as VersusEntityData[]
    rerender(<MemoryRouter><MobileVersusScoreboard entities={entities} detailLinks={['/one', '/two']} groups={[{ label: '榜单成绩', metrics: [{ label: '走势点数', values: ['120', '90'], winners: [0] }] }]} personalMetrics={[]} wins={[1, 0]} personalLoading={false} /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Winner' })).toBeInTheDocument()
    expect(screen.getAllByRole('article')).toHaveLength(2)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})
