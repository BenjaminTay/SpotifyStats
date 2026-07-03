import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ReportCard } from '@/features/ai-insights/ReportCard'
import { VisualYearlyReport } from '@/features/ai-insights/yearly-artifact/VisualYearlyReport'
import type { VisualYearlyArtifact } from '@/features/ai-insights/yearly-artifact/yearlyArtifactTypes'

const EDITORIAL_METADATA_SENTINEL = 'DO_NOT_RENDER_EDITORIAL_METADATA'

function artifact(): VisualYearlyArtifact {
  return {
    report_mode: 'visual_yearly_artifact',
    contract_version: 'visual_yearly_v1',
    title: '你的 2025 音乐年记',
    subtitle: '几乎没有离开音乐的一年',
    period: {
      year: 2025,
      start_date: '2025-01-01',
      end_date: '2025-12-31',
      is_partial_year: false,
    },
    narrative_brief: {},
    visual_brief: {},
    sections: [
      {
        id: 'opening',
        role: 'opening',
        heading: '几乎没有离开音乐的一年',
        deck: '364 个活跃日说明音乐几乎每天都在场。',
        prose: '这一年，音乐几乎没有从你的日常里退场。',
        chart_refs: ['listening_calendar'],
        insight_refs: ['activity_density'],
        evidence_refs: ['yearly_overview'],
        pull_quote: '音乐不是偶尔打开的背景。',
      },
    ],
    insight_cards: [
      {
        id: 'activity_density',
        label: '全年陪伴密度',
        value: '364 天',
        caption: '这一年几乎每天都有音乐在场。',
        tone: 'warm',
        evidence_refs: [],
      },
    ],
    chart_specs: [
      {
        id: 'listening_calendar',
        chart_type: 'listening_calendar_heatmap',
        title: '音乐铺满这一年',
        narrative_question: '音乐是否每天都在场？',
        entities: [],
        data_key: 'listening_calendar',
        insight: '364 个活跃日。',
        fallback: '显示活跃日。',
      },
    ],
    chart_data: {
      listening_calendar: {
        days: [],
        active_days: 364,
      },
    },
    metadata: {
      report_mode: 'visual_yearly_artifact',
      contract_version: 'visual_yearly_v1',
      section_count: 1,
      chart_count: 1,
      insight_card_count: 1,
      article_length: 40,
      critic_passed: true,
      fact_validation_passed: true,
      fallback_level: null,
    },
  }
}

function artifactWithEditorialMetadata(): VisualYearlyArtifact {
  const value = artifact()
  value.metadata = {
    ...value.metadata,
    editorial_plan_version: 'yearly_editorial_v1',
    fact_count: 8,
    section_roles: [
      'opening',
      'main_artist',
      'turning_point',
      'album_story',
      'highlight_day',
      'closing',
    ],
    language_budget: { '入口': 2, '陪伴': 4 },
    editorial_debug_sentinel: EDITORIAL_METADATA_SENTINEL,
  }
  return value
}

describe('VisualYearlyReport', () => {
  it('renders hero, insight cards, sections, and chart blocks', () => {
    render(<VisualYearlyReport artifact={artifact()} />)

    expect(screen.getByText('你的 2025 音乐年记')).toBeInTheDocument()
    expect(screen.getByText('全年陪伴密度')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '几乎没有离开音乐的一年' })).toBeInTheDocument()
    expect(screen.getByText('音乐铺满这一年')).toBeInTheDocument()
  })

  it('tolerates editorial metadata without rendering raw metadata', () => {
    render(<VisualYearlyReport artifact={artifactWithEditorialMetadata()} />)

    expect(screen.getByText('你的 2025 音乐年记')).toBeInTheDocument()
    expect(screen.getByText('全年陪伴密度')).toBeInTheDocument()
    expect(screen.queryByText(new RegExp(EDITORIAL_METADATA_SENTINEL))).not.toBeInTheDocument()
    expect(screen.queryByText(/yearly_editorial_v1/)).not.toBeInTheDocument()
  })

  it('renders concrete chart labels for supported chart types', () => {
    const value = artifact()
    value.chart_specs = [
      {
        ...value.chart_specs[0],
        chart_type: 'listening_calendar_heatmap',
        id: 'listening_calendar',
      },
      {
        ...value.chart_specs[0],
        chart_type: 'album_duality_compare',
        id: 'album_duality_compare',
        title: '两张专辑，两种喜欢',
      },
      {
        ...value.chart_specs[0],
        chart_type: 'artist_monthly_trend',
        id: 'artist_monthly_trend',
        title: '艺人月度趋势',
      },
      {
        ...value.chart_specs[0],
        chart_type: 'genre_language_mix',
        id: 'genre_language_mix',
        title: '你的音乐地理',
      },
      {
        ...value.chart_specs[0],
        chart_type: 'highlight_day_timeline',
        id: 'highlight_day_timeline',
        title: '高光日播放切片',
      },
      {
        ...value.chart_specs[0],
        chart_type: 'discovery_timeline',
        id: 'discovery_timeline',
        title: '新声音出现时间线',
      },
      {
        ...value.chart_specs[0],
        chart_type: 'playback_billboard_matrix',
        id: 'playback_billboard_matrix',
        title: '播放与个人榜单位置',
      },
    ]
    value.chart_data = {
      listening_calendar: {
        days: [
          { date: '2025-01-01', plays: 2, minutes: 6 },
          { date: '2025-03-09', plays: 5, minutes: 15 },
        ],
        active_days: 2,
      },
      album_duality_compare: {
        playback_leader: {
          name: 'The Life of a Showgirl',
          artist: 'Taylor Swift',
          plays: 1106,
        },
        chart_leader: {
          name: '光良「回憶裡的瘋狂」巡迴演唱會',
          artist: 'Michael Wong',
          weeks_on_chart: 32,
        },
      },
      artist_monthly_trend: {
        entities: ['Taylor Swift', 'Michael Wong'],
        months: [
          { month: '2025-03', 'Taylor Swift': 20, 'Michael Wong': 0 },
          { month: '2025-04', 'Taylor Swift': 35, 'Michael Wong': 18 },
        ],
      },
      genre_language_mix: {
        genres: [{ name: 'mandopop', share: 16.7 }],
      },
      highlight_day_timeline: {
        date: '2025-02-14',
        hourly: [{ hour: 21, plays: 4 }],
        top_tracks: [{ name: 'Changes', artist: 'Charlie Puth', plays: 4 }],
      },
      discovery_timeline: {
        new_artists: [{ name: 'JOLIN', first_date: '2025-05-08', plays: 108 }],
      },
      playback_billboard_matrix: {
        items: [
          {
            name: 'The Fate of Ophelia',
            type: 'track',
            artist: 'Taylor Swift',
            plays: 190,
            weeks_on_chart: 13,
            peak_position: 1,
          },
          {
            name: '1989 (Taylor’s Version)',
            type: 'album',
            plays: 1106,
            weeks_on_chart: 9,
            peak_rank: 2,
          },
          {
            name: 'Taylor Swift',
            type: 'artist',
            plays: 5020,
            weeks_on_chart: 28,
            peak_rank: 1,
          },
          {
            name: 'unknown',
            type: 'track',
            artist: 'unknown',
            plays: Number.NaN,
            weeks_on_chart: null,
            peak_rank: null,
          },
          {
            name: 'Midnight Rain',
            type: 'track',
            plays: Number.NaN,
            weeks_on_chart: 4,
          },
        ],
        observations: [
          'The Fate of Ophelia 是单曲里兼具高播放和长在榜的核心作品。',
          'Taylor Swift 是艺人里兼具高播放和长在榜的核心对象。',
          '第三条观察不应默认挤占图表空间。',
        ],
      },
    }
    value.sections[0].chart_refs = [
      'listening_calendar',
      'album_duality_compare',
      'artist_monthly_trend',
      'genre_language_mix',
      'highlight_day_timeline',
      'discovery_timeline',
      'playback_billboard_matrix',
    ]

    render(<VisualYearlyReport artifact={value} />)

    expect(screen.getByText('活跃 2 天')).toBeInTheDocument()
    expect(screen.getByText('The Life of a Showgirl')).toBeInTheDocument()
    expect(screen.getByText('光良「回憶裡的瘋狂」巡迴演唱會')).toBeInTheDocument()
    expect(screen.getAllByText('Taylor Swift').length).toBeGreaterThan(0)
    expect(screen.getByText('mandopop')).toBeInTheDocument()
    expect(screen.getByText('Changes · Charlie Puth')).toBeInTheDocument()
    expect(screen.getByText('JOLIN')).toBeInTheDocument()
    expect(screen.getByText('2025-05-08 · 108 次')).toBeInTheDocument()
    expect(screen.getByLabelText('Taylor Swift 3 月 20 次')).toBeInTheDocument()
    expect(screen.getByLabelText('Taylor Swift 4 月 35 次')).toBeInTheDocument()
    expect(screen.getAllByText('单曲').length).toBeGreaterThan(0)
    expect(screen.getByText('专辑')).toBeInTheDocument()
    expect(screen.getByText('艺人')).toBeInTheDocument()
    expect(screen.getByText('190 次播放 · 13 周在榜 · PK #1')).toBeInTheDocument()
    expect(screen.getByText('The Fate of Ophelia 是单曲里兼具高播放和长在榜的核心作品。')).toBeInTheDocument()
    expect(screen.getByText('Taylor Swift 是艺人里兼具高播放和长在榜的核心对象。')).toBeInTheDocument()
    expect(screen.queryByText('第三条观察不应默认挤占图表空间。')).not.toBeInTheDocument()
    expect(screen.queryAllByText(/unknown/i)).toHaveLength(0)
    expect(screen.queryByText(/NaN/)).not.toBeInTheDocument()
    expect(screen.queryByText(/undefined|null/)).not.toBeInTheDocument()
    expect(screen.queryByText('艺人月度趋势数据不足')).not.toBeInTheDocument()
    expect(screen.queryByText('曲风或语种占比数据不足')).not.toBeInTheDocument()
    expect(screen.queryByText('高光日数据不足')).not.toBeInTheDocument()
    expect(screen.queryByText('新发现时间线数据不足')).not.toBeInTheDocument()
  })

  it('ReportCard renders visual artifact instead of markdown when artifact exists', () => {
    render(
      <ReportCard
        artifact={artifact()}
        cached={false}
        cachedAt={null}
        entities={null}
        error={null}
        fetching={false}
        loading={false}
        onRetry={() => undefined}
        report="## Markdown fallback"
        reportType="yearly"
        title="年度叙事 · 2025"
      />,
    )

    expect(screen.getByText('你的 2025 音乐年记')).toBeInTheDocument()
    expect(screen.queryByText('Markdown fallback')).not.toBeInTheDocument()
  })

  it('ReportCard artifact branch tolerates editorial metadata without rendering raw metadata', () => {
    const value = artifactWithEditorialMetadata()

    render(
      <ReportCard
        artifact={value}
        cached={false}
        cachedAt={null}
        entities={null}
        error={null}
        fetching={false}
        loading={false}
        metadata={value.metadata}
        onRetry={() => undefined}
        report="## Markdown fallback"
        reportType="yearly"
        title="年度叙事 · 2025"
      />,
    )

    expect(screen.getByText('你的 2025 音乐年记')).toBeInTheDocument()
    expect(screen.queryByText('Markdown fallback')).not.toBeInTheDocument()
    expect(screen.queryByText(new RegExp(EDITORIAL_METADATA_SENTINEL))).not.toBeInTheDocument()
    expect(screen.queryByText(/yearly_editorial_v1/)).not.toBeInTheDocument()
  })
})
