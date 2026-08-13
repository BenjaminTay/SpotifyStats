import { Search } from 'lucide-react'

import { useArchiveDiscovery } from '@/features/account-archive/hooks/useAccountArchive'
import { useArchiveSection } from '@/features/account-archive/hooks/useArchiveSection'
import { formatArchiveNumber } from '@/features/account-archive/model/archiveModel'
import { PhoneArchiveError, PhoneArchiveLoading, PhoneArchiveUnavailable, PhoneChapterHeading } from './PhoneArchivePrimitives'

const WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日']

export function PhoneDiscoveryChapter() {
  const { ref, enabled } = useArchiveSection()
  const query = useArchiveDiscovery(enabled)
  const weekdayMax = Math.max(...(query.data?.weekday_distribution.map(point => point.bursts) ?? [1]))
  const hourMax = Math.max(...(query.data?.hour_distribution.map(point => point.bursts) ?? [1]))
  return (
    <section ref={ref} id="archive-discovery" className="phone-archive-chapter" data-archive-section="discovery">
      <PhoneChapterHeading number="05" title="搜索与发现" />
      {!enabled || query.isLoading ? <PhoneArchiveLoading /> : null}
      {query.isError ? <PhoneArchiveError onRetry={() => void query.refetch()} /> : null}
      {query.data?.status === 'unavailable' ? <PhoneArchiveUnavailable>尚未导入搜索记录。</PhoneArchiveUnavailable> : null}
      {query.data && query.data.status !== 'unavailable' ? (
        <>
          <div className="phone-archive-private-ledger">
            <Search aria-hidden="true" />
            <p>搜索记录</p>
            <strong>{formatArchiveNumber(query.data.coverage.search_bursts)} 次搜索</strong>
            <div>
              <span><b>{formatArchiveNumber(query.data.period.active_days)}</b>个搜索日</span>
              <span><b>{formatArchiveNumber(query.data.coverage.interaction_bursts)}</b>次搜索后有点击</span>
            </div>
          </div>
          <div className="phone-archive-weekdays" aria-label="按星期的搜索次数">
            <p>一周里的搜索</p>
            <div>
              {query.data.weekday_distribution.map(item => (
                <span key={item.weekday}><i style={{ height: `${Math.max((item.bursts / weekdayMax) * 100, 5)}%` }} /><small>{WEEKDAYS[item.weekday]}</small></span>
              ))}
            </div>
          </div>
          <div className="phone-archive-hours" aria-label="一天内的搜索次数">
            <div><p>一天里的搜索</p><small>本地时间</small></div>
            <div className="phone-archive-hour-strip">
              {query.data.hour_distribution.map(item => (
                <i
                  key={item.hour}
                  aria-label={`${item.hour} 时，${item.bursts} 次搜索`}
                  style={{ opacity: Math.max(item.bursts / hourMax, item.bursts ? 0.22 : 0.06) }}
                />
              ))}
            </div>
            <div className="phone-archive-hour-labels"><span>00</span><span>06</span><span>12</span><span>18</span><span>24</span></div>
          </div>
          <p className="phone-archive-block-title">搜索后的动作</p>
          <ol className="phone-archive-funnel">
            {[
              ['搜索后点开歌曲', query.data.funnel.track_interaction_bursts],
              ['其中 1 小时内播放', query.data.funnel.played_within_1h_bursts],
              ['其中 30 天内收藏', query.data.funnel.currently_saved_within_30d_bursts],
            ].map(([label, value], index) => <li key={String(label)}><span>{index + 1}</span><strong>{label}</strong><small>{formatArchiveNumber(Number(value))}</small></li>)}
          </ol>
        </>
      ) : null}
    </section>
  )
}
