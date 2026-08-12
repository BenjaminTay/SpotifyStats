import { describe, expect, it } from 'vitest'

import desktopExperienceSource from '../features/yearly-review/YearlyReviewDesktopExperience.tsx?raw'
import recordsChapterSource from '../features/yearly-review/records/RecordsChapter.tsx?raw'
import appendixChapterSource from '../features/yearly-review/appendix/AppendixChapter.tsx?raw'
import pageSource from '../pages/YearlyReviewPage.tsx?raw'
import { buildYearlyReviewParams, formatMetric, yearlyReviewFilterKey } from '../features/yearly-review/yearlyReviewData'
import type { AnalysisFilters } from '../types/analysis'

const filters: AnalysisFilters = {
  min_ms: 30_000,
  music_only: true,
  merge_enabled: true,
  dynamic_threshold: true,
  max_merge_gap_minutes: 30,
  merge_level: 2,
  include_compilations: false,
  bb_top_n: 30,
  bb_album_top_n: 20,
  bb_artist_top_n: 20,
  bb_week_start_dow: 4,
  bb_week_start_hour: 0,
}

describe('Yearly Review V2 desktop contract', () => {
  it('serializes the complete statistical context into a stable query fingerprint', () => {
    const params = buildYearlyReviewParams(filters)
    expect(params).toMatchObject({
      min_ms: 30_000,
      dynamic_threshold: true,
      max_merge_gap_minutes: 30,
      merge_level: 2,
      bb_top_n: 30,
      bb_album_top_n: 20,
      bb_artist_top_n: 20,
      bb_week_start_dow: 4,
      bb_week_start_hour: 0,
    })
    expect(yearlyReviewFilterKey(params)).toBe(yearlyReviewFilterKey(Object.fromEntries(Object.entries(params).reverse())))
  })

  it('formats deterministic metrics without editorial inference', () => {
    expect(formatMetric({ key: 'plays', label: '播放', value: 1234, unit: '次', comparison_value: null, comparison_label: null })).toBe('1,234次')
    expect(formatMetric({ key: 'status', label: '状态', value: '完整年度', unit: null, comparison_value: null, comparison_label: null })).toBe('完整年度')
  })

  it('mounts V2 only outside phone while keeping official Wrapped isolated', () => {
    expect(pageSource).toContain("isPhone && activeTab === 'custom'")
    expect(pageSource).toContain("!isPhone && activeTab === 'custom'")
    expect(pageSource).toContain('<YearlyReviewDesktopExperience')
    expect(pageSource).toContain('<OfficialWrapped />')
    expect(pageSource).toContain('<CustomSummary data={data} />')
  })

  it('keeps the eight chapters in one editorial order', () => {
    const chapterNames = [
      'PassportChapter',
      'HonorsChapter',
      'SeasonChapter',
      'RelationshipsChapter',
      'ListeningLifeChapter',
      'RecordsChapter',
      'TasteMigrationChapter',
      'EpilogueChapter',
      'AppendixChapter',
    ]
    for (let index = 0; index < chapterNames.length - 1; index += 1) {
      expect(desktopExperienceSource.indexOf(`<${chapterNames[index]}`)).toBeLessThan(
        desktopExperienceSource.indexOf(`<${chapterNames[index + 1]}`),
      )
    }
  })

  it('paginates both the complete record catalog and appendix tables', () => {
    expect(recordsChapterSource).toContain('useYearlyReviewV2Records')
    expect(recordsChapterSource).toContain('page, 20')
    expect(appendixChapterSource).toContain('const PAGE_SIZE = 10')
    expect(appendixChapterSource).toContain('rows.slice((page - 1) * PAGE_SIZE')
  })
})
