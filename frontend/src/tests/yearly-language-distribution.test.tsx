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
    expect(screen.getByText('已分类 70%')).toBeInTheDocument()
    expect(screen.getByText('未知 30%')).toBeInTheDocument()
    expect(screen.getByText('7 小时')).toBeInTheDocument()
    expect(screen.getByText('2 位艺人')).toBeInTheDocument()
    expect(screen.getByText('艺人级估算，按主艺人归属。')).toBeInTheDocument()
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

    expect(
      screen.getByText('另有 1.25 小时因无法归属主艺人而未纳入语言分布。'),
    ).toBeInTheDocument()
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
    expect(screen.queryByText('语言分布')).not.toBeInTheDocument()
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
    expect(screen.queryByText('语言分布')).not.toBeInTheDocument()
  })
})
