import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AllTimeControls } from '@/features/billboard/all-time/AllTimeControls'
import { AllTimeTable, Pagination } from '@/features/billboard/all-time/AllTimeTable'
import { AllTimeToolbar } from '@/features/billboard/all-time/AllTimeToolbar'
import {
  recommendedVisibleColumnIds,
  getColumnsForTab,
  loadVisibleColumnIds,
  saveVisibleColumnIds,
  sanitizeVisibleColumnIds,
  selectAllTimeRows,
  visibleColumnsForTab,
  type AllTimeRows,
  type MergedAlbumRow,
  type MergedArtistRow,
  type MergedTrackRow,
} from '@/features/billboard/all-time/allTimeData'

const track: MergedTrackRow = {
  track_id: 1,
  track_name: 'Cruel Summer',
  artist_name: 'Taylor Swift',
  artist_names: ['Taylor Swift'],
  album_name: 'Lover',
  cover_url: null,
  weeks_on_chart: 10,
  peak_position: 1,
  weeks_at_peak: 2,
  weeks_top5: 5,
  weeks_top10: 9,
  power_score: 900,
  power_rank: 7,
  total_chart_plays: 300,
  is_debut_no1: false,
}

const album: MergedAlbumRow = {
  album_name: 'GUTS',
  artist_name: 'Olivia Rodrigo',
  cover_url: null,
  weeks_on_chart: 8,
  peak_position: 1,
  weeks_at_peak: 1,
  weeks_top5: 4,
  weeks_top10: 8,
  total_tracks: 9,
  top1_tracks: 4,
  top5_tracks: 6,
  top10_tracks: 8,
  track_power_sum: 12345,
  track_power_rank: 2,
  power_score: 800,
  power_rank: 4,
  total_plays: 500,
  is_debut_no1: false,
}

const artist: MergedArtistRow = {
  artist_name: 'SZA',
  cover_url: null,
  weeks_on_chart: 9,
  peak_position: 2,
  weeks_at_peak: 2,
  weeks_top5: 6,
  weeks_top10: 9,
  total_tracks: 12,
  top1_tracks: 2,
  top5_tracks: 7,
  top10_tracks: 10,
  num_no1_albums: 1,
  top5_albums: 2,
  top10_albums: 3,
  track_power_sum: 22345,
  track_power_rank: 3,
  album_power_sum: 10345,
  album_power_rank: 4,
  power_score: 700,
  power_rank: 5,
  total_plays: 650,
  is_debut_no1: false,
}

const rows: AllTimeRows = { tracks: [track], albums: [album], artists: [artist] }

describe('Billboard all-time search and column schema', () => {
  beforeEach(() => localStorage.clear())

  it('matches the documented fields without changing the original full-chart rank', () => {
    expect(selectAllTimeRows(rows, 'tracks', 'all', 'power_score', 'desc', 'lover').rows).toEqual([track])
    expect(selectAllTimeRows(rows, 'tracks', 'all', 'power_score', 'desc', 'TAYLOR').rows).toEqual([track])
    expect(selectAllTimeRows(rows, 'albums', 'all', 'power_score', 'desc', 'olivia').rows).toEqual([album])
    expect(selectAllTimeRows(rows, 'artists', 'all', 'power_score', 'desc', 'sza').rows).toEqual([artist])
    expect(selectAllTimeRows(rows, 'albums', 'all', 'power_score', 'desc', 'missing').rows).toEqual([])
    expect(album.power_rank).toBe(4)
  })

  it('keeps fixed columns, ignores obsolete ids, migrates legacy arrays, and persists tabs independently', () => {
    const sanitized = sanitizeVisibleColumnIds('albums', ['top10_tracks', 'removed_column'])
    expect(sanitized).toContain('top10_tracks')
    expect(sanitized).not.toContain('removed_column')

    localStorage.setItem('spotify_stats_billboard_all_time_columns:tracks', JSON.stringify(['weeks_top5']))
    expect(loadVisibleColumnIds('tracks')).toEqual(expect.arrayContaining(['power_rank', 'weeks_top5']))

    localStorage.setItem('spotify_stats_billboard_all_time_columns:tracks', JSON.stringify({
      version: 2,
      visible: ['weeks_top5'],
    }))
    expect(loadVisibleColumnIds('tracks')).toEqual(['weeks_top5'])

    saveVisibleColumnIds('albums', ['track_power_sum'])
    saveVisibleColumnIds('artists', ['album_power_sum'])
    expect(loadVisibleColumnIds('albums')).toEqual(['track_power_sum'])
    expect(loadVisibleColumnIds('artists')).toEqual(['album_power_sum'])
    expect(visibleColumnsForTab('albums', loadVisibleColumnIds('albums')).map((column) => column.key))
      .not.toContain('album_power_sum')
  })

  it('uses the requested recommendation and exposes every score/rank as an independent right-aligned field', () => {
    expect(recommendedVisibleColumnIds('tracks')).toEqual([
      'peak_position', 'weeks_at_peak', 'weeks_on_chart', 'power_score', 'power_rank', 'total_chart_plays',
    ])
    expect(recommendedVisibleColumnIds('albums')).toEqual([
      'peak_position', 'weeks_at_peak', 'weeks_on_chart', 'total_tracks', 'top1_tracks',
      'track_power_sum', 'track_power_rank', 'power_score', 'power_rank', 'total_plays',
    ])
    expect(recommendedVisibleColumnIds('artists')).toEqual([
      'peak_position', 'weeks_at_peak', 'weeks_on_chart', 'total_tracks', 'top1_tracks',
      'track_power_sum', 'track_power_rank', 'num_no1_albums', 'album_power_sum',
      'album_power_rank', 'power_score', 'power_rank', 'total_plays',
    ])

    const labels = Object.fromEntries(getColumnsForTab('artists').map((column) => [column.key, column.label]))
    expect(labels).toMatchObject({
      track_power_sum: '歌曲总点数',
      track_power_rank: '歌曲总点数排名',
      album_power_sum: '专辑总点数',
      album_power_rank: '专辑总点数排名',
      power_score: '艺人走势评分',
      power_rank: '艺人走势排名',
    })
    for (const tab of ['tracks', 'albums', 'artists'] as const) {
      const columns = getColumnsForTab(tab)
      expect(columns.every((column) => column.align === 'right')).toBe(true)
      expect(columns.find((column) => column.key === 'power_score')?.fixed).not.toBe(true)
      expect(columns.find((column) => column.key === 'power_rank')?.rankStyle).toBe(true)
    }
  })

  it('offers an accessible compact field menu and search clear action', async () => {
    const user = userEvent.setup()
    const onVisible = vi.fn()
    const onReset = vi.fn()
    const onQuery = vi.fn()
    render(
      <AllTimeControls
        query="Taylor"
        onQueryChange={onQuery}
        columns={getColumnsForTab('albums')}
        visibleColumnIds={recommendedVisibleColumnIds('albums')}
        onVisibleColumnIdsChange={onVisible}
        onRestoreRecommended={onReset}
      />,
    )

    await user.click(screen.getByRole('button', { name: '选择总榜显示字段' }))
    await user.click(screen.getByLabelText('Top10曲数'))
    expect(onVisible).toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: '恢复推荐显示' }))
    expect(onReset).toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: '清除总榜搜索' }))
    expect(onQuery).toHaveBeenCalledWith('')
  })

  it('renders the preserved full-chart rank and a search-specific empty state', () => {
    const columns = visibleColumnsForTab('tracks', recommendedVisibleColumnIds('tracks'))
    const { rerender } = render(
      <MemoryRouter>
        <AllTimeTable
          activeTab="tracks"
          rows={[track]}
          columns={columns}
          total={1}
          sortKey="power_score"
          sortDir="desc"
          page={1}
          pageSize={50}
          maxBarValue={300}
          onColumnClick={vi.fn()}
          onPageChange={vi.fn()}
        />
      </MemoryRouter>,
    )
    expect(screen.getByTitle(/搜索、分页和字段隐藏不会重算/)).toHaveTextContent('07')

    rerender(
      <MemoryRouter>
        <AllTimeTable
          activeTab="tracks"
          rows={[]}
          columns={columns}
          total={1}
          sortKey="power_score"
          sortDir="desc"
          page={1}
          pageSize={50}
          maxBarValue={1}
          emptyMessage="没有匹配当前搜索的结果"
          onColumnClick={vi.fn()}
          onPageChange={vi.fn()}
        />
      </MemoryRouter>,
    )
    expect(screen.getByText('没有匹配当前搜索的结果')).toBeInTheDocument()
  })

  it('keeps fixed power ranks unchanged under arbitrary sorting and renders numeric columns right-aligned', () => {
    const second = { ...track, track_id: 2, track_name: 'Style', power_rank: 2, power_score: 1200, total_chart_plays: 100 }
    const sorted = selectAllTimeRows({ ...rows, tracks: [track, second] }, 'tracks', 'all', 'total_chart_plays', 'asc')
    expect((sorted.rows as MergedTrackRow[]).map((row) => row.power_rank)).toEqual([2, 7])

    render(
      <MemoryRouter>
        <AllTimeTable
          activeTab="tracks"
          rows={sorted.rows}
          columns={visibleColumnsForTab('tracks', recommendedVisibleColumnIds('tracks'))}
          total={2}
          sortKey="total_chart_plays"
          sortDir="asc"
          page={1}
          pageSize={50}
          maxBarValue={300}
          onColumnClick={vi.fn()}
          onPageChange={vi.fn()}
        />
      </MemoryRouter>,
    )

    expect(screen.getByRole('columnheader', { name: '#' })).toHaveClass('text-right')
    expect(screen.getByRole('columnheader', { name: /走势评分/ })).toHaveClass('text-right')
    expect(screen.getByRole('columnheader', { name: /走势排名/ })).toHaveClass('text-right')
    const chartPlaysHeader = screen.getByRole('columnheader', { name: /入榜播放/ })
    const chartPlaysCell = document.querySelector('td[data-column-key="total_chart_plays"]')
    expect(chartPlaysHeader).toHaveClass('text-right')
    expect(chartPlaysHeader).not.toHaveClass('text-center', 'text-left')
    expect(chartPlaysCell).toHaveClass('text-right')
    expect(chartPlaysCell).not.toHaveClass('text-center', 'text-left')
    expect(chartPlaysCell?.querySelector('.absolute')).toBeInTheDocument()
    expect(screen.getAllByTitle(/搜索、分页和字段隐藏不会重算/).map((cell) => cell.textContent)).toEqual(['02', '07'])
    expect(screen.getAllByText('02').length).toBeGreaterThanOrEqual(2)
  })

  it('keeps zero-contribution derived ranks empty and sorted after comparable entities', () => {
    const noContribution = { ...album, album_name: 'No charted songs', track_power_sum: 0, track_power_rank: null }
    const albumRows = { ...rows, albums: [noContribution, album] }
    for (const direction of ['asc', 'desc'] as const) {
      const selected = selectAllTimeRows(albumRows, 'albums', 'all', 'track_power_rank', direction)
      expect((selected.rows as MergedAlbumRow[]).map((row) => row.track_power_rank)).toEqual([2, null])
    }
  })

  it('persists column width dragging without triggering a sort', () => {
    const onColumnClick = vi.fn()
    render(
      <MemoryRouter>
        <AllTimeTable
          activeTab="albums"
          rows={[album]}
          columns={visibleColumnsForTab('albums', ['power_score', 'power_rank'])}
          total={1}
          sortKey="power_score"
          sortDir="desc"
          page={1}
          pageSize={50}
          maxBarValue={500}
          onColumnClick={onColumnClick}
          onPageChange={vi.fn()}
        />
      </MemoryRouter>,
    )

    fireEvent.mouseDown(screen.getByRole('separator', { name: '调整专辑走势评分列宽' }), { clientX: 100 })
    fireEvent.mouseMove(document, { clientX: 124 })
    fireEvent.mouseUp(document)
    expect(JSON.parse(localStorage.getItem('billboard-alltime-col-widths') ?? '{}').power_score).toBe(104)
    expect(onColumnClick).not.toHaveBeenCalled()
  })

  it('keeps the desktop toolbar in filter → fields/search → pagination order with narrow-screen stacking', async () => {
    const user = userEvent.setup()
    const onPageChange = vi.fn()
    render(
      <AllTimeToolbar
        filters={<button type="button">筛选控件</button>}
        fieldsSearch={<><button type="button">字段控件</button><input aria-label="搜索控件" /></>}
        pagination={<Pagination page={1} totalPages={6} onPageChange={onPageChange} />}
      />,
    )

    const toolbar = screen.getByTestId('all-time-toolbar')
    expect(toolbar).toHaveClass('flex-col', 'xl:flex-row', 'xl:flex-nowrap')
    expect([...toolbar.children].map((element) => element.getAttribute('data-toolbar-part'))).toEqual([
      'filters', 'fields-search', 'pagination',
    ])
    expect(screen.getByText('1 / 6')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '第 1 页' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '第 2 页' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '第 3 页' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '下一页' }))
    const update = onPageChange.mock.calls[0]?.[0]
    expect(typeof update).toBe('function')
    expect(update(1)).toBe(2)
  })
})
