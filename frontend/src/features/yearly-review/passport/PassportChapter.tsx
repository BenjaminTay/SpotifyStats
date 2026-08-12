import { CalendarRange, Fingerprint } from 'lucide-react'

import { STATUS_COPY } from '@/features/yearly-review/yearlyReviewData'
import { EntityLink } from '@/features/yearly-review/YearlyReviewPrimitives'
import type { YearlyReviewResponse } from '@/types/yearly-review-v2'

export function PassportChapter({ report }: { report: YearlyReviewResponse }) {
  const passport = report.passport
  if (!passport) return null
  const status = STATUS_COPY[report.status]

  return (
    <section className="yearly-v2-cover" aria-labelledby="yearly-v2-cover-title">
      <div className="yearly-v2-cover-orbit" aria-hidden="true" />
      <div className="yearly-v2-cover-kicker">
        <span>PERSONAL LISTENING ANNUAL</span>
        <span>ISSUE {String(report.year).slice(-2)}</span>
      </div>
      <div className="yearly-v2-cover-main">
        <div>
          <p className="yearly-v2-cover-status"><i />{status.label} · {status.note}</p>
          <h1 id="yearly-v2-cover-title"><span>{report.year}</span> 我的音乐年鉴</h1>
          <p className="yearly-v2-cover-deck">
            不只是谁听得最多。这里记录榜首如何更替、关系如何沉淀，以及这一年的品味真正往哪里移动。
          </p>
        </div>
        <div className="yearly-v2-cover-meta">
          <div><CalendarRange aria-hidden="true" /><span>观察范围</span><strong>{passport.observed_start ?? '—'}<br />至 {passport.observed_end ?? '—'}</strong></div>
          <div><Fingerprint aria-hidden="true" /><span>统计口径</span><strong>L{report.filter_context.merge_level} 归并<br />{report.filter_context.dynamic_threshold ? '动态有效阈值' : '固定阈值'}</strong></div>
        </div>
      </div>
      <div className="yearly-v2-kpi-strip">
        {passport.metrics.map((metric) => (
          <div key={metric.key}>
            <span>{metric.label}</span>
            <strong>{typeof metric.value === 'number' ? metric.value.toLocaleString('zh-CN', { maximumFractionDigits: 1 }) : metric.value}</strong>
            <small>{metric.unit}</small>
          </div>
        ))}
      </div>
      {report.headlines.length > 0 && (
        <div className="yearly-v2-headlines">
          {report.headlines.map((headline, index) => (
            <article key={headline.headline_id}>
              <span>0{index + 1}</span>
              <div><p>{headline.title}</p><h3>{headline.statement}</h3>{headline.entity_refs.slice(0, 1).map((entity) => <EntityLink key={`${entity.entity_type}-${entity.entity_id}-${entity.name}`} entity={entity} className="yearly-v2-inline-entity" />)}</div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
