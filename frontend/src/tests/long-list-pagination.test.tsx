import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { AllTimeTable } from '@/features/billboard/all-time/AllTimeTable'
import type { AllTimeRow, ColumnDef, MergedTrackRow } from '@/features/billboard/all-time/allTimeData'
import { MiniRankTable } from '@/features/billboard/records/RecordsPrimitives'

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
})
