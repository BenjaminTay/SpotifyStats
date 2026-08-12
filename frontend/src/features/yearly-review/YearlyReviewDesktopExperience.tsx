import type { AnalysisFilters } from '@/types/analysis'
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

export function YearlyReviewDesktopExperience({ report, filters }: { report: YearlyReviewResponse; filters: AnalysisFilters }) {
  return (
    <div className="yearly-review-content yearly-v2-experience">
      <PassportChapter report={report} />
      <HonorsChapter report={report} />
      <SeasonChapter report={report} />
      <RelationshipsChapter report={report} />
      <ListeningLifeChapter report={report} />
      <RecordsChapter key={`records-${report.year}-${report.filter_context.filter_fingerprint}`} report={report} filters={filters} />
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
