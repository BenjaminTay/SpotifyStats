import { ArrowUpRight } from 'lucide-react'

import { EntityCover, EntityLink, EntityMediaLink } from '@/features/yearly-review/YearlyReviewPrimitives'
import { formatMetric } from '@/features/yearly-review/yearlyReviewData'
import type { YearlyEntityRef, YearlyHeadline, YearlyReviewResponse } from '@/types/yearly-review-v2'

function metricRepeatsStatement(conclusion: YearlyHeadline) {
  if (!conclusion.primary_metric) return false
  const normalize = (value: string) => value.replace(/[\s·，。+\-↑↓]/g, '').toLowerCase()
  return normalize(conclusion.statement).includes(normalize(formatMetric(conclusion.primary_metric)))
}

function MobileEntityShelf({ title, entities }: { title: string; entities: YearlyEntityRef[] }) {
  if (entities.length === 0) return null

  return (
    <div className="mobile-yearly-v2-epilogue-shelf">
      <h3>{title}</h3>
      <div>
        {entities.slice(0, 8).map((entity) => (
          <EntityLink
            key={`${entity.entity_type}-${entity.entity_id}-${entity.name}`}
            entity={entity}
            className="mobile-yearly-v2-epilogue-entity"
          >
            <EntityCover entity={entity} size="small" />
            <span>
              <strong>{entity.name}</strong>
              <small>{entity.artist_name ?? (entity.entity_type === 'track' ? '歌曲' : entity.entity_type === 'album' ? '专辑' : '艺人')}</small>
            </span>
            <ArrowUpRight aria-hidden="true" />
          </EntityLink>
        ))}
      </div>
    </div>
  )
}

export function MobileEpilogueChapter({ report }: { report: YearlyReviewResponse }) {
  const { epilogue } = report
  if (
    epilogue.conclusions.length === 0
    && epilogue.new_history_tops.length === 0
    && epilogue.next_year_carryovers.length === 0
  ) return null

  return (
    <section className="mobile-yearly-v2-section mobile-yearly-v2-epilogue" id="phone-yearly-epilogue">
      <header className="mobile-yearly-v2-chapter-heading">
        <span className="mobile-yearly-v2-section-number" aria-hidden="true">07</span>
        <div>
          <p className="mobile-yearly-v2-eyebrow">EPILOGUE</p>
          <h2>这一年最终留下了什么</h2>
        </div>
      </header>

      {epilogue.conclusions.length > 0 && (
        <ol className="mobile-yearly-v2-conclusions">
          {epilogue.conclusions.map((conclusion, index) => (
            <li key={conclusion.headline_id}>
              <span className="mobile-yearly-v2-conclusion-number" aria-hidden="true">
                {String(index + 1).padStart(2, '0')}
              </span>
              <div className="mobile-yearly-v2-conclusion-copy">
                <p>{conclusion.title}</p>
                <h3>{conclusion.statement}</h3>
                {conclusion.primary_metric && !metricRepeatsStatement(conclusion) && (
                  <strong>{conclusion.primary_metric.label} · {formatMetric(conclusion.primary_metric)}</strong>
                )}
                {conclusion.entity_refs.map((entity) => (
                  <EntityMediaLink
                    key={`${entity.entity_type}-${entity.entity_id}-${entity.name}`}
                    entity={entity}
                    className="mobile-yearly-v2-conclusion-entity"
                  />
                ))}
              </div>
            </li>
          ))}
        </ol>
      )}

      <div className="mobile-yearly-v2-epilogue-shelves">
        <MobileEntityShelf title="写进个人历史的新高" entities={epilogue.new_history_tops} />
        <MobileEntityShelf title="带往下一年的名字" entities={epilogue.next_year_carryovers} />
      </div>
    </section>
  )
}
