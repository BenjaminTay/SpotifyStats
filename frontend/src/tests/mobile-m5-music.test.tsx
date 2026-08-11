import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { RecentPlaysSection } from '@/components/shared/RecentPlaysSection'
import { ArtistAlbumsSection } from '@/features/music/details/ArtistAlbumsSection'
import { MusicTracksSection } from '@/features/music/details/MusicTracksSection'
import {
  MobileChartHistoryList,
  MobileMusicDetailHero,
  MobileMusicDetailNav,
} from '@/features/mobile/music/MobileMusicDetail'

vi.mock('@/hooks/useViewportMode', () => ({ useViewportMode: () => 'phone' }))

afterEach(() => {
  document.body.style.overflow = ''
})

describe('M5 mobile music search and details', () => {
  it('renders entity-specific hero facts and chart history without a table', () => {
    render(
      <MemoryRouter>
        <MobileMusicDetailHero
          kind="album"
          title="The Life of a Showgirl"
          subtitle="Taylor Swift"
          facts={[
            { label: '有效播放', value: '1,651 次' },
            { label: '专辑榜', value: 'PK #1', accent: true },
            { label: '成员单曲', value: '6 首入榜' },
            { label: '走势排名', value: '#3' },
          ]}
        />
        <MobileChartHistoryList entries={[
          { week: '2026-07-31', rank: 3, change: '▲2', playCount: 88, runningPeak: 1, runningWeeks: 12, runningPeakWeeks: 3 },
        ]} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'The Life of a Showgirl' })).toBeInTheDocument()
    expect(screen.queryByText(/Personal Listening/i)).not.toBeInTheDocument()
    expect(screen.getByText('有效播放').closest('dl')?.querySelectorAll(':scope > div')).toHaveLength(4)
    expect(screen.getByText('1,651 次')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Peak 1 · 在榜 12周 · 峰值 3周/ })).toHaveAttribute('href', '/billboard?week=2026-07-31')
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('keeps all artist detail tabs visible in one horizontal scroller', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <MobileMusicDetailNav
        activeTab="stats"
        primaryTabs={[
          { key: 'stats', label: '统计' },
          { key: 'overview', label: '榜单' },
          { key: 'tracks', label: '歌曲' },
        ]}
        moreTabs={[
          { key: 'albums', label: '专辑', description: '专辑榜成绩与固定走势排名' },
          { key: 'releases', label: '发行周期' },
          { key: 'career', label: '艺人生涯', description: '简介、档案与生涯信息' },
        ]}
        scrollable
        onChange={onChange}
      />,
    )

    expect(screen.getByRole('navigation', { name: '详情栏目' })).toHaveClass('mobile-music-detail-nav-scroll')
    expect(screen.queryByRole('button', { name: '更多' })).not.toBeInTheDocument()
    expect(screen.getAllByRole('button')).toHaveLength(6)
    await user.click(screen.getByRole('button', { name: '专辑' }))
    expect(onChange).toHaveBeenCalledWith('albums')
  })

  it('paginates long mobile chart histories at ten rows', async () => {
    const user = userEvent.setup()
    const entries = Array.from({ length: 11 }, (_, index) => ({
      week: `2026-${String(index + 1).padStart(2, '0')}-01`,
      rank: index + 1,
      change: index === 0 ? 'NEW' : '—',
      playCount: 20 - index,
      runningPeak: 1,
      runningWeeks: index + 1,
      runningPeakWeeks: 1,
    }))
    render(<MemoryRouter><MobileChartHistoryList entries={entries} /></MemoryRouter>)
    expect(screen.getByText('2026-10-01')).toBeInTheDocument()
    expect(screen.queryByText('2026-11-01')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '下一页' }))
    expect(screen.getByText('2026-11-01')).toBeInTheDocument()
  })

  it('unifies the complete mobile achievement KPIs and removes duplicate trend labels', () => {
    render(
      <MemoryRouter>
        <section aria-label="单曲移动成绩">
          <MusicTracksSection
            artistName="Artist"
            info={{ total_tracks: 6, top1: 1, top5: 4, top10: 6, weeks_at_no1: 3, total_weeks: 42, total_track_power: 680, track_power_rank: 4 }}
            tracks={[{
              track_id: 7,
              track_name: 'Chart Song',
              artist_names: ['Artist'],
              cover_url: null,
              peak_position: 2,
              weeks_on_chart: 12,
              weeks_at_peak: 3,
              first_week: '2026-01-01',
              first_peak_week: '2026-01-08',
              last_week: '2026-03-01',
              total_chart_plays: 88,
              power_score: 100,
              power_rank: 9,
            }]}
          />
        </section>
        <section aria-label="专辑移动成绩">
          <ArtistAlbumsSection
            artistName="Artist"
            info={{ num_no1_albums: 1, total_albums: 3, album_top5: 2, album_no1_weeks: 4, total_album_weeks: 14, total_album_power: 520, album_power_rank: 2 } as never}
            albums={[
              { album_name: 'Album One', cover_url: null, peak: 1, weeks: 8, pk_wks: 2, first_week: '', first_peak_week: '', last_week: '', total_plays: 80, power_score: 100, power_rank: 3 },
              { album_name: 'Album Five', cover_url: null, peak: 5, weeks: 4, pk_wks: 1, first_week: '', first_peak_week: '', last_week: '', total_plays: 40, power_score: 50, power_rank: 8 },
              { album_name: 'Album Nine', cover_url: null, peak: 9, weeks: 2, pk_wks: 1, first_week: '', first_peak_week: '', last_week: '', total_plays: 20, power_score: 20, power_rank: 12 },
            ]}
          />
        </section>
      </MemoryRouter>,
    )

    const tracks = screen.getByRole('region', { name: '单曲移动成绩' })
    expect(tracks.querySelectorAll('.mobile-achievement-kpis > div')).toHaveLength(8)
    expect(within(tracks).getByText('#1 曲目')).toBeInTheDocument()
    expect(within(tracks).getByText('Top 5')).toBeInTheDocument()
    expect(within(tracks).getByText('Top 10')).toBeInTheDocument()
    expect(within(tracks).getByText('冠军周数')).toBeInTheDocument()
    expect(within(tracks).getByText('总在榜周数')).toBeInTheDocument()
    expect(within(tracks).getByText('歌曲总点数')).toBeInTheDocument()
    const trackKpis = tracks.querySelectorAll('.mobile-achievement-kpis > div')
    expect(trackKpis[7]).toHaveTextContent('总点数排名')
    expect(trackKpis[7]).toHaveTextContent('4')
    expect(within(tracks).getByRole('link', { name: /Chart Song/ })).toHaveTextContent('Peak')
    expect(within(tracks).queryByText(/走势/)).not.toBeInTheDocument()
    const albums = screen.getByRole('region', { name: '专辑移动成绩' })
    expect(albums.querySelectorAll('.mobile-achievement-kpis > div')).toHaveLength(7)
    expect(within(albums).getByText('入榜专辑')).toBeInTheDocument()
    expect(within(albums).getByText('Top 5')).toBeInTheDocument()
    expect(within(albums).getByText('#1 专辑')).toBeInTheDocument()
    expect(within(albums).getByText('冠军周数')).toBeInTheDocument()
    expect(within(albums).getByText('总在榜周数')).toBeInTheDocument()
    expect(within(albums).getByText('专辑总点数')).toBeInTheDocument()
    expect(within(albums).queryByText('#2')).not.toBeInTheDocument()
    expect(within(albums).getAllByText('2')).not.toHaveLength(0)
    expect(within(albums).getAllByText('3')).not.toHaveLength(0)
    expect(within(albums).queryByText(/走势/)).not.toBeInTheDocument()
  })

  it('renders recent plays as mobile entity rows instead of desktop tables', async () => {
    const fetchPage = vi.fn().mockResolvedValue({
      total: 1,
      limit: 50,
      offset: 0,
      rows: [{
        play_id: 7,
        ts: '2026-08-05T01:30:00Z',
        date: '2026-08-05',
        track_id: 42,
        track_name: 'Cruel Summer',
        artist_name: 'Taylor Swift',
        artist_names: ['Taylor Swift'],
        album_name: 'Lover',
        ms_played: 178000,
        hours: 178000 / 3_600_000,
        platform: 'iOS',
        cover_url: null,
      }],
    })
    render(
      <MemoryRouter>
        <RecentPlaysSection
          kind="track"
          entityId="42"
          filters={{} as never}
          apiParams={{ period: 'lifetime' }}
          fetchPage={fetchPage}
          fetchPlayDates={vi.fn().mockResolvedValue([{ date: '2026-08-05', count: 1 }])}
          mobile
        />
      </MemoryRouter>,
    )

    const row = await screen.findByRole('link', { name: /Cruel Summer/ })
    expect(row).toHaveAttribute('href', '/music/tracks/42')
    expect(row).toHaveTextContent('专辑 Lover')
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})
