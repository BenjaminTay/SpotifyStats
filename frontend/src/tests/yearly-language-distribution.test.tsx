import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { GenrePanorama } from '@/pages/yearly-review/GenrePanorama'
import type { LanguageDistribution } from '@/types/yearly-review'

function languageDistribution(
  overrides: Partial<LanguageDistribution> = {},
): LanguageDistribution {
  return {
    eligible_hours: 10,
    excluded_unattributed_hours: 1.25,
    classified_hours: 7,
    unknown_hours: 3,
    classified_pct: 70,
    unknown_pct: 30,
    buckets: [
      {
        key: 'es-419',
        label: '西班牙语（拉丁美洲）',
        classification: 'single_language',
        hours: 7,
        share_pct: 70,
        artist_count: 2,
      },
      {
        key: 'unknown',
        label: '未知',
        classification: 'unknown',
        hours: 3,
        share_pct: 30,
        artist_count: 1,
      },
    ],
    source_hours: { manual: 7 },
    top_missing: [{ artist_id: 9, artist_name: 'Unknown Artist', hours: 3 }],
    caveat: '艺人级估算，按主艺人归属。',
    ...overrides,
  }
}

describe('Yearly GenrePanorama language distribution', () => {
  it('renders dynamic backend buckets even when genre data is empty', () => {
    render(
      <GenrePanorama
        genrePanorama={{
          top_genres: [],
          monthly_genres: [],
          language_dist: languageDistribution(),
        }}
      />,
    )

    expect(screen.getByText('西班牙语（拉丁美洲）')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '语言' })).toBeInTheDocument()
    expect(screen.getByText('尚未归类')).toBeInTheDocument()
    expect(screen.getByText('7 小时')).toBeInTheDocument()
    expect(screen.queryByText('按艺人常用演唱语言与主艺人播放时长估算。')).not.toBeInTheDocument()
    expect(screen.queryByText(/审核|证据|置信|LLM|覆盖/)).not.toBeInTheDocument()
  })

  it('explains listening time excluded from primary-artist attribution', () => {
    render(
      <GenrePanorama
        genrePanorama={{
          top_genres: [],
          monthly_genres: [],
          language_dist: languageDistribution(),
        }}
      />,
    )

    expect(screen.queryByText(/无法归属主艺人/)).not.toBeInTheDocument()
  })

  it('renders genre data independently when language data is absent', () => {
    render(
      <GenrePanorama
        genrePanorama={{
          top_genres: [{ name: 'art pop', play_share: 42 }],
          monthly_genres: [],
          language_dist: null,
        }}
      />,
    )

    expect(screen.getByText('art pop')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '主曲风' })).toBeInTheDocument()
    expect(screen.queryByText(/曲风流派数据不足/)).not.toBeInTheDocument()
  })

  it('shows the empty state only when both genre and language data are absent', () => {
    render(
      <GenrePanorama
        genrePanorama={{
          top_genres: [],
          monthly_genres: [],
          language_dist: languageDistribution({ buckets: [] }),
        }}
      />,
    )

    expect(screen.getByText('曲风与语言数据不足，多听听歌获取更多洞察')).toBeInTheDocument()
    expect(screen.queryByText('Top 流派')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '语言' })).not.toBeInTheDocument()
  })

  it('renders consumer style and scene blocks without role or governance language', () => {
    render(
      <GenrePanorama
        genrePanorama={{
          display_taxonomy_version: 'consumer_v1',
          primary_styles: {
            axis: 'style', label: '主曲风', total_hours: 10, known_hours: 10, unknown_hours: 0, allows_multiple: true,
            buckets: [{ key: 'r&b/soul', label: 'R&B / Soul', hours: 10, share_pct: 100, artist_count: 1 }],
          },
          regional_pop: {
            axis: 'scene', label: '地区流行', total_hours: 10, known_hours: 10, unknown_hours: 0, allows_multiple: true,
            buckets: [{ key: 'c-pop', label: 'C-Pop', hours: 10, share_pct: 100, artist_count: 1 }],
          },
          top_genres: [],
          monthly_genres: [],
          axes: [{
            axis: 'role', label: '身份', hours: 10, share_pct: 100, coverage_pct: 100,
            unknown_hours: 0, unknown_pct: 0, canonical_count: 1, interpretation: 'role',
            buckets: [{ name: 'singer-songwriter', label: 'Singer-Songwriter', hours: 10, share_pct: 100, overall_share_pct: 100, confidence_tier: 'high', top_artists: [], risk_flags: [] }],
          }],
          language_dist: null,
        }}
      />,
    )

    expect(screen.getByText('R&B / Soul')).toBeInTheDocument()
    expect(screen.getByText('C-Pop')).toBeInTheDocument()
    expect(screen.queryByText('Singer-Songwriter')).not.toBeInTheDocument()
    expect(screen.queryByText(/占全部可归属有效聆听时长/)).not.toBeInTheDocument()
    expect(screen.queryByText(/一首华语 R&B/)).not.toBeInTheDocument()
    expect(screen.queryByText(/按艺人常用演唱语言/)).not.toBeInTheDocument()
    expect(screen.queryByText(/审核|证据|置信|LLM|覆盖/)).not.toBeInTheDocument()
  })
})
