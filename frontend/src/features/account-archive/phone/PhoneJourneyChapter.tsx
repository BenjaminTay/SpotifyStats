import { useArchiveJourney } from '@/features/account-archive/hooks/useAccountArchive'
import { useArchiveSection } from '@/features/account-archive/hooks/useArchiveSection'
import {
  formatArchiveDate,
  formatArchiveHours,
  formatArchiveNumber,
} from '@/features/account-archive/model/archiveModel'
import { PhoneArchiveError, PhoneArchiveLoading, PhoneChapterHeading, PhoneEntityCard } from './PhoneArchivePrimitives'

export function PhoneJourneyChapter() {
  const { ref, enabled } = useArchiveSection()
  const query = useArchiveJourney(enabled)
  const max = Math.max(...(query.data?.annual_growth.map(point => point.saved_tracks) ?? [1]))
  return (
    <section ref={ref} id="archive-journey" className="phone-archive-chapter" data-archive-section="journey">
      <PhoneChapterHeading number="01" title="收藏旅程" />
      {!enabled || query.isLoading ? <PhoneArchiveLoading /> : null}
      {query.isError ? <PhoneArchiveError onRetry={() => void query.refetch()} /> : null}
      {query.data ? (
        <>
          <div className="phone-archive-dual-facts">
            <div><span>收藏歌曲总时长</span><strong>{formatArchiveHours(query.data.duration.known_duration_ms)}</strong></div>
            <div><span>发行年代</span><strong>{query.data.duration.release_year_start}—{query.data.duration.release_year_end}</strong></div>
          </div>
          <ol className="phone-archive-growth" aria-label="年度收藏增长">
            {query.data.annual_growth.map(point => (
              <li key={point.period}>
                <time>{point.year}</time>
                <span><i style={{ width: `${Math.max((point.saved_tracks / max) * 100, 3)}%` }} /></span>
                <strong>{formatArchiveNumber(point.saved_tracks)} 首</strong>
              </li>
            ))}
          </ol>
          <div className="phone-archive-story-list">
            <p className="phone-archive-list-title">收藏里程碑</p>
            {query.data.milestones.map((item) => (
              <PhoneEntityCard key={`${item.ordinal}-${item.track_name}`} name={item.track_name} artist={item.artist_name} coverUrl={item.cover_url} href={item.deep_link} meta={`第 ${item.ordinal} 首 · ${formatArchiveDate(item.added_date)}`} />
            ))}
          </div>
        </>
      ) : null}
    </section>
  )
}
