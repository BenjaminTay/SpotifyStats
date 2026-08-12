import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { MobileHonorsChapter } from '@/features/mobile/yearly-v2/chapters/MobileHonorsChapter'
import { MobileListeningLifeChapter } from '@/features/mobile/yearly-v2/chapters/MobileListeningLifeChapter'
import { MobileRelationshipsChapter } from '@/features/mobile/yearly-v2/chapters/MobileRelationshipsChapter'
import { MobileSeasonChapter } from '@/features/mobile/yearly-v2/chapters/MobileSeasonChapter'
import type { YearlyEntityRef, YearlyMetric, YearlyReviewResponse } from '@/types/yearly-review-v2'

function entity(entityType: YearlyEntityRef['entity_type'], name: string): YearlyEntityRef {
  return {
    entity_type: entityType,
    entity_id: name,
    name,
    artist_name: entityType === 'artist' ? null : '测试艺人',
    cover_url: `/covers/${encodeURIComponent(name)}.jpg`,
    deep_link: `/music/${entityType}s/${encodeURIComponent(name)}`,
  }
}

function metric(key: string, label: string, value: number, unit = '次'): YearlyMetric {
  return { key, label, value, unit, comparison_value: null, comparison_label: null }
}

const volumeTrack = entity('track', '播放冠军歌曲')
const chartTrack = entity('track', '年榜冠军歌曲')
const volumeAlbum = entity('album', '播放冠军专辑')
const chartAlbum = entity('album', '年榜冠军专辑')
const artist = entity('artist', '年度艺人')

const report = {
  year: 2025,
  honors: {
    play_leaders: {
      track: { honor_id: 'play-track', title: '播放冠军', entity: volumeTrack, metrics: [metric('plays', '播放', 120)], evidence_grade: 'A' },
      album: { honor_id: 'play-album', title: '播放冠军', entity: volumeAlbum, metrics: [metric('plays', '播放', 360)], evidence_grade: 'A' },
      artist: { honor_id: 'play-artist', title: '播放冠军', entity: artist, metrics: [metric('plays', '播放', 500)], evidence_grade: 'A' },
    },
    billboard_leaders: {
      track: { honor_id: 'chart-track', title: '年榜冠军', entity: chartTrack, metrics: [metric('score', '年度积分', 3200, '分')], evidence_grade: 'A' },
      album: { honor_id: 'chart-album', title: '年榜冠军', entity: chartAlbum, metrics: [metric('score', '年度积分', 2800, '分')], evidence_grade: 'A' },
      artist: { honor_id: 'chart-artist', title: '年榜冠军', entity: artist, metrics: [metric('score', '年度积分', 4000, '分')], evidence_grade: 'A' },
    },
    divergence_stories: [{ entity: entity('track', '分歧歌曲'), play_rank: 15, billboard_year_end_rank: 45, rank_gap: 30, interpretation: 'volume_more_concentrated', evidence_grade: 'A' }],
    annual_honors: [{ honor_id: 'longest', title: '最长在榜歌曲', entity: entity('track', '长跑歌曲'), metrics: [metric('weeks', '在榜', 30, '周')], evidence_grade: 'A' }],
  },
  season: {
    stages: [{ stage_id: 'spring', label: '春日循环', start_month: 1, end_month: 3, entity_refs: [entity('album', '春日专辑')], evidence: [] }],
    turning_points: [{ point_id: 'turn', month: 2, date: '2025-02-14', event_type: 'discovery_peak', title: '二月遇见新歌', statement: '它改变了这一段时间的声音。', evidence_grade: 'A', entity_refs: [entity('track', '二月歌曲')], metrics: [] }],
    months: [
      { month: 1, plays: 11, hours: 1.2, active_days: 5, leaders: { play_track: entity('track', '一月冠军') }, comparisons: [], stage_id: 'spring', event_ids: [] },
      { month: 2, plays: 22, hours: 2.4, active_days: 8, leaders: { play_track: entity('track', '二月冠军') }, comparisons: [], stage_id: 'spring', event_ids: ['turn'] },
    ],
  },
  relationships: [{ story_id: 'companion', relationship_type: 'long_companion', title: '陪你走过这一年', statement: '十二个月里一直都在。', entity: artist, evidence_grade: 'C', evidence_status: 'sufficient', metrics: [metric('days', '陪伴', 300, '天')], source_refs: [] }],
  listening_life: {
    metrics: [metric('late', '深夜播放', 88)],
    observations: [
      { headline_id: 'lead', title: '你的黄金时段', statement: '夜晚是这一年的主场。', evidence_grade: 'A', evidence_status: 'sufficient', primary_metric: metric('share', '夜晚占比', 55, '%'), entity_refs: [entity('track', '夜晚歌曲')], source_refs: [] },
      { headline_id: 'second', title: '最长的一天', statement: '这一天音乐从早陪到晚。', evidence_grade: 'A', evidence_status: 'sufficient', primary_metric: metric('day-plays', '当天播放', 80), entity_refs: [entity('album', '当天专辑')], source_refs: [] },
    ],
  },
} as unknown as YearlyReviewResponse

function renderChapter(node: React.ReactNode) {
  return render(<MemoryRouter>{node}</MemoryRouter>)
}

describe('Yearly Review V2 phone chapters A', () => {
  it('switches honor entities while keeping divergence and artwork links visible', () => {
    const { container } = renderChapter(<MobileHonorsChapter report={report} />)
    expect(screen.getByRole('link', { name: /播放冠军歌曲/ })).toHaveAttribute('href', volumeTrack.deep_link)
    expect(screen.getByText('播放第 15 · 个人年榜第 45')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: '专辑' }))
    expect(screen.getByRole('link', { name: /播放冠军专辑/ })).toHaveAttribute('href', volumeAlbum.deep_link)
    expect(screen.getByRole('link', { name: /年榜冠军专辑/ })).toHaveAttribute('href', chartAlbum.deep_link)
    expect(container.querySelectorAll('a img').length).toBeGreaterThan(0)
  })

  it('uses a vertical season story and shows only the selected month panel', () => {
    const { container } = renderChapter(<MobileSeasonChapter report={report} />)
    expect(screen.getByRole('link', { name: /春日专辑/ })).toBeInTheDocument()
    expect(screen.getByText('二月遇见新歌')).toBeInTheDocument()
    expect(container.querySelector('.mobile-yearly-v2-timeline-index')).not.toBeInTheDocument()

    fireEvent.click(screen.getByText('十二个月，逐月翻阅'))
    fireEvent.click(screen.getByRole('tab', { name: '02' }))
    const panel = screen.getByRole('tabpanel')
    expect(within(panel).getByText('22')).toBeInTheDocument()
    expect(within(panel).getByText('FEB')).toBeInTheDocument()
    expect(within(panel).queryByText('2 月')).not.toBeInTheDocument()
    expect(within(panel).getByRole('link', { name: /二月冠军/ })).toBeInTheDocument()
    expect(within(panel).queryByRole('link', { name: /一月冠军/ })).not.toBeInTheDocument()
  })

  it('keeps every relationship and listening observation accessible as linked media', () => {
    renderChapter(
      <>
        <MobileRelationshipsChapter report={report} />
        <MobileListeningLifeChapter report={report} />
      </>,
    )
    expect(screen.getByText('陪你走过这一年')).toBeInTheDocument()
    expect(screen.getByText('夜晚是这一年的主场。')).toBeInTheDocument()
    expect(screen.getByText('这一天音乐从早陪到晚。')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /夜晚歌曲/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /当天专辑/ })).toBeInTheDocument()
    expect(screen.getByText('深夜播放')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /年度艺人/ })).toHaveAttribute('data-entity-type', 'artist')
  })

  it('does not repeat a primary metric already written in the listening story', () => {
    const duplicateReport = {
      ...report,
      listening_life: {
        metrics: [],
        observations: [{
          ...report.listening_life.observations[0],
          statement: '12–13 点最常听歌，一共播放了 1,664 次。',
          primary_metric: metric('peak-hour', '高峰小时播放', 1664),
        }],
      },
    } as YearlyReviewResponse
    renderChapter(<MobileListeningLifeChapter report={duplicateReport} />)
    expect(screen.getByText(/一共播放了 1,664 次/)).toBeInTheDocument()
    expect(screen.queryByText('高峰小时播放')).not.toBeInTheDocument()
  })
})
