import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { MobileTasteMigrationChapter } from '@/features/mobile/yearly-v2/chapters/MobileTasteMigrationChapter'
import { TasteMigrationChapter } from '@/features/yearly-review/taste-migration/TasteMigrationChapter'
import type { YearlyReviewResponse } from '@/types/yearly-review-v2'

function report(levels: Record<string, string> = { language: 'core' }): YearlyReviewResponse {
  return {
    coverage: {
      taste: Object.fromEntries(['style', 'scene', 'language', 'release_era'].map(key => [key, {
        level: levels[key] ?? 'unavailable', known_pct: 70, unknown_hours: 3,
      }])),
    },
    taste_migration: {
      distributions: {
        language: [
          { key: 'es-419', label: '西班牙语（拉丁美洲）', hours: 7, share_pct: 70 },
          { key: 'unknown', label: '尚未归类', hours: 3, share_pct: 30 },
        ],
        style: [{ key: 'r&b/soul', label: 'R&B / Soul', hours: 10, share_pct: 100 }],
        scene: [{ key: 'c-pop', label: 'C-Pop', hours: 10, share_pct: 100 }],
      },
      changes: {}, observations: [], comparison: { status: 'unavailable' },
    },
  } as unknown as YearlyReviewResponse
}

describe.each([
  ['desktop', TasteMigrationChapter],
  ['phone', MobileTasteMigrationChapter],
] as const)('Yearly V2 language distribution: %s', (_name, Chapter) => {
  it('renders backend language buckets without requiring genre coverage', () => {
    render(<Chapter report={report()} />)

    expect(screen.getByRole('tab', { name: '语言' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByText('西班牙语（拉丁美洲）')).toBeInTheDocument()
    expect(screen.getByText('70.0%')).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: '主曲风' })).not.toBeInTheDocument()
  })

  it('retains unknown listening in the distribution denominator', () => {
    render(<Chapter report={report()} />)

    expect(screen.getByText('其他')).toBeInTheDocument()
    expect(screen.getByText('30.0%')).toBeInTheDocument()
    expect(screen.queryByText('100.0%')).not.toBeInTheDocument()
    expect(screen.queryByText(/无法归属主艺人/)).not.toBeInTheDocument()
  })

  it('renders style and scene independently when language is unavailable', () => {
    render(<Chapter report={report({ style: 'core', scene: 'secondary' })} />)

    expect(screen.getByText('R&B / Soul')).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: '语言' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: '地区流行' }))
    expect(screen.getByText('C-Pop')).toBeInTheDocument()
    expect(screen.queryByText('R&B / Soul')).not.toBeInTheDocument()
  })

  it('omits unsupported taste coverage without inventing a distribution', () => {
    const { container } = render(<Chapter report={report({ language: 'insufficient' })} />)

    expect(container).toBeEmptyDOMElement()
  })

  it('keeps governance details out of the annual presentation', () => {
    render(<Chapter report={report()} />)

    expect(screen.queryByText(/审核|证据|置信|LLM|覆盖/)).not.toBeInTheDocument()
    expect(screen.queryByText(/艺人常用演唱语言/)).not.toBeInTheDocument()
    expect(screen.queryByText(/占全部可归属有效聆听时长/)).not.toBeInTheDocument()
  })
})
