import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { YearEndExperience } from '@/features/billboard/year-end/YearEndExperience'
import type {
  BillboardYearEndHonors,
  BillboardYearEndResponse,
  BillboardYearEndTrackRow,
} from '@/types/billboard'

const useBillboardYearEndMock = vi.hoisted(() => vi.fn())
const useSettingsMock = vi.hoisted(() => vi.fn())

vi.mock('@/hooks/useBillboard', () => ({
  useBillboardYearEnd: useBillboardYearEndMock,
}))
vi.mock('@/hooks/useSettings', () => ({
  useSettings: useSettingsMock,
}))

function trackRow(name: string): BillboardYearEndTrackRow {
  return {
    track_id: 1,
    track_name: name,
    artist_name: 'Test Artist',
    artist_names: ['Test Artist'],
    album_name: 'Test Album',
    cover_url: null,
    year_end_score: 1200,
    year_end_rank: 1,
    peak_position: 1,
    weeks_on_chart: 20,
    weeks_at_peak: 3,
    weeks_at_no1: 3,
    weeks_top5: 10,
    weeks_top10: 15,
    chart_plays: 200,
    annual_plays: 230,
    first_week: '2026-01-02T00:00:00',
    last_week: '2026-05-15T00:00:00',
    true_first_week: '2026-01-02T00:00:00',
    is_true_debut_no1: true,
  }
}

function honors(row: BillboardYearEndTrackRow): BillboardYearEndHonors {
  return {
    year_end_no1_track: row,
    year_end_no1_album: null,
    year_end_no1_artist: null,
    longest_charting_track: row,
    longest_charting_album: null,
    longest_charting_artist: null,
    biggest_no1_run_track: row,
    biggest_no1_run_album: null,
    biggest_no1_run_artist: null,
    top_new_entry_track: row,
    breakthrough_artist: null,
    album_era_of_the_year: null,
  }
}

function response(year: number, name: string): BillboardYearEndResponse {
  const row = trackRow(name)
  return {
    meta: {
      year,
      available_years: [2025, 2026],
      total_weeks: 20,
      top_n: 50,
      album_top_n: 30,
      artist_top_n: 30,
      year_end_top_n: 50,
      year_end_album_top_n: 30,
      year_end_artist_top_n: 30,
      weekly_top_n: 25,
      weekly_album_top_n: 15,
      weekly_artist_top_n: 15,
      week_start_dow: 4,
      week_start_hour: 12,
      score_label: 'Year-End Score',
      semantics_version: 'year_end_v4',
      coverage_status: 'year_to_date',
      is_complete_year: false,
      period_start: `${year}-01-02T00:00:00`,
      period_end: `${year}-05-15T00:00:00`,
      first_billboard_week: `${year}-01-02T00:00:00`,
      last_billboard_week: `${year}-05-15T00:00:00`,
      observed_weeks: 20,
      expected_weeks: 52,
      has_internal_gaps: false,
    },
    tracks: [row],
    albums: [],
    artists: [],
    honors: honors(row),
  }
}

describe('Billboard Year-End experience', () => {
  beforeEach(() => {
    useBillboardYearEndMock.mockReset()
    useSettingsMock.mockReset()
    useSettingsMock.mockReturnValue({
      settings: { include_compilations: false },
      loading: false,
    })
  })

  it('marks partial-year coverage and honors as provisional', () => {
    useBillboardYearEndMock.mockReturnValue({
      data: response(2026, 'Current Leader'),
      loading: false,
      fetching: false,
      placeholder: false,
      error: null,
      refetch: vi.fn(),
    })

    render(
      <MemoryRouter initialEntries={['/billboard/year-end?year=2026']}>
        <YearEndExperience />
      </MemoryRouter>,
    )

    expect(screen.getByText(/阶段年榜/)).toBeInTheDocument()
    expect(screen.getByText(/已统计 20\/52 个榜单周/)).toBeInTheDocument()
    expect(screen.getByText(/单曲 Top 25、专辑 Top 15、艺人 Top 15/)).toBeInTheDocument()
    expect(screen.getByText('阶段领先单曲')).toBeInTheDocument()
    expect(screen.getAllByText('Current Leader').length).toBeGreaterThan(0)
  })

  it('does not render the previous year while a requested year is fetching', () => {
    useBillboardYearEndMock.mockReturnValue({
      data: response(2025, 'Previous Year Leader'),
      loading: false,
      fetching: true,
      placeholder: true,
      error: null,
      refetch: vi.fn(),
    })

    const { container } = render(
      <MemoryRouter initialEntries={['/billboard/year-end?year=2026']}>
        <YearEndExperience />
      </MemoryRouter>,
    )

    expect(screen.queryByText('Previous Year Leader')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Year-End Summary')).not.toBeInTheDocument()
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0)
  })

  it('does not announce an empty year list while the initial request is loading', () => {
    useBillboardYearEndMock.mockReturnValue({
      data: null,
      loading: true,
      fetching: true,
      placeholder: false,
      error: null,
      refetch: vi.fn(),
    })

    const { container } = render(
      <MemoryRouter initialEntries={['/billboard/year-end']}>
        <YearEndExperience />
      </MemoryRouter>,
    )

    expect(screen.queryByText('无数据')).not.toBeInTheDocument()
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0)
  })

  it('shows no data only after the year request settles successfully', () => {
    const emptyResponse = response(2026, 'Unused')
    emptyResponse.meta.available_years = []
    emptyResponse.tracks = []
    emptyResponse.honors = {
      year_end_no1_track: null,
      year_end_no1_album: null,
      year_end_no1_artist: null,
      longest_charting_track: null,
      longest_charting_album: null,
      longest_charting_artist: null,
      biggest_no1_run_track: null,
      biggest_no1_run_album: null,
      biggest_no1_run_artist: null,
      top_new_entry_track: null,
      breakthrough_artist: null,
      album_era_of_the_year: null,
    }
    useBillboardYearEndMock.mockReturnValue({
      data: emptyResponse,
      loading: false,
      fetching: false,
      placeholder: false,
      error: null,
      refetch: vi.fn(),
    })

    render(
      <MemoryRouter initialEntries={['/billboard/year-end']}>
        <YearEndExperience />
      </MemoryRouter>,
    )

    expect(
      within(screen.getByLabelText('切换年榜年份')).getByText('无数据'),
    ).toBeInTheDocument()
  })

  it('does not mislabel a failed year request as no data', () => {
    useBillboardYearEndMock.mockReturnValue({
      data: null,
      loading: false,
      fetching: false,
      placeholder: false,
      error: '网络请求失败',
      refetch: vi.fn(),
    })

    render(
      <MemoryRouter initialEntries={['/billboard/year-end']}>
        <YearEndExperience />
      </MemoryRouter>,
    )

    expect(screen.getByText('网络请求失败')).toBeInTheDocument()
    expect(screen.queryByText('无数据')).not.toBeInTheDocument()
  })

  it('does not render same-year placeholder data from a previous chart configuration', () => {
    useBillboardYearEndMock.mockReturnValue({
      data: response(2026, 'Previous Configuration Leader'),
      loading: false,
      fetching: true,
      placeholder: true,
      error: null,
      refetch: vi.fn(),
    })

    const { container } = render(
      <MemoryRouter initialEntries={['/billboard/year-end?year=2026&merge_level=3']}>
        <YearEndExperience />
      </MemoryRouter>,
    )

    expect(screen.queryByText('Previous Configuration Leader')).not.toBeInTheDocument()
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0)
  })

  it('uses the persisted compilation setting when the URL has no override', () => {
    useSettingsMock.mockReturnValue({
      settings: { include_compilations: true },
      loading: false,
    })
    useBillboardYearEndMock.mockReturnValue({
      data: response(2026, 'Compilation-Aware Leader'),
      loading: false,
      fetching: false,
      placeholder: false,
      error: null,
      refetch: vi.fn(),
    })

    render(
      <MemoryRouter initialEntries={['/billboard/year-end?year=2026']}>
        <YearEndExperience />
      </MemoryRouter>,
    )

    expect(useBillboardYearEndMock).toHaveBeenCalledWith(2026, 2, true, true)
  })

  it.each([
    ['tracks', '单曲榜'],
    ['albums', '专辑榜'],
    ['artists', '艺人榜'],
  ] as const)('opens the %s tab requested by the URL', (tab, label) => {
    useBillboardYearEndMock.mockReturnValue({
      data: response(2026, 'Linked Leader'),
      loading: false,
      fetching: false,
      placeholder: false,
      error: null,
      refetch: vi.fn(),
    })

    render(
      <MemoryRouter initialEntries={[`/billboard/year-end?year=2026&tab=${tab}`]}>
        <YearEndExperience />
      </MemoryRouter>,
    )

    expect(screen.getByRole('tab', { name: label })).toHaveAttribute('aria-selected', 'true')
  })
})
