import { useEffect, useMemo, useState } from 'react'

import type { YearlyReviewResponse } from '@/types/yearly-review-v2'
import { MobileHonorsChapter } from './chapters/MobileHonorsChapter'
import { MobileSeasonChapter } from './chapters/MobileSeasonChapter'
import { MobileRelationshipsChapter } from './chapters/MobileRelationshipsChapter'
import { MobileListeningLifeChapter } from './chapters/MobileListeningLifeChapter'
import { MobileRecordsChapter } from './chapters/MobileRecordsChapter'
import { MobileTasteMigrationChapter } from './chapters/MobileTasteMigrationChapter'
import { MobileEpilogueChapter } from './chapters/MobileEpilogueChapter'
import { MobileAppendixChapter } from './chapters/MobileAppendixChapter'
import { MobileYearlyCover } from './MobileYearlyCover'
import { MobileYearlyChapterNavV2, type MobileYearlyChapterItem } from './MobileYearlyChapterNavV2'
import './mobileYearlyV2.css'

export function YearlyReviewPhoneExperience({ report }: { report: YearlyReviewResponse }) {
  const chapters = useMemo<MobileYearlyChapterItem[]>(() => [
    { id: 'phone-yearly-honors', label: '年度荣誉' },
    { id: 'phone-yearly-season', label: '年度时间线' },
    ...(report.relationships.length > 0
      ? [{ id: 'phone-yearly-relationships', label: '喜欢与陪伴' }]
      : []),
    ...(report.listening_life.observations.length > 0
      ? [{ id: 'phone-yearly-listening-life', label: '收听生活' }]
      : []),
    { id: 'phone-yearly-records', label: '年度纪录' },
    { id: 'phone-yearly-taste', label: '品味变化' },
    { id: 'phone-yearly-epilogue', label: '年度结语' },
    { id: 'phone-yearly-appendix', label: '完整榜单' },
  ], [report.listening_life.observations.length, report.relationships.length])
  const [activeId, setActiveId] = useState(chapters[0]?.id ?? '')

  useEffect(() => {
    const elements = chapters
      .map(chapter => document.getElementById(chapter.id))
      .filter((element): element is HTMLElement => element != null)
    if (elements.length === 0) return undefined

    let frame = 0
    const updateActiveChapter = () => {
      window.cancelAnimationFrame(frame)
      frame = window.requestAnimationFrame(() => {
        const anchor = Math.max(96, window.innerHeight * 0.24)
        const containing = elements.find((element) => {
          const rect = element.getBoundingClientRect()
          return rect.top <= anchor && rect.bottom > anchor
        })
        const next = elements.find(element => element.getBoundingClientRect().top > anchor)
        const active = containing ?? next ?? elements[elements.length - 1]
        if (active?.id) setActiveId(active.id)
      })
    }

    updateActiveChapter()
    window.addEventListener('scroll', updateActiveChapter, { passive: true })
    window.addEventListener('resize', updateActiveChapter)
    return () => {
      window.cancelAnimationFrame(frame)
      window.removeEventListener('scroll', updateActiveChapter)
      window.removeEventListener('resize', updateActiveChapter)
    }
  }, [chapters])

  const selectChapter = (id: string) => {
    setActiveId(id)
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="mobile-yearly-v2-experience" data-yearly-presentation="phone-v2">
      <MobileYearlyCover report={report} />
      <MobileYearlyChapterNavV2 chapters={chapters} activeId={activeId} onSelect={selectChapter} />
      <main className="mobile-yearly-v2-story">
        <MobileHonorsChapter report={report} />
        <MobileSeasonChapter report={report} />
        <MobileRelationshipsChapter report={report} />
        <MobileListeningLifeChapter report={report} />
        <MobileRecordsChapter report={report} />
        <MobileTasteMigrationChapter report={report} />
        <MobileEpilogueChapter report={report} />
        <MobileAppendixChapter report={report} />
      </main>
      <footer className="mobile-yearly-v2-colophon">
        <span>SPOTIFY STATS</span>
        <strong>{report.year}</strong>
        <span>END OF ISSUE</span>
      </footer>
    </div>
  )
}
