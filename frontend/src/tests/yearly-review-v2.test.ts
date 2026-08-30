import { waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import desktopExperienceSource from '../features/yearly-review/YearlyReviewDesktopExperience.tsx?raw'
import recordsChapterSource from '../features/yearly-review/records/RecordsChapter.tsx?raw'
import appendixChapterSource from '../features/yearly-review/appendix/AppendixChapter.tsx?raw'
import passportChapterSource from '../features/yearly-review/passport/PassportChapter.tsx?raw'
import primitivesSource from '../features/yearly-review/YearlyReviewPrimitives.tsx?raw'
import statesSource from '../features/yearly-review/YearlyReviewStates.tsx?raw'
import pageSource from '../pages/YearlyReviewPage.tsx?raw'
import { buildYearlyReviewParams, displayYearlyText, formatMetric, formatMetricComparison, yearlyReviewFilterKey } from '../features/yearly-review/yearlyReviewData'
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
  afterEach(() => localStorage.removeItem('chineseStyle'))

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
    expect(formatMetricComparison({ key: 'plays', label: '年度播放', value: 90, unit: '次', comparison_value: 100, comparison_label: '比去年' })).toEqual({
      direction: 'down',
      text: '10.0%',
      ariaLabel: '比去年低 10.0%',
    })
    expect(formatMetricComparison({
      key: 'plays',
      label: '年度播放',
      value: 1000,
      unit: '次',
      comparison_current_value: 90,
      comparison_value: 60,
      comparison_label: '比去年同期',
    })).toEqual({
      direction: 'up',
      text: '50.0%',
      ariaLabel: '比去年同期高 50.0%',
    })
  })

  it('applies the global Chinese display preference to annual copy', async () => {
    localStorage.setItem('chineseStyle', 'simplified')
    await waitFor(() => expect(displayYearlyText('專輯《認了吧》重新出現')).toBe('专辑《认了吧》重新出现'))
  })

  it('shares V2 data across separate phone and desktop presentations without a second annual mode', () => {
    expect(pageSource).toContain('isPhone && v2Data')
    expect(pageSource).toContain('!isPhone && v2Data')
    expect(pageSource).toContain('<YearlyReviewPhoneExperience')
    expect(pageSource).toContain('<YearlyReviewDesktopExperience')
    expect(pageSource).not.toContain('OfficialWrapped')
    expect(pageSource).not.toContain('官方 Wrapped')
    expect(pageSource).not.toContain('/wrapped-hub')
    expect(pageSource).not.toContain('<CustomSummary')
    expect(pageSource).not.toContain('useYearlyReview(')
    expect(pageSource).not.toContain("'/wrapped/available-years'")
    expect(pageSource).not.toContain('activeTab')
    expect(pageSource).toContain('useYearlyReviewV2AvailableYears(true)')
    expect(pageSource).toContain('useYearlyReviewGenerationStatus(v2Years, filters, generationEnabled)')
    expect(pageSource).toContain('foreground_year: currentYear')
    expect(pageSource).toContain("currentGenerationTask?.state === 'queued'")
    expect(pageSource).toContain("currentGenerationTask.state === 'ready'")
    expect(pageSource).toContain('void refetchV2Review()')
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

  it('keeps only curated annual records while paginating appendix tables', () => {
    expect(recordsChapterSource).not.toContain('useYearlyReviewV2Records')
    expect(recordsChapterSource).not.toContain('更多年度纪录')
    expect(recordsChapterSource).not.toContain('yearly-v2-catalog-toggle')
    expect(appendixChapterSource).toContain('const PAGE_SIZE = 10')
    expect(appendixChapterSource).toContain('rows.slice((page - 1) * PAGE_SIZE')
  })

  it('keeps audit language out of the consumer-facing annual', () => {
    const consumerSource = [passportChapterSource, appendixChapterSource, statesSource].join('\n')
    for (const banned of ['统计口径', '可比基线', '有效阈值', '服务端分页', '方法与限制', '口径索引']) {
      expect(consumerSource).not.toContain(banned)
    }
    expect(primitivesSource).not.toContain('description: string')
    expect(passportChapterSource).not.toContain('yearly-v2-cover-deck')
    expect(passportChapterSource).not.toContain('yearly-v2-cover-period-note')
    expect(appendixChapterSource).toContain('title="完整榜单"')
  })

  it('renders comparisons and artwork across the passport and complete charts', () => {
    expect(passportChapterSource).toContain('formatMetricComparison(metric)')
    expect(passportChapterSource).toContain("comparison.direction === 'up' ? '↑'")
    expect(passportChapterSource).not.toContain('同期参照')
    expect(passportChapterSource).not.toContain('formatComparisonWindow')
    expect(passportChapterSource).not.toContain('report.headlines')
    expect(appendixChapterSource).toContain('<EntityMediaLink')
    expect(appendixChapterSource).not.toContain("'months'")
    expect(appendixChapterSource).not.toContain("'method'")
  })

  it('defaults V2 on every viewport to the newest available year and keeps year labels concise', () => {
    expect(pageSource).toContain(': latestYear')
    expect(pageSource).toContain('setSearchParams({ year: String(latestYear) })')
    expect(pageSource).not.toContain('latestCompleteYear')
    expect(pageSource).toContain('{y}')
    expect(pageSource).not.toContain('· 进行中')
    expect(pageSource).toContain('sort((left, right) => left - right)')
    expect(pageSource).not.toContain('ShareButton')
  })

  it('shows period status only for unfinished reports', () => {
    expect(passportChapterSource).toContain("report.status !== 'complete'")
    expect(passportChapterSource).not.toContain(`${'${report.year}'}.01.01`)
  })

})
