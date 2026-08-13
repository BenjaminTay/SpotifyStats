import { useArchiveCohorts } from '@/features/account-archive/hooks/useAccountArchive'
import { useArchiveSection } from '@/features/account-archive/hooks/useArchiveSection'
import { formatArchiveNumber } from '@/features/account-archive/model/archiveModel'
import {
  ArchiveEntityRow,
  ArchiveError,
  ArchiveLoading,
  ArchiveSectionHeading,
  ArchiveUnavailable,
} from '@/features/account-archive/components/ArchivePrimitives'

const ENCOUNTER_LABELS = {
  same_day: '同日',
  days_1_7: '1–7 天',
  days_8_30: '8–30 天',
  days_31_90: '31–90 天',
  days_90_plus: '90 天以上',
}

export function CohortsSection() {
  const { ref, enabled } = useArchiveSection()
  const query = useArchiveCohorts(enabled)

  return (
    <section
      ref={ref}
      id="archive-cohorts"
      className="archive-chapter"
      data-archive-section="cohorts"
    >
      <ArchiveSectionHeading
        number="02"
        eyebrow="From encounter to keeping"
        title="从遇见到收藏"
        description="以记录期内第一次有效播放为起点，观察一首歌经过多久进入当前收藏；没有被记录到的更早相遇不会被假装成不存在。"
      />
      {!enabled || query.isLoading ? <ArchiveLoading /> : null}
      {query.isError && <ArchiveError onRetry={() => void query.refetch()} />}
      {query.data?.status === 'unavailable' && (
        <ArchiveUnavailable>收藏与播放暂时无法稳定关联，本章不生成推测性结论。</ArchiveUnavailable>
      )}
      {query.data && query.data.status !== 'unavailable' && (
        <>
          <div className="archive-cohort-layout">
            <div className="archive-encounter-panel">
              <div className="archive-panel-heading">
                <div>
                  <p>记录期首次播放 → 收藏</p>
                  <strong>{formatArchiveNumber(query.data.encounter_to_save.eligible_entities)} 首可计算</strong>
                </div>
                <span>{formatArchiveNumber(query.data.encounter_to_save.no_observed_pre_save_play)} 首未观察到收藏前播放</span>
              </div>
              <ol className="archive-encounter-bars">
                {query.data.encounter_to_save.bins.map((bin) => (
                  <li key={bin.key}>
                    <span className="archive-encounter-label">{ENCOUNTER_LABELS[bin.key]}</span>
                    <span className="archive-encounter-track">
                      <span style={{ width: `${Math.max(bin.share_pct, bin.entities ? 2 : 0)}%` }} />
                    </span>
                    <strong>{bin.entities}</strong>
                    <small>{bin.share_pct.toFixed(1)}%</small>
                  </li>
                ))}
              </ol>
            </div>

            <aside className="archive-window-note">
              <span className="archive-red-rule" aria-hidden="true" />
              <p>收藏前后各 30 天</p>
              <strong>{formatArchiveNumber(query.data.symmetric_30_day_window.after_events)}</strong>
              <span>次收藏后有效播放</span>
              <small>
                对照收藏前 {formatArchiveNumber(query.data.symmetric_30_day_window.before_events)} 次；
                只使用左右窗口都完整的 {formatArchiveNumber(query.data.symmetric_30_day_window.eligible_entities)} 首收藏。
              </small>
            </aside>
          </div>

          {query.data.encounter_to_save.examples.length > 0 && (
            <div className="archive-story-preview">
              <p className="archive-kicker">Archive notes</p>
              {query.data.encounter_to_save.examples.slice(0, 3).map((item, index) => (
                <ArchiveEntityRow
                  key={`${item.track_name}-${item.artist_name}`}
                  index={index + 1}
                  name={item.track_name}
                  artist={item.artist_name}
                  coverUrl={item.cover_url}
                  href={item.deep_link}
                  meta={`${item.effective_plays} 次有效播放`}
                />
              ))}
            </div>
          )}

          <div
            id="archive-relationships"
            className="archive-chapter-subsection"
            data-archive-section="relationships"
          >
            <ArchiveSectionHeading
              number="03"
              eyebrow="What happened after saving"
              title="收藏之后"
              description="每个回访节点只使用已经完整经历对应天数的收藏。高比例只描述当前仍在收藏的歌曲，不代表所有历史收藏的留存。"
            />
            <div className="archive-return-milestones">
              {query.data.return_windows.map((window) => (
                <div key={window.horizon_days}>
                  <span>{window.horizon_days === 365 ? '1 年' : `${window.horizon_days} 天`}</span>
                  <strong>
                    {window.return_rate_pct !== null
                      ? `${window.return_rate_pct.toFixed(1)}%`
                      : `${formatArchiveNumber(window.returned_entities)} 首`}
                  </strong>
                  <small>{formatArchiveNumber(window.eligible_entities)} 首可观察</small>
                </div>
              ))}
            </div>

            <div className="archive-relationship-grid">
              {[
                ['近期活跃收藏', query.data.relationship_matrix.counts.recent_active_saved, '最近 90 天仍有有效播放'],
                ['沉睡收藏', query.data.relationship_matrix.counts.sleeping_saved, '收藏满 90 天，近期没有播放'],
                ['常听未收藏', query.data.relationship_matrix.counts.frequent_unsaved, '近期至少 5 次，但不在当前收藏'],
                ['暂时无法关联', query.data.relationship_matrix.counts.unmatched_saved_tracks, '保留在快照，不参与关系分母'],
              ].map(([label, value, note]) => (
                <div key={String(label)}>
                  <span>{label}</span><strong>{formatArchiveNumber(Number(value))}</strong><small>{note}</small>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </section>
  )
}
