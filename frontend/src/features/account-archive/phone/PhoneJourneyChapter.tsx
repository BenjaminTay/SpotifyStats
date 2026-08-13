import { useArchiveJourney } from '@/features/account-archive/hooks/useAccountArchive'
import { useArchiveSection } from '@/features/account-archive/hooks/useArchiveSection'
import {
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
      <PhoneChapterHeading number="01" eyebrow="The collection grows" title="收藏旅程" description="今天仍留在收藏库中的音乐，沿收藏日期形成的年轮。" />
      {!enabled || query.isLoading ? <PhoneArchiveLoading /> : null}
      {query.isError ? <PhoneArchiveError onRetry={() => void query.refetch()} /> : null}
      {query.data ? (
        <>
          <div className="phone-archive-dual-facts">
            <div><span>准确总时长</span><strong>{formatArchiveHours(query.data.duration.known_duration_ms)}</strong><small>{query.data.coverage.duration_coverage_pct.toFixed(1)}% 曲长覆盖</small></div>
            <div><span>发行年代</span><strong>{query.data.duration.release_year_start}—{query.data.duration.release_year_end}</strong><small>当前收藏跨度</small></div>
          </div>
          <ol className="phone-archive-growth" aria-label="年度收藏增长">
            {query.data.annual_growth.map(point => (
              <li key={point.period}>
                <time>{point.year}</time>
                <span><i style={{ width: `${Math.max((point.saved_tracks / max) * 100, 3)}%` }} /></span>
                <strong>+{formatArchiveNumber(point.saved_tracks)}</strong>
                <small>累计 {formatArchiveNumber(point.cumulative_saved_tracks)}</small>
              </li>
            ))}
          </ol>
          <div className="phone-archive-story-list">
            {query.data.milestones.slice(0, 2).map((item, index) => (
              <PhoneEntityCard key={`${item.role}-${item.track_name}`} ordinal={index + 1} name={item.track_name} artist={item.artist_name} coverUrl={item.cover_url} href={item.deep_link} meta={item.role === 'first_saved' ? '档案起点' : '最近入档'} />
            ))}
          </div>
        </>
      ) : null}
    </section>
  )
}
