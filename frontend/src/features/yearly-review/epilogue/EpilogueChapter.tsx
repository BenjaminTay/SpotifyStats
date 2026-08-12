import { ArrowUpRight } from 'lucide-react'

import { EntityCover, EntityLink, EntityMediaLink, SectionHeading } from '@/features/yearly-review/YearlyReviewPrimitives'
import type { YearlyEntityRef, YearlyReviewResponse } from '@/types/yearly-review-v2'

function EntityShelf({ title, entities }: { title: string; entities: YearlyEntityRef[] }) {
  if (entities.length === 0) return null
  return (
    <div className="yearly-v2-epilogue-shelf">
      <p>{title}</p>
      <div>
        {entities.slice(0, 8).map((entity) => (
          <EntityLink key={`${entity.entity_type}-${entity.entity_id}-${entity.name}`} entity={entity} className="yearly-v2-epilogue-entity">
            <EntityCover entity={entity} size="small" />
            <span><strong>{entity.name}</strong><small>{entity.artist_name ?? entity.entity_type}</small></span>
            <ArrowUpRight aria-hidden="true" />
          </EntityLink>
        ))}
      </div>
    </div>
  )
}

export function EpilogueChapter({ report }: { report: YearlyReviewResponse }) {
  if (
    report.epilogue.conclusions.length === 0
    && report.epilogue.new_history_tops.length === 0
    && report.epilogue.next_year_carryovers.length === 0
  ) return null
  return (
    <section className="yearly-v2-section yearly-v2-epilogue" id="yearly-v2-epilogue">
      <SectionHeading number="07" eyebrow="EPILOGUE" title="这一年最终留下了什么" />
      {report.epilogue.conclusions.length > 0 && (
        <div className="yearly-v2-conclusion-grid">
          {report.epilogue.conclusions.map((conclusion, index) => (
            <article key={conclusion.headline_id}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <p>{conclusion.title}</p>
              <h3>{conclusion.statement}</h3>
              {conclusion.primary_metric && <strong>{conclusion.primary_metric.label} · {conclusion.primary_metric.value}{conclusion.primary_metric.unit ?? ''}</strong>}
              {conclusion.entity_refs.map((entity) => <EntityMediaLink key={`${entity.entity_type}-${entity.entity_id}`} entity={entity} className="yearly-v2-conclusion-entity" />)}
            </article>
          ))}
        </div>
      )}
      <div className="yearly-v2-epilogue-shelves">
        <EntityShelf title="写进个人历史的新高" entities={report.epilogue.new_history_tops} />
        <EntityShelf title="带往下一年的名字" entities={report.epilogue.next_year_carryovers} />
      </div>
    </section>
  )
}
