import { useArchiveCohorts } from '@/features/account-archive/hooks/useAccountArchive'
import { useArchiveSection } from '@/features/account-archive/hooks/useArchiveSection'
import { formatArchiveNumber } from '@/features/account-archive/model/archiveModel'
import { PhoneArchiveError, PhoneArchiveLoading, PhoneArchiveUnavailable, PhoneChapterHeading, PhoneEntityCard } from './PhoneArchivePrimitives'

const ENCOUNTER_LABELS = {
  same_day: '同日收藏',
  days_1_7: '1–7 天',
  days_8_30: '8–30 天',
  days_31_90: '31–90 天',
  days_90_plus: '90 天以上',
}

const VITALITY_LABELS = {
  within_7d: '收藏后 7 天内又听',
  days_8_30: '收藏后第 8–30 天仍听',
  after_180d: '收藏半年后还在听',
  after_365d: '收藏一年后还在听',
}

export function PhoneRelationshipsChapter() {
  const { ref, enabled } = useArchiveSection()
  const query = useArchiveCohorts(enabled)
  return (
    <section ref={ref} id="archive-cohorts" className="phone-archive-chapter phone-archive-cohorts" data-archive-section="cohorts">
      <PhoneChapterHeading number="02" title="播放多久后收藏" />
      {!enabled || query.isLoading ? <PhoneArchiveLoading /> : null}
      {query.isError ? <PhoneArchiveError onRetry={() => void query.refetch()} /> : null}
      {query.data?.status === 'unavailable' ? <PhoneArchiveUnavailable>暂时没有可展示的收藏与播放关联数据。</PhoneArchiveUnavailable> : null}
      {query.data && query.data.status !== 'unavailable' ? (
        <>
          <div className="phone-archive-window-card">
            <p>收藏前后 30 天</p>
            <div><span>收藏前<strong>{formatArchiveNumber(query.data.symmetric_30_day_window.before_events)}</strong><small>次播放</small></span><span>收藏后<strong>{formatArchiveNumber(query.data.symmetric_30_day_window.after_events)}</strong><small>次播放</small></span></div>
          </div>
          <ol className="phone-archive-encounters">
            {query.data.encounter_to_save.bins.map(bin => (
              <li key={bin.key}>
                <span>{ENCOUNTER_LABELS[bin.key]}</span>
                <i><b style={{ width: `${Math.max(bin.share_pct, bin.entities ? 3 : 0)}%` }} /></i>
                <strong>{bin.entities}</strong>
                <small>{bin.share_pct.toFixed(1)}%</small>
              </li>
            ))}
          </ol>
          {query.data.encounter_to_save.examples.length ? (
            <div className="phone-archive-story-list phone-archive-encounter-stories">
              <p className="phone-archive-list-title">首次播放后，隔了最久才收藏</p>
              {query.data.encounter_to_save.examples.slice(0, 3).map(item => (
                <PhoneEntityCard
                  key={`${item.track_name}-${item.artist_name}`}
                  name={item.track_name}
                  artist={item.artist_name}
                  coverUrl={item.cover_url}
                  href={item.deep_link}
                  meta={`相隔 ${formatArchiveNumber(item.days_to_save ?? 0)} 天`}
                />
              ))}
            </div>
          ) : null}

          <div id="archive-relationships" className="phone-archive-subchapter" data-archive-section="relationships">
            <PhoneChapterHeading number="03" title="收藏后再次播放" />
            <div className="phone-archive-vitality-grid">
              {query.data.vitality_metrics.map(metric => (
                <div key={metric.key}>
                  <span>{VITALITY_LABELS[metric.key]}</span>
                  <strong>{metric.return_rate_pct !== null ? `${metric.return_rate_pct.toFixed(1)}%` : `${metric.returned_entities} 首`}</strong>
                  <small>{formatArchiveNumber(metric.returned_entities)} / {formatArchiveNumber(metric.eligible_entities)} 首有播放</small>
                </div>
              ))}
            </div>
            <div className="phone-archive-relation-grid">
              <div><strong>{formatArchiveNumber(query.data.relationship_matrix.counts.recent_active_saved)}</strong><span>近 90 天听过的收藏</span></div>
              <div><strong>{formatArchiveNumber(query.data.relationship_matrix.counts.sleeping_saved)}</strong><span>近 90 天没听的收藏</span></div>
              <div><strong>{formatArchiveNumber(query.data.relationship_matrix.counts.frequent_unsaved)}</strong><span>近 90 天常听但未收藏</span></div>
            </div>
          </div>
        </>
      ) : null}
    </section>
  )
}
