import type { YearlyReviewResponse } from '@/types/yearly-review-v2'

import { AppendixChapter } from './appendix/AppendixChapter'
import { EpilogueChapter } from './epilogue/EpilogueChapter'
import { HonorsChapter } from './honors/HonorsChapter'
import { ListeningLifeChapter } from './listening-life/ListeningLifeChapter'
import { PassportChapter } from './passport/PassportChapter'
import { RecordsChapter } from './records/RecordsChapter'
import { RelationshipsChapter } from './relationships/RelationshipsChapter'
import { SeasonChapter } from './season/SeasonChapter'
import { TasteMigrationChapter } from './taste-migration/TasteMigrationChapter'
import './yearlyReviewV2.css'

export function YearlyReviewDesktopExperience({ report }: { report: YearlyReviewResponse }) {
  const chapters = [
    ['yearly-v2-honors', '年度荣誉'],
    ['yearly-v2-season', '年度时间线'],
    ...(report.relationships.length > 0 ? [['yearly-v2-relationships', '喜欢与陪伴']] : []),
    ...(report.listening_life.observations.length > 0 ? [['yearly-v2-listening-life', '收听生活']] : []),
    ['yearly-v2-records', '年度纪录'],
    ['yearly-v2-taste', '品味变化'],
    ['yearly-v2-epilogue', '年度结语'],
    ['yearly-v2-appendix', '完整榜单'],
  ]
  return (
    <div className="yearly-review-content yearly-v2-experience">
      <PassportChapter report={report} />
      <nav className="yearly-v2-chapter-nav" aria-label="年度总结章节">
        {chapters.map(([id, label]) => <a key={id} href={`#${id}`}>{label}</a>)}
      </nav>
      <HonorsChapter report={report} />
      <SeasonChapter report={report} />
      <RelationshipsChapter report={report} />
      <ListeningLifeChapter report={report} />
      <RecordsChapter report={report} />
      <TasteMigrationChapter report={report} />
      <EpilogueChapter report={report} />
      <AppendixChapter key={`appendix-${report.year}-${report.filter_context.filter_fingerprint}`} report={report} />
      <footer className="yearly-v2-colophon">
        <span>SPOTIFY STATS · PERSONAL LISTENING ANNUAL</span>
        <strong>{report.year}</strong>
        <span>END OF ISSUE</span>
      </footer>
    </div>
  )
}
