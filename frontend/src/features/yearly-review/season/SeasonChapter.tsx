import { ChevronDown } from 'lucide-react'

import { EntityLink, SectionHeading } from '@/features/yearly-review/YearlyReviewPrimitives'
import type { YearlyReviewResponse } from '@/types/yearly-review-v2'

export function SeasonChapter({ report }: { report: YearlyReviewResponse }) {
  const { turning_points, months, stages } = report.season
  return (
    <section className="yearly-v2-section" id="yearly-v2-season">
      <SectionHeading number="02" eyebrow="THE SEASON" title="这一年如何转弯" description="只保留真正改变年度走向的月份；十二个月明细作为同一事实表展开。" />
      {stages.length > 0 && <div className="yearly-v2-stage-strip">{stages.map((stage) => <span key={stage.stage_id}>{stage.start_month}–{stage.end_month} 月 · {stage.label}</span>)}</div>}
      <div className="yearly-v2-timeline">
        {turning_points.map((point, index) => (
          <article key={point.point_id} className="yearly-v2-turning-point">
            <div className="yearly-v2-turning-month"><span>{String(point.month).padStart(2, '0')}</span><small>MONTH</small></div>
            <div className="yearly-v2-turning-line"><i /><b>{String(index + 1).padStart(2, '0')}</b></div>
            <div className="yearly-v2-turning-copy">
              <p>{point.event_type.replaceAll('_', ' ')}{point.date ? ` · ${point.date}` : ''}</p>
              <h3>{point.title}</h3><span>{point.statement}</span>
              {point.entity_refs.length > 0 && <div>{point.entity_refs.slice(0, 3).map((entity) => <EntityLink key={`${entity.entity_type}-${entity.entity_id}-${entity.name}`} entity={entity} className="yearly-v2-inline-entity" />)}</div>}
            </div>
          </article>
        ))}
      </div>
      <details className="yearly-v2-month-ledger">
        <summary><span>展开十二个月事实账本</span><small>唯一月度明细 · {months.filter((month) => month.plays > 0).length}/12 个月有数据</small><ChevronDown aria-hidden="true" /></summary>
        <div className="yearly-v2-month-grid">
          {months.map((month) => (
            <article key={month.month} className={month.plays === 0 ? 'is-empty' : undefined}>
              <header><strong>{String(month.month).padStart(2, '0')}</strong><span>月</span></header>
              <p>{month.plays.toLocaleString()} 次 · {month.hours.toLocaleString(undefined, { maximumFractionDigits: 1 })} 小时</p>
              <small>{month.active_days} 个活跃日</small>
              {month.leaders.play_track && <EntityLink entity={month.leaders.play_track} className="yearly-v2-month-leader" />}
            </article>
          ))}
        </div>
      </details>
    </section>
  )
}
