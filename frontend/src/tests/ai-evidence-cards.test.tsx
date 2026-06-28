import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AIEvidenceCards } from '@/features/ai-tasks/AIEvidenceCards'

describe('AIEvidenceCards', () => {
  it('renders compact evidence metrics and limitations', () => {
    render(
      <AIEvidenceCards
        cards={[
          {
            card_id: 'album:GUTS:entity_stats',
            title: 'GUTS 播放统计',
            entity_name: 'GUTS',
            entity_type: 'album',
            question_axis: 'personal_playback',
            source: { tool_name: 'entity_stats', source_range: 'lifetime' },
            metrics: [
              { name: 'total_plays', label: '播放次数', value: 1749, unit: 'plays' },
            ],
            observations: ['累计播放明显领先同窗专辑'],
            limitations: ['全时期累计口径'],
          },
        ]}
      />,
    )

    expect(screen.getByText('证据卡片')).toBeInTheDocument()
    expect(screen.getByText('GUTS 播放统计')).toBeInTheDocument()
    expect(screen.getByText('entity_stats')).toBeInTheDocument()
    expect(screen.getByText('lifetime')).toBeInTheDocument()
    expect(screen.getByText('播放次数')).toBeInTheDocument()
    expect(screen.getByText('1749 plays')).toBeInTheDocument()
    expect(screen.getByText('累计播放明显领先同窗专辑')).toBeInTheDocument()
    expect(screen.getByText('全时期累计口径')).toBeInTheDocument()
  })

  it('renders nullish metric values as no data', () => {
    render(
      <AIEvidenceCards
        cards={[
          {
            card_id: 'track:unknown:billboard',
            title: '未知歌曲榜单表现',
            source: { tool_name: 'billboard_entity_detail' },
            metrics: [
              { name: 'peak_rank', label: '最高排名', value: null },
            ],
          },
        ]}
      />,
    )

    expect(screen.getByText('无数据')).toBeInTheDocument()
  })

  it('does not render a stray zero when notes are empty', () => {
    const { container } = render(
      <AIEvidenceCards
        cards={[
          {
            card_id: 'album:GUTS:empty-notes',
            title: 'GUTS 证据',
            source: { tool_name: 'entity_stats' },
            metrics: [
              { name: 'total_plays', label: '播放次数', value: 1749 },
            ],
            observations: [],
            limitations: [],
          },
        ]}
      />,
    )

    const hasStrayZeroTextNode = Array.from(container.querySelectorAll('article')).some((article) =>
      Array.from(article.childNodes).some(
        (node) => node.nodeType === Node.TEXT_NODE && node.textContent?.trim() === '0',
      ),
    )
    expect(hasStrayZeroTextNode).toBe(false)
  })
})
