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
      <PhoneChapterHeading number="04" eyebrow="The music comes back" title="找回音乐" description="两次有效播放至少相隔 90 天，才记作一次重逢。" />
      {!enabled || query.isLoading ? <PhoneArchiveLoading /> : null}
      {query.isError ? <PhoneArchiveError onRetry={() => void query.refetch()} /> : null}
      {query.data?.status === 'unavailable' ? <PhoneArchiveUnavailable>当前观察期不足以识别回归，继续导入播放记录后这里会自然形成。</PhoneArchiveUnavailable> : null}
      {query.data && query.data.status !== 'unavailable' ? (
        <>
          <div className="phone-archive-return-hero">
            <RotateCcw aria-hidden="true" />
            <span>发生过回归的收藏</span>
            <strong>{formatArchiveNumber(query.data.summary.returned_entities)}</strong>
            <small>{formatArchiveNumber(query.data.summary.return_episodes)} 次回归事件 · 最近 90 天有 {formatArchiveNumber(query.data.summary.recent_90_day_return_entities)} 首</small>
          </div>
          <div className="phone-archive-mini-heading"><span>Recently returned</span><strong>最近重新出现</strong></div>
          <div className="phone-archive-story-list">
            {query.data.latest_returns.slice(0, 3).map((item, index) => (
              <PhoneEntityCard key={`${item.track_name}-${item.returned_at}`} ordinal={index + 1} name={item.track_name} artist={item.artist_name} coverUrl={item.cover_url} href={item.deep_link} meta={`${item.dormant_days} 天后 · ${formatArchiveDate(item.returned_at)}`} />
            ))}
          </div>
          {query.data.sleeping_recommendations.length ? (
            <div className="phone-archive-sleeping">
              <p>Filed, not forgotten</p>
              <h3>也许值得再听一遍</h3>
              <small>{formatArchiveNumber(query.data.summary.current_sleeping_entities)} 首当前收藏最近 90 天没有出现</small>
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
