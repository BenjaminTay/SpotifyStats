import { ChevronDown } from 'lucide-react'

import { EntityMediaLink, SectionHeading } from '@/features/yearly-review/YearlyReviewPrimitives'
import type { YearlyReviewResponse } from '@/types/yearly-review-v2'

const EVENT_LABELS: Record<string, string> = {
  listening_peak: '收听高峰',
  leader_change: '榜首更替',
  discovery_peak: '发现时刻',
  return: '旧爱回归',
  obsession_peak: '沉迷时刻',
  sustained_record: '持续纪录',
  listening_pattern: '收听模式',
  record_moment: '年度纪录',
  monthly_shift: '节奏变化',
}

export function SeasonChapter({ report }: { report: YearlyReviewResponse }) {
  const { turning_points, months, stages } = report.season
  return (
    <section className="yearly-v2-section" id="yearly-v2-season">
      <SectionHeading number="02" eyebrow="THE SEASON" title="这一年如何转弯" />
      {stages.length > 0 && <div className="yearly-v2-stage-strip">{stages.map((stage) => stage.entity_refs[0] ? <EntityMediaLink key={stage.stage_id} entity={stage.entity_refs[0]} meta={`${stage.start_month}–${stage.end_month} 月 · ${stage.label}`} /> : null)}</div>}
      <div className="yearly-v2-timeline">
        {turning_points.map((point, index) => (
          <article key={point.point_id} className="yearly-v2-turning-point">
            <div className="yearly-v2-turning-month"><span>{String(point.month).padStart(2, '0')}</span><small>MONTH</small></div>
            <div className="yearly-v2-turning-line"><i /><b>{String(index + 1).padStart(2, '0')}</b></div>
            <div className="yearly-v2-turning-copy">
              <p>{EVENT_LABELS[point.event_type] ?? '年度节点'}{point.date ? ` · ${point.date}` : ''}</p>
              <h3>{point.title}</h3><span>{point.statement}</span>
              {point.entity_refs.length > 0 && <div className="yearly-v2-turning-entities">{point.entity_refs.slice(0, 3).map((entity) => <EntityMediaLink key={`${entity.entity_type}-${entity.entity_id}-${entity.name}`} entity={entity} />)}</div>}
            </div>
          </article>
        ))}
      </div>
      <details className="yearly-v2-month-ledger">
        <summary><span>查看每个月</span><small>{months.filter((month) => month.plays > 0).length} 个月留下了听歌记录</small><ChevronDown aria-hidden="true" /></summary>
        <div className="yearly-v2-month-grid">
          {months.map((month) => (
            <article key={month.month} className={month.plays === 0 ? 'is-empty' : undefined}>
              <header><strong>{String(month.month).padStart(2, '0')}</strong><span>月</span></header>
              <p>{month.plays.toLocaleString()} 次 · {month.hours.toLocaleString(undefined, { maximumFractionDigits: 1 })} 小时</p>
              <small>{month.active_days} 个活跃日</small>
              {month.leaders.play_track && <EntityMediaLink entity={month.leaders.play_track} className="yearly-v2-month-leader" />}
            </article>
          ))}
        </div>
      </details>
    </section>
  )
}
