import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { AllTimeTable } from '@/features/billboard/all-time/AllTimeTable'
import type { AllTimeRow, ColumnDef, MergedTrackRow } from '@/features/billboard/all-time/allTimeData'
import { YearEndTable } from '@/features/billboard/year-end/YearEndTable'
import { MiniRankTable } from '@/features/billboard/records/RecordsPrimitives'
import { recentPlayRowKey } from '@/components/shared/recentPlaysUtils'
import type { RecentPlayRow } from '@/types/analysis'
import type { BillboardYearEndTrackRow } from '@/types/billboard'

describe('Phase 5 long-list pagination', () => {
  it('renders only the current page for Records mini rank tables', () => {
    const rows = Array.from({ length: 25 }, (_, index) => ({
      name: `Record ${index + 1}`,
      value: index + 1,
    }))

    render(
      <MiniRankTable
        rows={rows}
        columns={[
          { header: 'Name', render: (row) => <span>{row.name}</span> },
          { header: 'Value', render: (row) => <span>{row.value}</span> },
        ]}
      />,
    )

    expect(screen.getByText('Record 1')).toBeInTheDocument()
    expect(screen.getByText('Record 10')).toBeInTheDocument()
    expect(screen.queryByText('Record 11')).not.toBeInTheDocument()
    expect(screen.queryByText('Record 25')).not.toBeInTheDocument()

    fireEvent.click(screen.getAllByRole('button')[2])

    expect(screen.queryByText('Record 1')).not.toBeInTheDocument()
    expect(screen.getByText('Record 11')).toBeInTheDocument()
    expect(screen.getByText('Record 20')).toBeInTheDocument()
  })

  it('renders only the current page for all-time Billboard tables', () => {
    const rows: MergedTrackRow[] = Array.from({ length: 25 }, (_, index) => ({
      track_id: index + 1,
      track_name: `Track ${index + 1}`,
      artist_name: `Artist ${index + 1}`,
      artist_names: [`Artist ${index + 1}`],
      album_name: `Album ${index + 1}`,
      cover_url: null,
      peak_position: index + 1,
      weeks_at_peak: 1,
      weeks_on_chart: 1,
      weeks_top5: 1,
      weeks_top10: 1,
      power_score: 100 - index,
      power_rank: index + 1,
      total_chart_plays: 1000 - index,
      is_debut_no1: false,
    }))
    const columns: ColumnDef<AllTimeRow>[] = [
      {
        key: 'total_chart_plays',
        label: '播放',
        group: '个人数据',
        defaultVisible: true,
        minWidth: 100,
        mobilePriority: 1,
        align: 'right',
        getValue: (row) => (row as MergedTrackRow).total_chart_plays,
        format: (row) => String((row as MergedTrackRow).total_chart_plays),
        sortable: true,
      },
    ]

    render(
      <MemoryRouter>
        <AllTimeTable
          activeTab="tracks"
          rows={rows}
          columns={columns}
          total={rows.length}
          sortKey="total_chart_plays"
          sortDir="desc"
          page={1}
          pageSize={10}
          maxBarValue={1000}
          onColumnClick={vi.fn()}
          onPageChange={vi.fn()}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('Track 1')).toBeInTheDocument()
    expect(screen.getByText('Track 10')).toBeInTheDocument()
    expect(screen.queryByText('Track 11')).not.toBeInTheDocument()
    expect(screen.queryByText('Track 25')).not.toBeInTheDocument()
  })

  it('paginates Billboard Year-End rows', () => {
    const rows: BillboardYearEndTrackRow[] = Array.from({ length: 75 }, (_, index) => ({
      track_id: index + 1,
      track_name: `Year-End Track ${index + 1}`,
      artist_name: 'Artist',
      artist_names: ['Artist'],
      album_name: 'Album',
      cover_url: null,
      year_end_score: 1000 - index,
      year_end_rank: index + 1,
      peak_position: 1,
      weeks_on_chart: 10,
      weeks_at_peak: 2,
      weeks_at_no1: 1,
      weeks_top5: 6,
      weeks_top10: 10,
      chart_plays: 200 - index,
      annual_plays: 220 - index,
      first_week: '2025-01-03',
      last_week: '2025-03-07',
      true_first_week: '2025-01-03',
      is_true_debut_no1: index === 0,
    }))

    function Wrapper() {
      const [page, setPage] = useState(1)
      return <YearEndTable tab="tracks" rows={rows} page={page} pageSize={50} onPageChange={setPage} />
    }

    render(
      <MemoryRouter>
        <Wrapper />
      </MemoryRouter>,
    )

    expect(screen.getByText('Year-End Track 1')).toBeInTheDocument()
    expect(screen.getByText('显示 1–50 / 总数 75 条')).toBeInTheDocument()
    expect(screen.queryByText('Year-End Track 75')).not.toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('下一页'))

    expect(screen.getByText('Year-End Track 75')).toBeInTheDocument()
    expect(screen.getByText('显示 51–75 / 总数 75 条')).toBeInTheDocument()
  })

  it('labels Billboard Year-End table metrics as annual and formats annual peak like rank numbers', () => {
    const rows: BillboardYearEndTrackRow[] = [
      {
        track_id: 1,
        track_name: 'Annual Peak Song',
        artist_name: 'Artist',
        artist_names: ['Artist'],
        album_name: 'Album',
        cover_url: null,
        year_end_score: 1000,
        year_end_rank: 12,
        peak_position: 1,
        weeks_on_chart: 10,
        weeks_at_peak: 2,
        weeks_at_no1: 1,
        weeks_top5: 6,
        weeks_top10: 10,
        chart_plays: 200,
        annual_plays: 240,
        first_week: '2025-01-03',
        last_week: '2025-03-07',
        true_first_week: '2025-01-03',
        is_true_debut_no1: false,
      },
    ]

    render(
      <MemoryRouter>
        <YearEndTable tab="tracks" rows={rows} page={1} pageSize={50} onPageChange={vi.fn()} />
      </MemoryRouter>,
    )

    for (const label of ['年度积分', '年度最高', '年度在榜', '年度#1周', '年度Top5', '年度Top10', '在榜播放']) {
      expect(screen.getByRole('button', { name: `按${label}排序` })).toBeInTheDocument()
    }
    expect(screen.queryByRole('button', { name: '按年度播放排序' })).not.toBeInTheDocument()

    const annualPeakCell = screen.getByText('01').closest('td')
    expect(annualPeakCell).toHaveClass('font-serif')
    expect(annualPeakCell).toHaveClass('text-[22px]')
    expect(annualPeakCell).toHaveClass('text-accent-foreground')
    expect(screen.queryByText('#1')).not.toBeInTheDocument()
  })

  it('insets Year-End metric columns before annual plays to keep the final metrics readable', () => {
    const rows: BillboardYearEndTrackRow[] = [
      {
        track_id: 1,
        track_name: 'Spacing Song',
        artist_name: 'Artist',
        artist_names: ['Artist'],
        album_name: 'Album',
        cover_url: null,
        year_end_score: 1000,
        year_end_rank: 12,
        peak_position: 1,
        weeks_on_chart: 37,
        weeks_at_peak: 2,
        weeks_at_no1: 4,
        weeks_top5: 8,
        weeks_top10: 14,
        chart_plays: 200,
        annual_plays: 240,
        first_week: '2025-01-03',
        last_week: '2025-03-07',
        true_first_week: '2025-01-03',
        is_true_debut_no1: false,
      },
    ]

    render(
      <MemoryRouter>
        <YearEndTable tab="tracks" rows={rows} page={1} pageSize={50} onPageChange={vi.fn()} />
      </MemoryRouter>,
    )

    expect(screen.getByText('14').closest('td')).toHaveClass('pr-5')
    expect(screen.getByText('8').closest('td')).toHaveClass('pr-5')
    expect(screen.getByText('200').closest('td')).not.toHaveClass('pr-5')
  })

  it('keeps recent-play row keys unique when entity joins return duplicate play ids', () => {
    const rows: RecentPlayRow[] = [
      {
        play_id: 2112807,
        ts: '2026-06-01T12:00:00Z',
        date: '2026-06-01',
        track_id: 42,
        track_name: 'Duplicate Key Song',
        artist_name: 'Artist One',
        artist_names: ['Artist One', 'Artist Two'],
        album_name: 'Join Edge Case',
        ms_played: 180000,
        hours: 0.05,
        platform: 'ios',
        cover_url: null,
      },
      {
        play_id: 2112807,
        ts: '2026-06-01T12:00:00Z',
        date: '2026-06-01',
        track_id: 42,
        track_name: 'Duplicate Key Song',
        artist_name: 'Artist Two',
        artist_names: ['Artist One', 'Artist Two'],
        album_name: 'Join Edge Case',
        ms_played: 180000,
        hours: 0.05,
        platform: 'ios',
        cover_url: null,
      },
    ]

    const keys = rows.map(recentPlayRowKey)

    expect(new Set(keys).size).toBe(rows.length)
  })
})
