import { RotateCcw } from 'lucide-react'

import { useArchiveReturns } from '@/features/account-archive/hooks/useAccountArchive'
import { useArchiveSection } from '@/features/account-archive/hooks/useArchiveSection'
import { formatArchiveDate, formatArchiveNumber } from '@/features/account-archive/model/archiveModel'
import { PhoneArchiveError, PhoneArchiveLoading, PhoneArchiveUnavailable, PhoneChapterHeading, PhoneEntityCard } from './PhoneArchivePrimitives'

export function PhoneReturnsChapter() {
  const { ref, enabled } = useArchiveSection()
  const query = useArchiveReturns(enabled)
  return (
    <section ref={ref} id="archive-returns" className="phone-archive-chapter" data-archive-section="returns">
      <PhoneChapterHeading number="04" title="找回音乐" />
      {!enabled || query.isLoading ? <PhoneArchiveLoading /> : null}
      {query.isError ? <PhoneArchiveError onRetry={() => void query.refetch()} /> : null}
      {query.data?.status === 'unavailable' ? <PhoneArchiveUnavailable>当前观察期不足以识别回归，继续导入播放记录后这里会自然形成。</PhoneArchiveUnavailable> : null}
      {query.data && query.data.status !== 'unavailable' ? (
        <>
          <div className="phone-archive-return-hero">
            <RotateCcw aria-hidden="true" />
            <span>久别后又听到的收藏</span>
            <strong>{formatArchiveNumber(query.data.summary.returned_entities)}</strong>
            <div className="phone-archive-return-facts">
              <span><strong>{formatArchiveNumber(query.data.summary.return_episodes)}</strong>次久别重听</span>
              <span><strong>{formatArchiveNumber(query.data.summary.recent_90_day_return_entities)}</strong>首最近 90 天重新听到</span>
            </div>
          </div>
          <div className="phone-archive-mini-heading"><strong>最近重新出现</strong></div>
          <div className="phone-archive-story-list">
            {query.data.latest_returns.slice(0, 3).map((item, index) => (
              <PhoneEntityCard key={`${item.track_name}-${item.returned_at}`} ordinal={index + 1} name={item.track_name} artist={item.artist_name} coverUrl={item.cover_url} href={item.deep_link} meta={`${item.dormant_days} 天后 · ${formatArchiveDate(item.returned_at)}`} />
            ))}
          </div>
          {query.data.sleeping_recommendations.length ? (
            <div className="phone-archive-sleeping">
              <h3>也许值得再听一遍</h3>
              <small>{formatArchiveNumber(query.data.summary.current_sleeping_entities)} 首收藏近 90 天没听</small>
              <div>
                {query.data.sleeping_recommendations.slice(0, 2).map(item => (
                  <PhoneEntityCard key={`${item.track_name}-${item.artist_name}`} name={item.track_name} artist={item.artist_name} coverUrl={item.cover_url} href={item.deep_link} meta={`${item.dormant_days} 天未出现`} />
                ))}
              </div>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  )
}
