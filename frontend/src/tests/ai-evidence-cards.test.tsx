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

  it('renders comparison winner metrics as a readable matrix', () => {
    const { container } = render(
      <AIEvidenceCards
        cards={[
          {
            card_id: 'album:comparison',
            title: '实体比较摘要',
            entity_type: 'album',
            question_axis: 'comparison',
            source: { tool_name: 'compare_entities', source_range: 'comparison' },
            metrics: [
              { name: 'winner_by_cumulative_plays', label: '累计播放胜出', value: 'GUTS' },
              {
                name: 'winner_by_total_hours',
                label: '播放时长胜出',
                value: 'The Life of a Showgirl',
              },
              { name: 'winner_by_power_score', label: '个人榜单 Power Score 胜出', value: 'GUTS' },
              {
                name: 'winner_by_intensity',
                label: '单位在榜周强度胜出',
                value: 'The Life of a Showgirl',
              },
            ],
            observations: ['对象进入你的播放历史时间不同，累计值和强度值需要分开看。'],
            limitations: ['比较结果必须说明口径。'],
          },
        ]}
      />,
    )

    expect(screen.getByText('累计播放胜出')).toBeInTheDocument()
    expect(screen.getAllByText('GUTS').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('单位在榜周强度胜出')).toBeInTheDocument()
    expect(screen.getAllByText('The Life of a Showgirl').length).toBeGreaterThanOrEqual(2)

    const metricsMatrix = container.querySelector('dl')
    expect(metricsMatrix).toHaveClass('grid-cols-1')
    expect(metricsMatrix).toHaveClass('sm:grid-cols-2')
    expect(metricsMatrix).not.toHaveClass('grid-cols-2')
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
