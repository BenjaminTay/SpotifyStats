import { describe, expect, it } from 'vitest'

import phoneExperienceSource from '../features/mobile/yearly-v2/YearlyReviewPhoneExperience.tsx?raw'
import phoneCoverSource from '../features/mobile/yearly-v2/MobileYearlyCover.tsx?raw'
import phoneNavSource from '../features/mobile/yearly-v2/MobileYearlyChapterNavV2.tsx?raw'
import pageSource from '../pages/YearlyReviewPage.tsx?raw'

describe('Yearly Review V2 phone presentation contract', () => {
  it('mounts an independent phone presentation over the shared V2 report', () => {
    expect(pageSource).toContain('<YearlyReviewPhoneExperience')
    expect(pageSource).toContain('<YearlyReviewDesktopExperience report={v2Data} />')
    expect(pageSource).not.toContain('legacyReview')
    expect(phoneExperienceSource).toContain('data-yearly-presentation="phone-v2"')
  })

  it('renders the cover as a 2 by 3 KPI editorial grid', () => {
    expect(phoneCoverSource).toContain('passport.metrics.slice(0, 6)')
    expect(phoneCoverSource).toContain('formatMetricComparison(metric)')
    expect(phoneCoverSource).toContain('className="mobile-yearly-v2-kpis"')
  })

  it('uses one compact sticky chapter control and an accessible chapter sheet', () => {
    expect(phoneNavSource).toContain('<MobileBottomSheet')
    expect(phoneNavSource).toContain('aria-haspopup="dialog"')
    expect(phoneNavSource).toContain('className="mobile-yearly-v2-chapter-nav"')
  })

  it('keeps eight mobile chapters in the editorial sequence', () => {
    const chapterNames = [
      'MobileHonorsChapter',
      'MobileSeasonChapter',
      'MobileRelationshipsChapter',
      'MobileListeningLifeChapter',
      'MobileRecordsChapter',
      'MobileTasteMigrationChapter',
      'MobileEpilogueChapter',
      'MobileAppendixChapter',
    ]
    for (let index = 0; index < chapterNames.length - 1; index += 1) {
      expect(phoneExperienceSource.indexOf(`<${chapterNames[index]}`)).toBeLessThan(
        phoneExperienceSource.indexOf(`<${chapterNames[index + 1]}`),
      )
    }
  })
})
