import { RotateCcw } from 'lucide-react'

import { useArchiveReturns } from '@/features/account-archive/hooks/useAccountArchive'
import { useArchiveSection } from '@/features/account-archive/hooks/useArchiveSection'
import { formatArchiveDate, formatArchiveNumber } from '@/features/account-archive/model/archiveModel'
import {
  ArchiveEntityRow,
  ArchiveError,
  ArchiveLoading,
  ArchiveMetric,
  ArchiveSectionHeading,
  ArchiveUnavailable,
} from '@/features/account-archive/components/ArchivePrimitives'

export function ReturnsSection() {
  const { ref, enabled } = useArchiveSection()
  const query = useArchiveReturns(enabled)

  return (
    <section ref={ref} id="archive-returns" className="archive-chapter" data-archive-section="returns">
      <ArchiveSectionHeading
        number="04"
        eyebrow="The music comes back"
        title="找回音乐"
        description="相邻两次有效播放至少相隔 90 天，才被记录为一次回归。它说明音乐重新出现过，不替你推断为什么。"
      />
      {!enabled || query.isLoading ? <ArchiveLoading /> : null}
      {query.isError && <ArchiveError onRetry={() => void query.refetch()} />}
      {query.data?.status === 'unavailable' && (
        <ArchiveUnavailable>当前观察期不足以识别回归，继续导入播放记录后这里会自然形成。</ArchiveUnavailable>
      )}
      {query.data && query.data.status !== 'unavailable' && (
        <>
          <div className="archive-returns-summary">
            <div className="archive-returns-mark" aria-hidden="true"><RotateCcw /></div>
            <ArchiveMetric value={formatArchiveNumber(query.data.summary.returned_entities)} label="首收藏发生过回归" tone="red" />
            <ArchiveMetric value={formatArchiveNumber(query.data.summary.return_episodes)} label="次回归事件" />
            <ArchiveMetric value={formatArchiveNumber(query.data.summary.recent_90_day_return_entities)} label="最近 90 天回归" />
            <ArchiveMetric value={formatArchiveNumber(query.data.summary.current_sleeping_entities)} label="首当前沉睡收藏" tone="quiet" />
          </div>

          <div className="archive-returns-columns">
            <div>
              <div className="archive-column-heading"><span>Recently returned</span><h3>最近重新出现</h3></div>
              <div className="archive-story-stack">
                {query.data.latest_returns.map((item, index) => (
                  <ArchiveEntityRow
                    key={`${item.track_name}-${item.returned_at}`}
                    index={index + 1}
                    name={item.track_name}
                    artist={item.artist_name}
                    coverUrl={item.cover_url}
                    href={item.deep_link}
                    meta={`${item.dormant_days} 天后 · ${formatArchiveDate(item.returned_at)}`}
                  />
                ))}
              </div>
            </div>
            <div>
              <div className="archive-column-heading"><span>Longest interval</span><h3>跨越最久的重逢</h3></div>
              <div className="archive-story-stack">
                {query.data.longest_returns.map((item, index) => (
                  <ArchiveEntityRow
                    key={`${item.track_name}-${item.dormant_days}`}
                    index={index + 1}
                    name={item.track_name}
                    artist={item.artist_name}
                    coverUrl={item.cover_url}
                    href={item.deep_link}
                    meta={`${formatArchiveNumber(item.dormant_days)} 天间隔`}
                  />
                ))}
              </div>
            </div>
          </div>

          {query.data.sleeping_recommendations.length > 0 && (
            <div className="archive-sleeping-strip">
              <div>
                <p className="archive-kicker">Filed, not forgotten</p>
                <h3>也许值得再听一遍</h3>
                <p>这些音乐仍在当前收藏，只是最近 90 天没有出现。</p>
              </div>
              <div className="archive-sleeping-list">
                {query.data.sleeping_recommendations.slice(0, 3).map((item) => (
                  <ArchiveEntityRow
                    key={`${item.track_name}-${item.artist_name}`}
                    name={item.track_name}
                    artist={item.artist_name}
                    coverUrl={item.cover_url}
                    href={item.deep_link}
                    meta={`${item.dormant_days} 天未出现`}
                  />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  )
}
