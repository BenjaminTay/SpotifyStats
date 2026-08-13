import { Search } from 'lucide-react'

import { useArchiveDiscovery } from '@/features/account-archive/hooks/useAccountArchive'
import { useArchiveSection } from '@/features/account-archive/hooks/useArchiveSection'
import { formatArchiveMonth, formatArchiveNumber } from '@/features/account-archive/model/archiveModel'
import {
  ArchiveError,
  ArchiveLoading,
  ArchiveSectionHeading,
  ArchiveUnavailable,
} from '@/features/account-archive/components/ArchivePrimitives'

const WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日']

export function DiscoverySection() {
  const { ref, enabled } = useArchiveSection()
  const query = useArchiveDiscovery(enabled)

  return (
    <section ref={ref} id="archive-discovery" className="archive-chapter" data-archive-section="discovery">
      <ArchiveSectionHeading
        number="05"
        eyebrow="A private search trail"
        title="发现路径"
        description="搜索词可能包含敏感内容，因此这里只展示去重后的活动轮廓与有限事件链，不展示任何原始查询。"
      />
      {!enabled || query.isLoading ? <ArchiveLoading /> : null}
      {query.isError && <ArchiveError onRetry={() => void query.refetch()} />}
      {query.data?.status === 'unavailable' && (
        <ArchiveUnavailable>尚未导入搜索记录。本章保持空白，不会根据播放历史猜测搜索行为。</ArchiveUnavailable>
      )}
      {query.data && query.data.status !== 'unavailable' && (
        <div className="archive-discovery-layout">
          <div className="archive-search-ledger">
            <Search aria-hidden="true" />
            <p>搜索档案覆盖</p>
            <strong>{formatArchiveMonth(query.data.period.first_search_at)}—{formatArchiveMonth(query.data.period.latest_search_at)}</strong>
            <div>
              <span><b>{formatArchiveNumber(query.data.coverage.search_bursts)}</b> 次搜索过程</span>
              <span><b>{formatArchiveNumber(query.data.coverage.unique_normalized_queries)}</b> 个去重查询</span>
              <span><b>{formatArchiveNumber(query.data.period.active_days)}</b> 个活跃日</span>
            </div>
            <small>相邻 5 分钟内的输入被合并为一次搜索过程，避免把逐字输入重复计数。</small>
          </div>

          <div className="archive-discovery-patterns">
            <div className="archive-week-pattern" aria-label="按星期的搜索过程分布">
              <p>一周里的搜索</p>
              <div>
                {query.data.weekday_distribution.map((item) => {
                  const max = Math.max(...query.data.weekday_distribution.map((point) => point.bursts), 1)
                  return (
                    <span key={item.weekday} title={`${item.bursts} 次`}>
                      <i style={{ height: `${Math.max((item.bursts / max) * 100, 5)}%` }} />
                      <small>{WEEKDAYS[item.weekday] ?? item.weekday}</small>
                    </span>
                  )
                })}
              </div>
            </div>
            <div className="archive-hour-pattern" aria-label="按小时的搜索过程分布">
              <p>一天里的搜索</p>
              <div>
                {query.data.hour_distribution.map((item) => {
                  const max = Math.max(...query.data.hour_distribution.map((point) => point.bursts), 1)
                  return <span key={item.hour} style={{ opacity: 0.12 + (item.bursts / max) * 0.88 }} title={`${item.hour}:00 · ${item.bursts} 次`} />
                })}
              </div>
              <small><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span></small>
            </div>
          </div>

          <div className="archive-funnel-panel">
            <div className="archive-panel-heading">
              <div><p>有限发现链路</p><strong>只展示可验证数量</strong></div>
              <span>{formatArchiveNumber(query.data.coverage.interaction_records)} 条记录带点击对象</span>
            </div>
            <ol className="archive-funnel">
              {[
                ['曲目点击过程', query.data.funnel.track_interaction_bursts],
                ['可映射本地曲目', query.data.funnel.mapped_track_interaction_bursts],
                ['1 小时内播放', query.data.funnel.played_within_1h_bursts],
                ['播放后 30 天内进入当前收藏', query.data.funnel.currently_saved_within_30d_bursts],
              ].map(([label, value], index) => (
                <li key={String(label)}>
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <div><strong>{label}</strong><small>{formatArchiveNumber(Number(value))} 次</small></div>
                </li>
              ))}
            </ol>
            <p className="archive-method-note">这不是搜索转化率；导出只为少量搜索保留第一个点击对象，且当前收藏快照看不到已经取消收藏的歌曲。</p>
          </div>
        </div>
      )}
    </section>
  )
}
