import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { RecentPlaysSection } from '@/components/shared/RecentPlaysSection'
import {
  MobileChartHistoryList,
  MobileMusicDetailHero,
  MobileMusicDetailNav,
} from '@/features/mobile/music/MobileMusicDetail'

afterEach(() => {
  document.body.style.overflow = ''
})

describe('M5 mobile music search and details', () => {
  it('renders entity-specific hero facts and chart history without a table', () => {
    render(
      <MemoryRouter>
        <MobileMusicDetailHero
          kind="album"
          eyebrow="Album / Personal Listening"
          title="The Life of a Showgirl"
          subtitle="Taylor Swift"
          facts={[
            { label: '有效播放', value: '1,651 次' },
            { label: '专辑榜', value: 'PK #1', accent: true },
          ]}
        />
        <MobileChartHistoryList entries={[
          { week: '2026-07-31', rank: 3, change: '▲2', playCount: 88, runningPeak: 1, runningWeeks: 12 },
        ]} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'The Life of a Showgirl' })).toBeInTheDocument()
    expect(screen.getByText('1,651 次')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /PK #1 · 在榜 12周/ })).toHaveAttribute('href', '/billboard?week=2026-07-31')
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('keeps high-frequency detail tabs visible and sends secondary artist sections to a sheet', async () => {
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
          { key: 'career', label: '艺人生涯', description: '简介、档案与生涯信息' },
        ]}
        onChange={onChange}
      />,
    )

    await user.click(screen.getByRole('button', { name: '更多' }))
    const dialog = screen.getByRole('dialog', { name: '更多详情栏目' })
    await user.click(within(dialog).getByRole('option', { name: /专辑/ }))
    expect(onChange).toHaveBeenCalledWith('albums')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
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
