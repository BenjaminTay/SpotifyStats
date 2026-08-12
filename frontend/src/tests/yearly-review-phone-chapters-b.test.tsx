import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { MobileAppendixChapter } from '@/features/mobile/yearly-v2/chapters/MobileAppendixChapter'
import { MobileEpilogueChapter } from '@/features/mobile/yearly-v2/chapters/MobileEpilogueChapter'
import { MobileRecordsChapter } from '@/features/mobile/yearly-v2/chapters/MobileRecordsChapter'
import { MobileTasteMigrationChapter } from '@/features/mobile/yearly-v2/chapters/MobileTasteMigrationChapter'
import type { YearlyEntityRef, YearlyReviewResponse } from '@/types/yearly-review-v2'

function entity(name: string, entityType: YearlyEntityRef['entity_type'] = 'track'): YearlyEntityRef {
  return {
    entity_type: entityType,
    entity_id: name,
    name,
    artist_name: entityType === 'artist' ? null : '测试艺人',
    cover_url: `/covers/${name}.jpg`,
    deep_link: null,
  }
}

function chartRows(prefix: string, count: number) {
  return Array.from({ length: count }, (_, index) => ({
    rank: index + 1,
    year_end_rank: index + 1,
    track_id: index + 1,
    name: `${prefix} ${index + 1}`,
    artist_name: '测试艺人',
    cover_url: `/covers/${index + 1}.jpg`,
    plays: 100 - index,
    hours: 20 - index / 2,
    year_end_score: 1000 - index * 10,
  }))
}

function report(): YearlyReviewResponse {
  const records = Array.from({ length: 7 }, (_, index) => ({
    record_id: `record-${index + 1}`,
    category: index === 0 ? 'obsession' : 'behavior',
    fact_type: 'test',
    title: `纪录标题 ${index + 1}`,
    statement: `纪录故事 ${index + 1}`,
    evidence_grade: 'A' as const,
    entity_refs: [entity(`纪录歌曲 ${index + 1}`)],
    metrics: [{ key: 'plays', label: '播放次数', value: 20 + index, unit: '次', comparison_value: null, comparison_label: null }],
    source_refs: [],
    deep_link: null,
  }))

  return {
    year: 2025,
    coverage: {
      taste: {
        style: { level: 'core' },
        scene: { level: 'secondary' },
        language: { level: 'core' },
        release_era: { level: 'core' },
      },
    },
    records: { featured: records, catalog_counts: {}, policy_version: 'test' },
    taste_migration: {
      comparison: {
        status: 'available',
        mode: 'half_years',
        from_label: '上半年',
        to_label: '下半年',
      },
      observations: [{
        headline_id: 'taste_migration_style',
        title: '从流行走向摇滚',
        statement: '下半年的听感更有力量。',
        entity_refs: [entity('摇滚代表作')],
      }],
      distributions: {
        style: [{ key: 'pop', label: 'Pop', share_pct: 62.5 }, { key: 'rock', label: 'Rock', share_pct: 37.5 }],
        scene: [{ key: 'mandopop', label: '华语流行', share_pct: 80 }],
        language: [{ key: 'zh', label: '中文', share_pct: 70 }],
        release_era: [{ key: '2020s', label: '2020s', share_pct: 55 }],
      },
      changes: {
        style: [{ key: 'rock', label: 'Rock', from_pct: 20, to_pct: 35, delta_pct: 15 }],
        scene: [],
        language: [],
        release_era: [],
      },
    },
    epilogue: {
      conclusions: [{
        headline_id: 'ending-1',
        title: '这一年的听歌节奏',
        statement: '比去年听得更多，也遇见了更多新歌。',
        primary_metric: { key: 'new', label: '新歌', value: 128, unit: '首', comparison_value: null, comparison_label: null },
        entity_refs: [entity('年度留下的歌')],
      }],
      new_history_tops: [entity('历史新高歌曲')],
      next_year_carryovers: [entity('带往明年的艺人', 'artist')],
    },
    appendix: {
      play_charts: {
        track_by_plays: chartRows('播放歌曲', 12),
        track_by_hours: chartRows('时长歌曲', 12),
        album_by_plays: [],
        album_by_hours: [],
        artist_by_plays: [],
        artist_by_hours: [],
      },
      billboard_charts: { track: chartRows('榜单歌曲', 12), album: [], artist: [] },
      monthly_champions: [],
      record_catalog_counts: {},
    },
  } as unknown as YearlyReviewResponse
}

function renderChapter(node: React.ReactNode) {
  return render(<MemoryRouter>{node}</MemoryRouter>)
}

describe('Yearly Review V2 phone chapters B', () => {
  it('展示全部精选纪录，并把首条作为主视觉', () => {
    const { container } = renderChapter(<MobileRecordsChapter report={report()} />)
    expect(screen.getAllByText(/\u7eaa\u5f55\u6545\u4e8b/)).toHaveLength(7)
    expect(container.querySelector('.mobile-yearly-v2-record-card.is-featured')).toHaveTextContent('纪录故事 1')
    expect(screen.queryByText('更多年度纪录')).not.toBeInTheDocument()
  })

  it('用可切换的全宽分布条和变化故事展示品味迁移', async () => {
    const user = userEvent.setup()
    const { container } = renderChapter(<MobileTasteMigrationChapter report={report()} />)

    expect(screen.getByRole('progressbar', { name: 'Pop占比' })).toHaveAttribute('aria-valuenow', '62.5')
    expect(screen.getByText('从流行走向摇滚')).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: '语言' }))
    expect(screen.getByRole('progressbar', { name: '中文占比' })).toBeInTheDocument()
    expect(container).not.toHaveTextContent('统计口径')
    expect(container).not.toHaveTextContent('coverage')
  })

  it('把结语按序号单列呈现，并保留关联实体', () => {
    const { container } = renderChapter(<MobileEpilogueChapter report={report()} />)
    expect(screen.getByText('01')).toBeInTheDocument()
    expect(screen.getByText('比去年听得更多，也遇见了更多新歌。')).toBeInTheDocument()
    expect(screen.getByText('年度留下的歌')).toBeInTheDocument()
    expect(screen.getByText('带往明年的艺人')).toBeInTheDocument()
    expect(container.querySelector('.mobile-yearly-v2-epilogue-shelf')).toBeInTheDocument()
  })

  it('结语正文已写出数字时不重复显示主指标', () => {
    const data = report()
    data.epilogue.conclusions[0].statement = '比去年少听了 5.5%。'
    data.epilogue.conclusions[0].primary_metric = {
      key: 'change', label: '播放时长变化', value: -5.5, unit: '%', comparison_value: null, comparison_label: null,
    }
    renderChapter(<MobileEpilogueChapter report={data} />)
    expect(screen.getByText('比去年少听了 5.5%。')).toBeInTheDocument()
    expect(screen.queryByText(/播放时长变化/)).not.toBeInTheDocument()
  })

  it('正文只预览 Top 5，全屏榜单每页 10 条且关闭后恢复焦点', async () => {
    const user = userEvent.setup()
    const { container } = renderChapter(<MobileAppendixChapter report={report()} />)
    const opener = screen.getByRole('button', { name: /\u67e5\u770b\u5b8c\u6574\u699c\u5355/ })
    expect(container.querySelector('.mobile-yearly-v2-appendix-controls.is-preview')).toBeInTheDocument()

    expect(container.querySelector('table')).not.toBeInTheDocument()
    expect(screen.getByText('播放歌曲 5')).toBeInTheDocument()
    expect(screen.queryByText('播放歌曲 6')).not.toBeInTheDocument()

    opener.focus()
    await user.click(opener)
    const dialog = screen.getByRole('dialog', { name: '完整榜单' })
    expect(dialog.querySelector('.mobile-yearly-v2-appendix-controls.is-dialog')).toBeInTheDocument()
    expect(within(dialog).getAllByRole('listitem')).toHaveLength(10)
    expect(within(dialog).getByText('播放歌曲 10')).toBeInTheDocument()
    expect(within(dialog).queryByText('播放歌曲 11')).not.toBeInTheDocument()

    await user.click(within(dialog).getByRole('button', { name: /\u4e0b\u4e00\u9875/ }))
    expect(within(dialog).getByText('播放歌曲 11')).toBeInTheDocument()
    expect(within(dialog).getAllByRole('listitem')).toHaveLength(2)

    await user.click(within(dialog).getByRole('tab', { name: '个人 Billboard' }))
    expect(within(dialog).getByText('榜单歌曲 1')).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '完整榜单' })).not.toBeInTheDocument())
    await waitFor(() => expect(opener).toHaveFocus())
  })
})
