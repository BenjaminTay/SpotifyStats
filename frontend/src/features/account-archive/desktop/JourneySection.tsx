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
        eyebrow="The collection grows"
        title="收藏旅程"
        description="这不是已经离开收藏库的完整历史，而是今天仍留在库中的音乐，沿着收藏日期留下的年轮。"
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
              <span>每年新增</span>
              <span>当前仍在收藏</span>
            </div>
            <ol className="archive-growth-chart" aria-label="年度收藏增长">
              {query.data.annual_growth.map((point) => {
                const max = Math.max(...query.data.annual_growth.map((item) => item.saved_tracks), 1)
                return (
                  <li key={point.period}>
                    <div className="archive-growth-value">
                      <strong>{formatArchiveNumber(point.saved_tracks)}</strong>
                      <small>累计 {formatArchiveNumber(point.cumulative_saved_tracks)}</small>
                    </div>
                    <div className="archive-growth-track">
                      <span style={{ width: `${Math.max((point.saved_tracks / max) * 100, 2)}%` }} />
                    </div>
                    <time>{point.year}</time>
                  </li>
                )
              })}
            </ol>
            <p className="archive-method-note">
              年度新增只统计具有有效收藏日期、且目前仍在收藏快照中的歌曲。
            </p>
          </div>

          <aside className="archive-journey-aside">
            <div className="archive-metric-grid archive-metric-grid-two">
              <ArchiveMetric
                value={formatArchiveHours(query.data.duration.known_duration_ms)}
                label="准确收藏总时长"
                note={`${query.data.coverage.duration_coverage_pct.toFixed(1)}% 曲长覆盖`}
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
              {query.data.milestones.map((item, index) => (
                <ArchiveEntityRow
                  key={`${item.role}-${item.track_name}`}
                  index={index + 1}
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
