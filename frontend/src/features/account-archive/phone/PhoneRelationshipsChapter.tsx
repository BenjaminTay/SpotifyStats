import { useRef, useState } from 'react'
import { Maximize2 } from 'lucide-react'

import { MobileFullscreenChart } from '@/components/mobile'
import { useArchiveCohorts } from '@/features/account-archive/hooks/useAccountArchive'
import { useArchiveSection } from '@/features/account-archive/hooks/useArchiveSection'
import { formatArchiveNumber } from '@/features/account-archive/model/archiveModel'
import { PhoneArchiveError, PhoneArchiveLoading, PhoneArchiveUnavailable, PhoneChapterHeading } from './PhoneArchivePrimitives'

const ENCOUNTER_LABELS = {
  same_day: '同日收藏',
  days_1_7: '1–7 天',
  days_8_30: '8–30 天',
  days_31_90: '31–90 天',
  days_90_plus: '90 天以上',
}

function AlignedWeeksChart({ points }: { points: Array<{ week_index: number; events_per_eligible: number }> }) {
  const width = 320
  const height = 170
  const padding = 22
  const max = Math.max(...points.map(point => point.events_per_eligible), 1)
  const line = points.map((point, index) => {
    const x = padding + (index / Math.max(points.length - 1, 1)) * (width - padding * 2)
    const y = height - padding - (point.events_per_eligible / max) * (height - padding * 2)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
  return (
    <div className="phone-archive-aligned-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="收藏前后逐周有效播放曲线">
        {[0, 1, 2, 3].map(index => <line key={index} x1={padding} x2={width - padding} y1={padding + index * ((height - padding * 2) / 3)} y2={padding + index * ((height - padding * 2) / 3)} />)}
        <polyline points={line} />
      </svg>
      <div><span>收藏后第 {points[0]?.week_index ?? 0} 周</span><span>每首可观察收藏的有效播放</span><span>第 {points.at(-1)?.week_index ?? 0} 周</span></div>
    </div>
  )
}

export function PhoneRelationshipsChapter() {
  const { ref, enabled } = useArchiveSection()
  const query = useArchiveCohorts(enabled)
  const [chartOpen, setChartOpen] = useState(false)
  const chartTriggerRef = useRef<HTMLButtonElement>(null)
  return (
    <section ref={ref} id="archive-cohorts" className="phone-archive-chapter phone-archive-cohorts" data-archive-section="cohorts">
      <PhoneChapterHeading number="02" eyebrow="From encounter to keeping" title="从遇见到收藏" description="从记录期内第一次有效播放出发，观察音乐经过多久进入当前收藏。" />
      {!enabled || query.isLoading ? <PhoneArchiveLoading /> : null}
      {query.isError ? <PhoneArchiveError onRetry={() => void query.refetch()} /> : null}
      {query.data?.status === 'unavailable' ? <PhoneArchiveUnavailable>收藏与播放暂时无法稳定关联，本章不生成推测性结论。</PhoneArchiveUnavailable> : null}
      {query.data && query.data.status !== 'unavailable' ? (
        <>
          <div className="phone-archive-window-card">
            <p>收藏前后各 30 天</p>
            <strong>{formatArchiveNumber(query.data.symmetric_30_day_window.after_events)}</strong>
            <span>次收藏后有效播放</span>
            <small>收藏前 {formatArchiveNumber(query.data.symmetric_30_day_window.before_events)} 次 · {formatArchiveNumber(query.data.symmetric_30_day_window.eligible_entities)} 首拥有完整双侧窗口</small>
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

          <div id="archive-relationships" className="phone-archive-subchapter" data-archive-section="relationships">
            <PhoneChapterHeading number="03" eyebrow="What happened after saving" title="收藏之后" description="每个节点只使用已经完整经历对应天数的收藏。" />
            <div className="phone-archive-return-strip">
              {query.data.return_windows.map(window => (
                <div key={window.horizon_days}>
                  <span>{window.horizon_days === 365 ? '1 年' : `${window.horizon_days} 天`}</span>
                  <strong>{window.return_rate_pct !== null ? `${window.return_rate_pct.toFixed(1)}%` : `${window.returned_entities} 首`}</strong>
                  <small>{window.eligible_entities} 首可观察</small>
                </div>
              ))}
            </div>
            {query.data.aligned_weeks.length > 1 ? (
              <button ref={chartTriggerRef} type="button" className="phone-archive-chart-open" onClick={() => setChartOpen(true)}><Maximize2 />查看完整回访曲线</button>
            ) : null}
            <div className="phone-archive-relation-grid">
              <div><strong>{formatArchiveNumber(query.data.relationship_matrix.counts.recent_active_saved)}</strong><span>近期活跃收藏</span></div>
              <div><strong>{formatArchiveNumber(query.data.relationship_matrix.counts.sleeping_saved)}</strong><span>沉睡收藏</span></div>
              <div><strong>{formatArchiveNumber(query.data.relationship_matrix.counts.frequent_unsaved)}</strong><span>常听未收藏</span></div>
              <div><strong>{formatArchiveNumber(query.data.relationship_matrix.counts.unmatched_saved_tracks)}</strong><span>暂无法关联</span></div>
            </div>
            <MobileFullscreenChart open={chartOpen} onOpenChange={setChartOpen} title="收藏前后的逐周回访" description="以收藏时点对齐，只纳入已完整经历对应周数的当前收藏" triggerRef={chartTriggerRef}>
              <div className="phone-archive-fullscreen-chart"><p>Aligned listening weeks</p><AlignedWeeksChart points={query.data.aligned_weeks} /><small>曲线下降也可能来自越往后的可观察收藏变少，不用于判断你是否“厌倦”某首歌。</small></div>
            </MobileFullscreenChart>
          </div>
        </>
      ) : null}
    </section>
  )
}
