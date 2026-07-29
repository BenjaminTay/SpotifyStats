import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { YearEndHonors } from '@/features/billboard/year-end/YearEndHonors'
import type { BillboardYearEndHonors } from '@/types/billboard'

function baseRow(name: string, coverUrl: string, overrides: Record<string, unknown> = {}) {
  return {
    track_id: 1,
    track_name: name,
    album_name: name,
    artist_name: name,
    artist_names: [name],
    cover_url: coverUrl,
    year_end_score: 1000,
    year_end_rank: 1,
    peak_position: 1,
    weeks_on_chart: 12,
    weeks_at_peak: 2,
    weeks_at_no1: 3,
    weeks_top5: 8,
    weeks_top10: 10,
    chart_plays: 300,
    annual_plays: 320,
    first_week: '2026-01-02',
    last_week: '2026-03-20',
    true_first_week: '2026-01-02',
    is_true_debut_no1: false,
    ...overrides,
  }
}

describe('Billboard Year-End UI', () => {
  it('renders selected year-end honors with cover artwork', () => {
    const honors: BillboardYearEndHonors = {
      year_end_no1_track: baseRow('年度冠军单曲', '/covers/track.jpg'),
      year_end_no1_album: baseRow('年度冠军专辑', '/covers/album.jpg'),
      year_end_no1_artist: baseRow('年度艺人', '/covers/artist.jpg'),
      longest_charting_track: baseRow('最长在榜单曲', '/covers/long-track.jpg'),
      longest_charting_album: baseRow('最长在榜专辑', '/covers/long-album.jpg'),
      longest_charting_artist: baseRow('最长在榜艺人', '/covers/long-artist.jpg'),
      biggest_no1_run_track: baseRow('冠军统治单曲', '/covers/no1-track.jpg'),
      biggest_no1_run_album: baseRow('最长冠军专辑', '/covers/no1-album.jpg'),
      biggest_no1_run_artist: baseRow('最长冠军艺人', '/covers/no1-artist.jpg'),
      top_new_entry_track: baseRow('年度新入榜', '/covers/new-entry.jpg'),
      breakthrough_artist: baseRow('突破艺人', '/covers/breakthrough.jpg'),
      album_era_of_the_year: baseRow('年度专辑时代', '/covers/era.jpg'),
    }

    render(<YearEndHonors honors={honors} />)

    const summary = screen.getByLabelText('Year-End Summary')
    expect(within(summary).getAllByRole('article')).toHaveLength(6)
    expect(within(summary).getAllByRole('img', { name: /封面/ })).toHaveLength(6)
    expect(within(summary).getAllByText('年度冠军单曲').length).toBeGreaterThan(0)
    expect(within(summary).getAllByText('年度冠军专辑').length).toBeGreaterThan(0)
    expect(within(summary).getAllByText('年度艺人').length).toBeGreaterThan(0)
    expect(within(summary).getAllByText('最长在榜单曲').length).toBeGreaterThan(0)
    expect(within(summary).getAllByText('冠军统治单曲').length).toBeGreaterThan(0)
    expect(within(summary).getAllByText('突破艺人').length).toBeGreaterThan(0)
    expect(within(summary).queryByText('年度专辑时代')).not.toBeInTheDocument()
    expect(within(summary).queryByText('最长冠军专辑')).not.toBeInTheDocument()
    expect(within(summary).queryByText('年度新入榜')).not.toBeInTheDocument()
  })

  it('renders honor-specific details for each selected year-end card', () => {
    const honors: BillboardYearEndHonors = {
      year_end_no1_track: baseRow('Track Winner', '/covers/track.jpg', {
        year_end_score: 4062,
        peak_position: 1,
        weeks_top10: 13,
      }),
      year_end_no1_album: baseRow('Album Winner', '/covers/album.jpg', {
        year_end_score: 9698,
        peak_position: 1,
        weeks_on_chart: 47,
      }),
      year_end_no1_artist: baseRow('Artist Winner', '/covers/artist.jpg', {
        year_end_score: 20579,
        peak_position: 1,
        weeks_on_chart: 52,
      }),
      longest_charting_track: baseRow('Long Runner', '/covers/long-track.jpg', {
        year_end_score: 1822,
        peak_position: 6,
        weeks_on_chart: 31,
      }),
      longest_charting_album: null,
      longest_charting_artist: null,
      biggest_no1_run_track: baseRow('No. 1 Run', '/covers/no1-track.jpg', {
        year_end_score: 4062,
        weeks_at_no1: 3,
        weeks_on_chart: 30,
      }),
      biggest_no1_run_album: null,
      biggest_no1_run_artist: null,
      top_new_entry_track: null,
      breakthrough_artist: baseRow('Breakthrough', '/covers/breakthrough.jpg', {
        year_end_score: 2191,
        year_end_rank: 15,
      }),
      album_era_of_the_year: null,
    }

    render(<YearEndHonors honors={honors} />)

    const summary = screen.getByLabelText('Year-End Summary')
    expect(within(summary).getByText('4,062 pts · 最高 #1 · Top10 13 周')).toBeInTheDocument()
    expect(within(summary).getByText('9,698 pts · 最高 #1 · 在榜 47 周')).toBeInTheDocument()
    expect(within(summary).getByText('20,579 pts · 最高 #1 · 在榜 52 周')).toBeInTheDocument()
    expect(within(summary).getByText('31 周在榜 · 最高 #6 · 1,822 pts')).toBeInTheDocument()
    expect(within(summary).getByText('#1 共 3 周 · 4,062 pts · 在榜 30 周')).toBeInTheDocument()
    expect(within(summary).getByText('年度首次入榜 · #15 · 2,191 pts')).toBeInTheDocument()
  })

  it('labels honors as provisional when the selected year is incomplete', () => {
    const honors: BillboardYearEndHonors = {
      year_end_no1_track: baseRow('Track Leader', '/covers/track.jpg'),
      year_end_no1_album: baseRow('Album Leader', '/covers/album.jpg'),
      year_end_no1_artist: baseRow('Artist Leader', '/covers/artist.jpg'),
      longest_charting_track: baseRow('Long Runner', '/covers/long-track.jpg'),
      longest_charting_album: null,
      longest_charting_artist: null,
      biggest_no1_run_track: baseRow('No. 1 Run', '/covers/no1-track.jpg'),
      biggest_no1_run_album: null,
      biggest_no1_run_artist: null,
      top_new_entry_track: null,
      breakthrough_artist: baseRow('Breakthrough', '/covers/breakthrough.jpg'),
      album_era_of_the_year: null,
    }

    render(<YearEndHonors honors={honors} isCompleteYear={false} />)

    expect(screen.getByText('阶段领先单曲')).toBeInTheDocument()
    expect(screen.getByText('阶段领先专辑')).toBeInTheDocument()
    expect(screen.getByText('阶段领先艺人')).toBeInTheDocument()
    expect(screen.getByText('本阶段首次入榜 · #1 · 1,000 pts')).toBeInTheDocument()
    expect(screen.queryByText('年度冠军单曲')).not.toBeInTheDocument()
  })
})
