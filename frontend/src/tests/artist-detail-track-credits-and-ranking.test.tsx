import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { MusicTracksSection } from '@/features/music/details/MusicTracksSection'
import { PersonalRankTable } from '@/components/shared/StatsTables'

vi.mock('@/components/shared/CoverCell', () => ({
  CoverCell: ({ label }: { label: string }) => <span>{label}封面</span>,
}))

describe('艺人详情曲目署名与个人排行', () => {
  it('单曲成绩展示每首歌的完整真实署名链接', () => {
    render(
      <MemoryRouter>
        <MusicTracksSection
          artistName="單依純"
          info={{ total_tracks: 1, top1: 0, top5: 1, top10: 1, weeks_at_no1: 0 }}
          tracks={[{
            track_id: 10,
            track_name: '愛我的時候',
            artist_names: ['Eric Chou', '單依純'],
            cover_url: null,
            peak_position: 10,
            weeks_on_chart: 1,
            weeks_at_peak: 1,
            first_week: '2026-07-17',
            first_peak_week: '2026-07-17',
            last_week: '2026-07-17',
            total_chart_plays: 4,
            power_score: 21,
            power_rank: 8,
          }]}
        />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: 'Eric Chou' })).toHaveAttribute(
      'href', '/music/artists/Eric%20Chou?tab=overview',
    )
    expect(screen.getByRole('link', { name: '單依純' })).toHaveAttribute(
      'href', '/music/artists/%E5%96%AE%E4%BE%9D%E7%B4%94?tab=overview',
    )
  })

  it('服务端分页使用API总数并把翻页动作交还上层', () => {
    const onPageChange = vi.fn()
    render(
      <MemoryRouter>
        <PersonalRankTable
          rows={[{
            rank: 21,
            track_id: 21,
            track_name: '第二页歌曲',
            artist_name: 'Artist',
            artist_names: ['Artist'],
            plays: 3,
            hours: 0.2,
            first_played: '2026-01-01',
            last_played: '2026-02-01',
            avg_daily_plays: 0.1,
            avg_daily_hours: 0.01,
            share_pct: 1,
            cover_url: null,
          }]}
          entity="track"
          metric="plays"
          pagination={{ total: 41, page: 2, pageSize: 20, onPageChange }}
        />
      </MemoryRouter>,
    )
    expect(screen.getByText('显示 21-40 / 总数 41 条')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '下一页' }))
    expect(onPageChange).toHaveBeenCalledWith(3)
  })

  it('歌曲榜搜索只过滤行，并让三榜共享艺术体原始名次', () => {
    const { rerender } = render(
      <MemoryRouter>
        <PersonalRankTable
          rows={[
            {
              rank: 1, track_id: 1, track_name: '合作歌曲', artist_name: '主艺人', artist_names: ['主艺人', 'Featured Artist'], album_name: '专辑',
              plays: 10, hours: 1, first_played: '2026-01-01', last_played: '2026-02-01', avg_daily_plays: 1, avg_daily_hours: 0.1, share_pct: 10, cover_url: null,
            },
            {
              rank: 2, track_id: 2, track_name: '另一首歌', artist_name: '其他艺人', album_name: '另一张专辑',
              plays: 8, hours: 0.8, first_played: '2026-01-01', last_played: '2026-02-01', avg_daily_plays: 0.8, avg_daily_hours: 0.08, share_pct: 8, cover_url: null,
            },
          ]}
          entity="track"
          metric="plays"
          searchQuery="featured"
        />
      </MemoryRouter>,
    )

    expect(screen.getByRole('cell', { name: '01' }).firstChild).toHaveClass('font-serif', 'text-accent-foreground')
    expect(screen.queryByText('另一首歌')).not.toBeInTheDocument()

    for (const entity of ['album', 'artist'] as const) {
      rerender(
        <MemoryRouter>
          <PersonalRankTable
            rows={[{
              rank: 1, album_name: '专辑', artist_name: '艺人', plays: 10, hours: 1,
              first_played: '2026-01-01', last_played: '2026-02-01', avg_daily_plays: 1,
              avg_daily_hours: 0.1, share_pct: 10, cover_url: null,
            }]}
            entity={entity}
            metric="plays"
          />
        </MemoryRouter>,
      )
      expect(screen.getByRole('cell', { name: '01' }).firstChild).toHaveClass('font-serif', 'text-accent-foreground')
    }
  })
})
