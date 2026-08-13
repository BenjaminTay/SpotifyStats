import { useArchiveJourney } from '@/features/account-archive/hooks/useAccountArchive'
import {
  formatArchiveDate,
  formatArchiveHours,
  formatArchiveNumber,
} from '@/features/account-archive/model/archiveModel'
import {
  ArchiveEntityRow,
  ArchiveError,
  ArchiveLoading,
  ArchiveMetric,
  ArchiveSectionHeading,
  ArchiveUnavailable,
} from '@/features/account-archive/components/ArchivePrimitives'

export function JourneySection() {
  const query = useArchiveJourney()

  return (
    <section id="archive-journey" className="archive-chapter" data-archive-section="journey">
      <ArchiveSectionHeading
        number="01"
        title="收藏旅程"
      />
      {query.isLoading && <ArchiveLoading />}
      {query.isError && <ArchiveError onRetry={() => void query.refetch()} />}
      {query.data?.status === 'unavailable' && (
        <ArchiveUnavailable>当前导入没有可用的收藏日期，收藏库仍可浏览，但时间旅程暂不可用。</ArchiveUnavailable>
      )}
      {query.data && query.data.status !== 'unavailable' && (
        <div className="archive-journey-layout">
          <div className="archive-growth-panel">
            <div className="archive-growth-caption">
              <span>每年收藏的歌曲</span>
            </div>
            <ol className="archive-growth-chart" aria-label="年度收藏增长">
              {query.data.annual_growth.map((point) => {
                const max = Math.max(...query.data.annual_growth.map((item) => item.saved_tracks), 1)
                return (
                  <li key={point.period}>
                    <div className="archive-growth-value">
                      <strong>{formatArchiveNumber(point.saved_tracks)}</strong>
                    </div>
                    <div className="archive-growth-track">
                      <span style={{ width: `${Math.max((point.saved_tracks / max) * 100, 2)}%` }} />
                    </div>
                    <time>{point.year}</time>
                  </li>
                )
              })}
            </ol>
          </div>

          <aside className="archive-journey-aside">
            <div className="archive-metric-grid archive-metric-grid-two">
              <ArchiveMetric
                value={formatArchiveHours(query.data.duration.known_duration_ms)}
                label="收藏歌曲总时长"
                tone="red"
              />
              <ArchiveMetric
                value={
                  query.data.duration.release_year_start && query.data.duration.release_year_end
                    ? `${query.data.duration.release_year_start}—${query.data.duration.release_year_end}`
                    : '待补齐'
                }
                label="发行年代跨度"
              />
            </div>
            <div className="archive-story-stack">
              <p className="archive-milestone-title">收藏里程碑</p>
              {query.data.milestones.map((item) => (
                <ArchiveEntityRow
                  key={`${item.ordinal}-${item.track_name}`}
                  index={item.ordinal}
                  name={item.track_name}
                  artist={item.artist_name}
                  coverUrl={item.cover_url}
                  href={item.deep_link}
                  meta={formatArchiveDate(item.added_date)}
                />
              ))}
            </div>
          </aside>
        </div>
      )}
    </section>
  )
}
