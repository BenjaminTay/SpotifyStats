import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, useLocation, useNavigationType } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { LongevitySection } from '@/features/analysis/records/LongevitySection'
import { ObsessionSection } from '@/features/analysis/records/ObsessionSection'
import { PlaybackMilestonesCard } from '@/features/analysis/records/BehaviorSection'
import { DiscoverySection } from '@/features/analysis/records/DiscoverySection'
import { ReignsSection } from '@/features/analysis/records/ReignsSection'
import { TimePatternsSection } from '@/features/analysis/records/TimePatternsSection'
import { EntityRecordCard } from '@/features/analysis/records/PlaybackRecordsPrimitives'
import { PlaybackRecordsExperience } from '@/features/analysis/records/PlaybackRecordsExperience'
import { PLAYBACK_RECORD_MODULE_COUNT, PLAYBACK_RECORD_SECTIONS } from '@/features/analysis/records/recordsArchitecture'
import { ThemeProvider } from '@/hooks/useTheme'
import type {
  EntityRecordFamily,
  PlaybackBehaviorRecords,
  PlaybackDiscoveryRecords,
  PlaybackLongevityRecords,
  PlaybackObsessionRecords,
  PlaybackRecordRow,
  PlaybackRecordsData,
  PlaybackReignRecords,
  PlaybackTimePatternRecords,
} from '@/types/analysis'

vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({
  matches: false,
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
}))

const emptyFamily = (): EntityRecordFamily => ({ track: [], album: [], artist: [] })

const row = (
  name: string,
  value: number,
  overrides: Partial<PlaybackRecordRow> = {},
): PlaybackRecordRow => ({
  rank: 1,
  name,
  value,
  unit: '次',
  ...overrides,
})

const obsessionData = (): PlaybackObsessionRecords => ({
  daily_binge: {
    track: [row('次数冠军', 12, { entity_id: 'track-1', artist_name: '测试艺人' })],
    album: [row('Album / Deluxe', 9, { artist_name: 'Artist & Co.' })],
    artist: [],
  },
  daily_duration: {
    track: [
      row('时长冠军', 4, { unit: '小时', entity_id: 'track-2' }),
      row('时长亚军', 2, { unit: '小时', entity_id: 'track-3' }),
    ],
    album: [],
    artist: [],
  },
  consecutive_marathon: {
    track: [
      row('马拉松冠军', 10, {
        unit: '次连续播放',
        secondary_value: 2,
        secondary_unit: '小时',
      }),
      row('马拉松亚军', 5, {
        unit: '次连续播放',
        secondary_value: 1,
        secondary_unit: '小时',
      }),
    ],
    album: [],
    artist: [],
  },
  daily_total_record: [],
})

function renderObsession() {
  return render(
    <MemoryRouter>
      <ObsessionSection data={obsessionData()} reigns={{ daily_champion: emptyFamily(), monthly_reign: emptyFamily(), yearly_reign: emptyFamily(), fastest_milestone: emptyFamily(), consecutive_champion_days: emptyFamily() }} behavior={{ skip_storm: emptyFamily(), shuffle_peak: [], platform_reign: [], platform_switch_day: [], playback_milestones: [] }} />
    </MemoryRouter>,
  )
}

function renderTimePatterns(data: PlaybackTimePatternRecords) {
  return render(<ThemeProvider><MemoryRouter><TimePatternsSection data={data} /></MemoryRouter></ThemeProvider>)
}

function RouterStateProbe() {
  const location = useLocation()
  const navigationType = useNavigationType()
  return <output data-testid="router-state">{location.search}|{navigationType}</output>
}

describe('播放记录 UI', () => {
  it('以五个导航唯一承载迁移后的 20 个模块', () => {
    expect(PLAYBACK_RECORD_SECTIONS.map((section) => section.label)).toEqual([
      '高光时刻', '个人王朝', '长线陪伴', '时间习惯', '探索与品味',
    ])
    expect(PLAYBACK_RECORD_SECTIONS.map((section) => section.modules.map((module) => module.title))).toEqual([
      ['单日巅峰', '单日总量记录', '播放里程碑', '最快里程碑', '连续播放马拉松'],
      ['每日冠军次数', '月度统治', '年度统治', '连续冠军天数'],
      ['最长连续播放天数', '最长陪伴跨度', '沉睡后回归', '最活跃月份'],
      ['时段统计', '月度巅峰', '深夜聆听轨迹'],
      ['发现日', '专辑全碟回放', '合作曲排行', '同名异曲'],
    ])
    const moduleKeys = PLAYBACK_RECORD_SECTIONS.flatMap((section) => section.modules.map((module) => module.key))
    expect(PLAYBACK_RECORD_MODULE_COUNT).toBe(20)
    expect(new Set(moduleKeys).size).toBe(20)
  })

  it('按迁移清单顺序渲染五个导航，并逐页承载全部 20 个模块', async () => {
    const data: PlaybackRecordsData = {
      obsession: obsessionData(),
      reigns: { daily_champion: emptyFamily(), monthly_reign: emptyFamily(), yearly_reign: emptyFamily(), fastest_milestone: emptyFamily(), consecutive_champion_days: emptyFamily() },
      longevity: { longest_streak_days: emptyFamily(), longest_span: emptyFamily(), comeback_after_sleep: emptyFamily(), most_active_months: emptyFamily(), user_active_streak: [] },
      time_patterns: { hourly_dominance: emptyFamily(), monthly_peak: emptyFamily(), yearly_peak: emptyFamily(), late_night_peak_day: [], weekday_preference: [] },
      discovery: { discovery_day: emptyFamily(), longest_no_repeat: emptyFamily(), album_completionist: emptyFamily(), same_name_diff_artist: [], feat_lover: emptyFamily() },
      behavior: { skip_storm: emptyFamily(), shuffle_peak: [], platform_reign: [], platform_switch_day: [], playback_milestones: [] },
    }
    render(<ThemeProvider><MemoryRouter><PlaybackRecordsExperience data={data} /></MemoryRouter></ThemeProvider>)

    const tabs = within(screen.getByRole('tablist', { name: '播放记录分类' })).getAllByRole('tab')
    expect(tabs.map((tab) => tab.textContent)).toEqual(['高光时刻', '个人王朝', '长线陪伴', '时间习惯', '探索与品味'])
    expect(screen.queryByRole('tab', { name: '行为奇观' })).not.toBeInTheDocument()

    const observed = new Set<string>()
    for (const section of PLAYBACK_RECORD_SECTIONS) {
      fireEvent.click(screen.getByRole('tab', { name: section.label }))
      for (const module of section.modules) {
        await screen.findByRole('heading', { name: new RegExp(`^${module.title} ·`) })
        observed.add(module.key)
      }
    }
    expect(observed.size).toBe(20)
  })

  it('移动端使用横向滑动栏目条，并省略重复的栏目标题和说明', async () => {
    const matchMedia = vi.mocked(window.matchMedia)
    matchMedia.mockImplementation((query: string) => ({
      matches: query.includes('max-width: 767px'),
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))

    const data: PlaybackRecordsData = {
      obsession: obsessionData(),
      reigns: { daily_champion: emptyFamily(), monthly_reign: emptyFamily(), yearly_reign: emptyFamily(), fastest_milestone: emptyFamily(), consecutive_champion_days: emptyFamily() },
      longevity: { longest_streak_days: emptyFamily(), longest_span: emptyFamily(), comeback_after_sleep: emptyFamily(), most_active_months: emptyFamily(), user_active_streak: [] },
      time_patterns: {
        hourly_dominance: {
          ...emptyFamily(),
          track: [row('零点冠军', 4, { date: '0:00' })],
        },
        monthly_peak: {
          ...emptyFamily(),
          track: [row('月度冠军', 8, { date: '2026-01' })],
        },
        yearly_peak: emptyFamily(),
        late_night_peak_day: [],
        weekday_preference: [],
      },
      discovery: { discovery_day: emptyFamily(), longest_no_repeat: emptyFamily(), album_completionist: emptyFamily(), same_name_diff_artist: [], feat_lover: emptyFamily() },
      behavior: { skip_storm: emptyFamily(), shuffle_peak: [], platform_reign: [], platform_switch_day: [], playback_milestones: [] },
    }

    try {
      render(<ThemeProvider><MemoryRouter><PlaybackRecordsExperience data={data} /></MemoryRouter></ThemeProvider>)

      const tablist = screen.getByRole('tablist', { name: '播放记录分类' })
      expect(tablist).toHaveClass('mobile-record-family-tabs')
      expect(tablist.parentElement).toHaveClass('mobile-playback-records-experience')
      expect(within(tablist).getAllByRole('tab').map((tab) => tab.textContent)).toEqual([
        '高光时刻', '个人王朝', '长线陪伴', '时间习惯', '探索与品味',
      ])
      await screen.findByRole('heading', { name: '单日巅峰' })
      expect(screen.queryByText('单个自然日内播放次数或累计听歌时长最高的歌曲、专辑与艺人')).not.toBeInTheDocument()
      expect(screen.queryByRole('heading', { name: '高光时刻' })).not.toBeInTheDocument()
      expect(screen.queryByText('把最强烈的一天、关键里程碑与最快达成纪录放在同一条个人音乐时间线上。')).not.toBeInTheDocument()

      fireEvent.click(screen.getByRole('tab', { name: '时间习惯' }))
      await screen.findByRole('heading', { name: '时段统计' })
      expect(within(screen.getByRole('tablist', { name: '选择八小时时段' })).getAllByRole('tab').map((tab) => tab.textContent)).toEqual([
        '0:00-7:00', '8:00-15:00', '16:00-23:00',
      ])
      expect(screen.queryByText(/^(凌晨|白天|夜间)$/)).not.toBeInTheDocument()
      expect(screen.getByText('2026-01')).toHaveClass('mobile-playback-record-date')

      fireEvent.click(screen.getByRole('tab', { name: '高光时刻' }))
      const marathonHeading = await screen.findByRole('heading', { name: '连续播放马拉松' })
      const marathonCard = marathonHeading.closest('.mobile-record-card') as HTMLElement
      expect(screen.queryByText('连续次数')).not.toBeInTheDocument()
      expect(within(marathonCard).getByText('马拉松冠军')).toBeInTheDocument()
      expect(marathonCard.querySelector('.mobile-record-rank-primary > small')).toBeNull()
      expect(marathonCard.querySelector('.mobile-record-value')).toHaveTextContent('10次连续播放')
    } finally {
      matchMedia.mockReturnValue({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      } as unknown as MediaQueryList)
    }
  })

  it('从 URL 恢复栏目，并用 replace 保留其他筛选参数', async () => {
    const data: PlaybackRecordsData = {
      obsession: obsessionData(),
      reigns: { daily_champion: emptyFamily(), monthly_reign: emptyFamily(), yearly_reign: emptyFamily(), fastest_milestone: emptyFamily(), consecutive_champion_days: emptyFamily() },
      longevity: { longest_streak_days: emptyFamily(), longest_span: emptyFamily(), comeback_after_sleep: emptyFamily(), most_active_months: emptyFamily(), user_active_streak: [] },
      time_patterns: { hourly_dominance: emptyFamily(), monthly_peak: emptyFamily(), yearly_peak: emptyFamily(), late_night_peak_day: [], weekday_preference: [] },
      discovery: { discovery_day: emptyFamily(), longest_no_repeat: emptyFamily(), album_completionist: emptyFamily(), same_name_diff_artist: [], feat_lover: emptyFamily() },
      behavior: { skip_storm: emptyFamily(), shuffle_peak: [], platform_reign: [], platform_switch_day: [], playback_milestones: [] },
    }

    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={['/analysis/records?from=summary&family=longevity']}>
          <PlaybackRecordsExperience data={data} />
          <RouterStateProbe />
        </MemoryRouter>
      </ThemeProvider>,
    )

    expect(screen.getByRole('tab', { name: '长线陪伴' })).toHaveAttribute('aria-selected', 'true')
    await screen.findByRole('heading', { name: /^最长连续播放天数/ })
    fireEvent.click(screen.getByRole('tab', { name: '个人王朝' }))
    expect(screen.getByTestId('router-state')).toHaveTextContent('?from=summary&family=reigns|REPLACE')
  })

  it('把单日爆听与单日时长合为一张可切换榜单', () => {
    renderObsession()

    expect(screen.getByText('单日巅峰 · Daily Peak')).toBeInTheDocument()
    expect(screen.getByText('次数冠军')).toBeInTheDocument()
    expect(screen.queryByText('时长冠军')).not.toBeInTheDocument()

    fireEvent.click(
      screen.getByRole('button', {
        name: '排名口径：播放次数。点击切换为听歌时长',
      }),
    )

    expect(screen.getByText('时长冠军')).toBeInTheDocument()
    expect(screen.queryByText('次数冠军')).not.toBeInTheDocument()
  })

  it('为播放记录里的专辑名称生成详情页链接', () => {
    renderObsession()
    const dailyPeakCard = screen
      .getByText('单日巅峰 · Daily Peak')
      .closest('.rounded-\\[16px\\]')
    expect(dailyPeakCard).not.toBeNull()
    fireEvent.click(within(dailyPeakCard as HTMLElement).getByRole('tab', { name: '专辑' }))

    expect(screen.getByRole('link', { name: 'Album / Deluxe' })).toHaveAttribute(
      'href',
      '/music/albums/Album%20%2F%20Deluxe?artist=Artist%20%26%20Co.',
    )
  })

  it('用后端保留的真实 track id 链接单日总量最高歌曲', () => {
    const data = obsessionData()
    data.daily_total_record = [row('2026-01-01', 100, {
      date: '2026-01-01',
      total_plays: 100,
      total_hours: 5,
      unique_tracks: 20,
      top_track_name: '最高歌曲',
      top_track_entity_id: 'real-track-123',
      top_track_artist_name: '最高艺人',
      top_track_plays: 9,
      top_album_name: '最高专辑',
      top_album_artist_name: '最高艺人',
      top_album_plays: 12,
      top_artist_name: '最高艺人',
      top_artist_plays: 18,
    })]

    render(
      <MemoryRouter>
        <ObsessionSection data={data} reigns={{ daily_champion: emptyFamily(), monthly_reign: emptyFamily(), yearly_reign: emptyFamily(), fastest_milestone: emptyFamily(), consecutive_champion_days: emptyFamily() }} behavior={{ skip_storm: emptyFamily(), shuffle_peak: [], platform_reign: [], platform_switch_day: [], playback_milestones: [] }} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: /最高歌曲/ })).toHaveAttribute(
      'href',
      '/music/tracks/real-track-123',
    )
  })

  it('按当前榜单最大值绘制单日时长和马拉松双指标视觉条', () => {
    renderObsession()
    fireEvent.click(
      screen.getByRole('button', {
        name: '排名口径：播放次数。点击切换为听歌时长',
      }),
    )

    const durationRunnerUp = screen.getByRole('meter', { name: '听歌时长：时长亚军' })
    expect(durationRunnerUp.querySelector('[data-value-bar-fill]')).toHaveStyle({ width: '50%' })

    const runRunnerUp = screen.getByRole('meter', { name: '连续次数：马拉松亚军' })
    expect(runRunnerUp.querySelector('[data-value-bar-fill]')).toHaveStyle({ width: '50%' })

    const hoursRunnerUp = screen.getByRole('meter', { name: '马拉松时长：马拉松亚军' })
    expect(hoursRunnerUp.querySelector('[data-value-bar-fill]')).toHaveStyle({ width: '50%' })
  })

  it('按榜单最大值绘制连续播放天数，并移除用户活跃天数卡片', () => {
    const longestStreak = emptyFamily()
    longestStreak.track = [
      row('连续冠军', 10, { unit: '天' }),
      row('连续亚军', 5, { unit: '天' }),
    ]
    const data: PlaybackLongevityRecords = {
      longest_streak_days: longestStreak,
      longest_span: emptyFamily(),
      comeback_after_sleep: emptyFamily(),
      most_active_months: emptyFamily(),
      user_active_streak: [row('最长活跃', 99, { unit: '天' })],
    }

    render(
      <MemoryRouter>
        <LongevitySection data={data} />
      </MemoryRouter>,
    )

    const card = screen
      .getByText('最长连续播放天数 · Longest Streak')
      .closest('.rounded-\\[16px\\]')
    expect(card).not.toBeNull()
    const streakMeter = within(card as HTMLElement).getByRole('meter', {
      name: '连续天数：连续亚军',
    })
    expect(streakMeter.querySelector('[data-value-bar-fill]')).toHaveStyle({ width: '50%' })
    expect(screen.queryByText('用户连续活跃天数 · User Active Streak')).not.toBeInTheDocument()
    expect(screen.queryByText('最长活跃')).not.toBeInTheDocument()
  })

  it('切换到较短实体榜单时自动收敛分页，不留下空表', () => {
    const trackRows = Array.from({ length: 11 }, (_, index) => row(`歌曲 ${index + 1}`, 20 - index))
    render(
      <MemoryRouter>
        <EntityRecordCard
          title="分页切换测试"
          recordsByEntity={{ track: trackRows, album: [row('短榜专辑', 1)] }}
          columns={() => [
            { header: '名称', render: (item) => <span>{item.name}</span> },
          ]}
        />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: '下一页' }))
    expect(screen.getByText('歌曲 11')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: '专辑' }))

    expect(screen.getByText('短榜专辑')).toBeInTheDocument()
    expect(screen.queryByText('歌曲 11')).not.toBeInTheDocument()
  })

  it('区分逐月冠军与累计月冠军，并移除重复年度巅峰', () => {
    const timeData: PlaybackTimePatternRecords = {
      hourly_dominance: {
        track: [
          row('凌晨完整长歌名不会被截断', 4, { date: '0:00', entity_id: 'hour-0', artist_name: '凌晨艺人', cover_url: '/covers/albums/hour-0.jpg' }),
          row('上午冠军', 8, { date: '8:00', entity_id: 'hour-8' }),
          row('晚间冠军', 16, { date: '16:00', entity_id: 'hour-16' }),
        ],
        album: [row('上午专辑', 6, { date: '8:00', artist_name: '专辑艺人' })],
        artist: [row('晚间艺人', 9, { date: '16:00' })],
      },
      monthly_peak: { ...emptyFamily(), track: [row('逐月冠军', 8, { date: '2026-01' })] },
      yearly_peak: { ...emptyFamily(), track: [row('重复年冠军', 99, { date: '2026' })] },
      late_night_peak_day: [],
      weekday_preference: [],
    }
    const reignData: PlaybackReignRecords = {
      daily_champion: emptyFamily(),
      monthly_reign: { ...emptyFamily(), track: [row('累计月冠军', 3, { unit: '月冠军' })] },
      yearly_reign: emptyFamily(),
      fastest_milestone: emptyFamily(),
      consecutive_champion_days: emptyFamily(),
    }

    const { container, unmount } = renderTimePatterns(timeData)
    expect(screen.getByText('逐个自然月列出当月播放次数最高的歌曲/专辑/艺人')).toBeInTheDocument()
    expect(screen.getByText('逐月冠军')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: '0:00-7:00 歌曲时段冠军' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: '8:00-15:00 歌曲时段冠军' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: '16:00-23:00 歌曲时段冠军' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '0:00-7:00' })).not.toBeInTheDocument()
    expect(screen.getAllByText('凌晨完整长歌名不会被截断')).toHaveLength(2)
    expect(container.querySelector('img[src="/covers/albums/hour-0.jpg"]')).not.toBeNull()
    expect(container.querySelectorAll('[data-hour-offset="0"]')).toHaveLength(3)
    expect(screen.queryByLabelText('下一页')).not.toBeInTheDocument()
    expect(screen.getByText('观察一天中的听歌时段、逐月冠军，以及深夜聆听比例如何随时间变化。')).toBeInTheDocument()
    expect(screen.queryByText('年度巅峰 · Yearly Peak')).not.toBeInTheDocument()
    expect(screen.queryByText("跨年时刻 · New Year's Eve")).not.toBeInTheDocument()
    expect(screen.queryByText('重复年冠军')).not.toBeInTheDocument()
    unmount()

    render(<MemoryRouter><ReignsSection data={reignData} /></MemoryRouter>)
    expect(screen.getByText('累计获得自然月播放冠军次数最多的歌曲/专辑/艺人')).toBeInTheDocument()
    expect(screen.getByText('累计月冠军')).toBeInTheDocument()
    expect(screen.queryByText('最快里程碑 · Fastest Milestone')).not.toBeInTheDocument()
  })

  it('深夜聆听轨迹默认按月，并可切换到季度最高合格样本', () => {
    const timeData: PlaybackTimePatternRecords = {
      hourly_dominance: emptyFamily(),
      monthly_peak: emptyFamily(),
      yearly_peak: emptyFamily(),
      late_night_peak_day: [],
      weekday_preference: [],
      late_night_trajectory: {
        monthly_min_plays: 500,
        quarterly_min_plays: 1500,
        monthly: [row('2026-01', 20, { total_plays: 499, secondary_value: 100, qualified: false })],
        quarterly: [row('2026Q1', 12.5, { total_plays: 1600, secondary_value: 200, qualified: true })],
      },
    }

    renderTimePatterns(timeData)

    expect(screen.getByText('深夜聆听轨迹 · Late-night Listening')).toBeInTheDocument()
    expect(screen.getByText('暂无可比较的月')).toBeInTheDocument()
    expect(screen.queryByText(/低样本/)).not.toBeInTheDocument()
    expect(screen.queryByText(/样本量不足/)).not.toBeInTheDocument()
    expect(screen.queryByText(/灰色/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '按季度' }))
    expect(screen.getByText('2026Q1 · 12.5%')).toBeInTheDocument()
    expect(screen.getByText('200 次深夜播放 / 1,600 次有效播放')).toBeInTheDocument()
  })

  it('用专辑全碟回放替换完成度榜，并显示覆盖与总播放', () => {
    const data: PlaybackDiscoveryRecords = {
      discovery_day: emptyFamily(),
      longest_no_repeat: { ...emptyFamily(), track: [row('最长不重复歌曲序列', 20)] },
      album_completionist: {
        ...emptyFamily(),
        album: [row('完整专辑', 2, {
          unit: '次完整回放',
          artist_name: '测试艺人',
          secondary_value: 10,
          secondary_unit: '/ 10 首',
          total_plays: 31,
        })],
      },
      same_name_diff_artist: [],
      feat_lover: emptyFamily(),
    }

    render(<MemoryRouter><DiscoverySection data={data} /></MemoryRouter>)

    expect(screen.getByText('专辑全碟回放 · Full Album Replays')).toBeInTheDocument()
    expect(screen.getByText('完整专辑')).toBeInTheDocument()
    expect(screen.getByText('31 次')).toBeInTheDocument()
    expect(screen.queryByText('最长不重复序列 · Longest No-Repeat')).not.toBeInTheDocument()
    expect(screen.queryByText('最长不重复歌曲序列')).not.toBeInTheDocument()
  })

  it('发现日使用中文实体单位，并按当前实体最高值归一化红色视觉条', () => {
    const data: PlaybackDiscoveryRecords = {
      discovery_day: {
        track: [row('2026-01-01', 10, { unit: '首新歌' }), row('2026-01-02', 5, { unit: '首新歌' })],
        album: [row('2026-02-01', 4, { unit: '张新专辑' })],
        artist: [row('2026-03-01', 3, { unit: '位新艺人' })],
      },
      longest_no_repeat: emptyFamily(),
      album_completionist: emptyFamily(),
      same_name_diff_artist: [],
      feat_lover: emptyFamily(),
    }

    render(<MemoryRouter><DiscoverySection data={data} /></MemoryRouter>)

    expect(screen.getAllByText('首新歌')).toHaveLength(2)
    expect(screen.getByRole('meter', { name: '2026-01-01新发现数量' }).querySelector('[data-value-bar-fill]')).toHaveStyle({ width: '100%' })
    expect(screen.getByRole('meter', { name: '2026-01-02新发现数量' }).querySelector('[data-value-bar-fill]')).toHaveStyle({ width: '50%' })
    const card = screen.getByText('发现日 · Discovery Day').parentElement?.parentElement?.parentElement as HTMLElement
    fireEvent.click(within(card).getByRole('tab', { name: '专辑' }))
    expect(within(card).getByText('张新专辑')).toBeInTheDocument()
    fireEvent.click(within(card).getByRole('tab', { name: '艺人' }))
    expect(within(card).getByText('位新艺人')).toBeInTheDocument()
  })

  it('把合作曲占比并入排行标题，并用完整艺人头像列表对照同名异曲', () => {
    const data: PlaybackDiscoveryRecords = {
      discovery_day: emptyFamily(),
      longest_no_repeat: emptyFamily(),
      album_completionist: emptyFamily(),
      feat_lover: {
        track: [
          row('合作曲播放佔比', 12.5, { rank: 0, unit: '%', secondary_value: 125 }),
          row('合作歌曲', 1341, { artist_name: '合作艺人', unit: '合作曲播放' }),
          row('合作歌曲二', 670, { artist_name: '合作艺人二', unit: '合作曲播放' }),
        ],
        album: [row('合作专辑', 100, { artist_name: '专辑艺人' })],
        artist: [row('合作艺人', 80, { unit: '合作曲播放' })],
      },
      same_name_diff_artist: [row('Home', 3, {
        artist_names: ['Artist One', 'Artist Two With A Complete Long Name', '艺人三'],
        artist_cover_urls: ['/covers/artists/1.jpg', null, null],
        artist_play_counts: [30, 20, 10],
      })],
    }

    render(<MemoryRouter><DiscoverySection data={data} /></MemoryRouter>)

    const summary = screen.getByLabelText('合作曲播放摘要')
    expect(within(summary).getByText('125')).toBeInTheDocument()
    expect(within(summary).getByText('12.5%')).toBeInTheDocument()
    expect(screen.queryByText(/合作曲占全部有效播放 12.5% · 共/)).not.toBeInTheDocument()
    expect(screen.queryByText('合作曲总体占比 · Collaboration Share')).not.toBeInTheDocument()
    expect(screen.getByText('Home')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '歌名' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '艺人版本' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Artist One30 次' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Artist Two With A Complete Long Name20 次' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '艺人三10 次' })).toBeInTheDocument()
    expect(screen.getByText('30 次')).toBeInTheDocument()
    expect(screen.getByText('20 次')).toBeInTheDocument()
    expect(screen.getByText('10 次')).toBeInTheDocument()
    expect(screen.queryByText('示例')).not.toBeInTheDocument()
    expect(screen.getByText('1,341')).toBeInTheDocument()
    expect(screen.queryByText('合作曲播放')).not.toBeInTheDocument()
    expect(screen.getByRole('meter', { name: '合作歌曲合作曲播放次数' }).querySelector('[data-value-bar-fill]')).toHaveStyle({ width: '100%' })
    expect((screen.getByRole('meter', { name: '合作歌曲二合作曲播放次数' }).querySelector('[data-value-bar-fill]') as HTMLElement).style.width).toMatch(/^49\./)
    const featCard = screen.getByText('合作曲排行 · Feat Ranking').parentElement?.parentElement?.parentElement as HTMLElement
    fireEvent.click(within(featCard).getByRole('tab', { name: '专辑' }))
    expect(within(featCard).getByRole('meter', { name: '合作专辑合作曲播放次数' })).toBeInTheDocument()
    fireEvent.click(within(featCard).getByRole('tab', { name: '艺人' }))
    expect(within(featCard).getByRole('meter', { name: '合作艺人合作曲播放次数' })).toBeInTheDocument()
  })

  it('播放里程碑显示封面、完整数字和“第 N 次播放”文案', () => {
    const data: PlaybackBehaviorRecords = {
      skip_storm: { ...emptyFamily(), track: [row('快进歌曲', 80)] },
      shuffle_peak: [row('Shuffle 日期', 90)],
      platform_reign: [],
      platform_switch_day: [row('切换日期', 5)],
      playback_milestones: [row('里程碑歌曲', 1000, { entity_id: 'milestone-track', artist_name: '里程碑艺人', cover_url: '/covers/albums/1.jpg', date: '2026-01-01', caption: '第 1,000 次播放', total_plays: 64986 })],
    }

    const { container } = render(<MemoryRouter><PlaybackMilestonesCard data={data} /></MemoryRouter>)

    expect(screen.getByText('当前共 64,986 次有效播放 · 仅展示已经完成的动态标准节点')).toBeInTheDocument()
    expect(screen.getByText('1,000')).toBeInTheDocument()
    expect(screen.getByText('里程碑歌曲')).toBeInTheDocument()
    expect(screen.getByText('里程碑艺人')).toBeInTheDocument()
    expect(screen.getByText('第 1,000 次播放')).toBeInTheDocument()
    expect(screen.queryByText(/累计播放/)).not.toBeInTheDocument()
    expect(screen.queryByText('播放节点')).not.toBeInTheDocument()
    expect(container.querySelector('img[src="/covers/albums/1.jpg"]')).not.toBeNull()
  })
})
