import { LockKeyhole } from 'lucide-react'

import { useArchiveDiscovery } from '@/features/account-archive/hooks/useAccountArchive'
import { useArchiveSection } from '@/features/account-archive/hooks/useArchiveSection'
import { formatArchiveMonth, formatArchiveNumber } from '@/features/account-archive/model/archiveModel'
import { PhoneArchiveError, PhoneArchiveLoading, PhoneArchiveUnavailable, PhoneChapterHeading } from './PhoneArchivePrimitives'

const WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日']

export function PhoneDiscoveryChapter() {
  const { ref, enabled } = useArchiveSection()
  const query = useArchiveDiscovery(enabled)
  const weekdayMax = Math.max(...(query.data?.weekday_distribution.map(point => point.bursts) ?? [1]))
  const hourMax = Math.max(...(query.data?.hour_distribution.map(point => point.bursts) ?? [1]))
  return (
    <section ref={ref} id="archive-discovery" className="phone-archive-chapter" data-archive-section="discovery">
      <PhoneChapterHeading number="05" eyebrow="A private search trail" title="发现路径" description="原始搜索词不离开本地；这里只留下去重后的活动轮廓。" />
      {!enabled || query.isLoading ? <PhoneArchiveLoading /> : null}
      {query.isError ? <PhoneArchiveError onRetry={() => void query.refetch()} /> : null}
      {query.data?.status === 'unavailable' ? <PhoneArchiveUnavailable>尚未导入搜索记录，本章不会根据播放历史猜测搜索行为。</PhoneArchiveUnavailable> : null}
      {query.data && query.data.status !== 'unavailable' ? (
        <>
          <div className="phone-archive-private-ledger">
            <LockKeyhole aria-hidden="true" />
            <p>搜索档案覆盖</p>
            <strong>{formatArchiveMonth(query.data.period.first_search_at)}—{formatArchiveMonth(query.data.period.latest_search_at)}</strong>
            <div>
              <span><b>{formatArchiveNumber(query.data.coverage.search_bursts)}</b>次过程</span>
              <span><b>{formatArchiveNumber(query.data.coverage.unique_normalized_queries)}</b>个去重查询</span>
              <span><b>{formatArchiveNumber(query.data.period.active_days)}</b>个活跃日</span>
            </div>
            <small>不展示任何原始查询内容</small>
          </div>
          <div className="phone-archive-weekdays" aria-label="按星期的搜索过程">
            <p>一周里的搜索</p>
            <div>
              {query.data.weekday_distribution.map(item => (
                <span key={item.weekday}><i style={{ height: `${Math.max((item.bursts / weekdayMax) * 100, 5)}%` }} /><small>{WEEKDAYS[item.weekday]}</small></span>
              ))}
            </div>
          </div>
          <div className="phone-archive-hours" aria-label="一天内的搜索过程">
            <div><p>一天里的搜索</p><small>本地时间</small></div>
            <div className="phone-archive-hour-strip">
              {query.data.hour_distribution.map(item => (
                <i
                  key={item.hour}
                  aria-label={`${item.hour} 时，${item.bursts} 次过程`}
                  style={{ opacity: Math.max(item.bursts / hourMax, item.bursts ? 0.22 : 0.06) }}
                />
              ))}
            </div>
            <div className="phone-archive-hour-labels"><span>00</span><span>06</span><span>12</span><span>18</span><span>24</span></div>
          </div>
          <ol className="phone-archive-funnel">
            {[
              ['曲目点击', query.data.funnel.track_interaction_bursts],
              ['映射本地', query.data.funnel.mapped_track_interaction_bursts],
              ['1 小时内播放', query.data.funnel.played_within_1h_bursts],
              ['30 天内收藏', query.data.funnel.currently_saved_within_30d_bursts],
            ].map(([label, value], index) => <li key={String(label)}><span>{index + 1}</span><strong>{label}</strong><small>{formatArchiveNumber(Number(value))}</small></li>)}
          </ol>
          <p className="phone-archive-footnote">这不是搜索转化率；导出只为少量搜索保留第一个点击对象。</p>
        </>
      ) : null}
    </section>
  )
}
