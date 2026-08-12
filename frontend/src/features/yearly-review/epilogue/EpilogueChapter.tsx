import { ArrowUpRight } from 'lucide-react'

import { EntityCover, EntityLink, EmptyChapter, SectionHeading } from '@/features/yearly-review/YearlyReviewPrimitives'
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
  return (
    <section className="yearly-v2-section yearly-v2-epilogue" id="yearly-v2-epilogue">
      <SectionHeading
        number="07"
        eyebrow="EPILOGUE"
        title="这一年最终留下了什么"
        description="结尾不是人格标签，而是几条能由全年事实支持、并可能延续到下一年的判断。"
      />
      {report.epilogue.conclusions.length === 0 ? (
        <EmptyChapter>当前覆盖范围不足以形成年度结论。</EmptyChapter>
      ) : (
        <div className="yearly-v2-conclusion-grid">
          {report.epilogue.conclusions.map((conclusion, index) => (
            <article key={conclusion.headline_id}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <p>{conclusion.title}</p>
              <h3>{conclusion.statement}</h3>
              {conclusion.primary_metric && <strong>{conclusion.primary_metric.label} · {conclusion.primary_metric.value}{conclusion.primary_metric.unit ?? ''}</strong>}
              {conclusion.entity_refs.map((entity) => <EntityLink key={`${entity.entity_type}-${entity.entity_id}`} entity={entity} className="yearly-v2-inline-entity" />)}
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
