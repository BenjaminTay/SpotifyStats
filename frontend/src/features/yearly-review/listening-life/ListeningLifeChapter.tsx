import { MoonStar, Repeat2, Sparkles, TimerReset } from 'lucide-react'

import { EntityMediaLink, MetricLine, SectionHeading } from '@/features/yearly-review/YearlyReviewPrimitives'
import { displayYearlyText } from '@/features/yearly-review/yearlyReviewData'
import type { YearlyReviewResponse } from '@/types/yearly-review-v2'

const ICONS = [TimerReset, MoonStar, Repeat2, Sparkles]

export function ListeningLifeChapter({ report }: { report: YearlyReviewResponse }) {
  const observations = report.listening_life.observations
  if (observations.length === 0) return null

  return (
    <section className="yearly-v2-section" id="yearly-v2-listening-life">
      <SectionHeading number="04" eyebrow="LISTENING LIFE" title="音乐如何进入日常" />
      <div className="yearly-v2-life-grid">
          {observations.map((observation, index) => {
            const Icon = ICONS[index % ICONS.length]
            return (
              <article key={observation.headline_id}>
                <div className="yearly-v2-life-index">
                  <Icon aria-hidden="true" />
                  <span>{String(index + 1).padStart(2, '0')}</span>
                </div>
                <p>{displayYearlyText(observation.title)}</p>
                <h3>{displayYearlyText(observation.statement)}</h3>
                {observation.primary_metric?.unit === '%' && typeof observation.primary_metric.value === 'number' && (
                  <div className="yearly-v2-life-meter" aria-label={`${observation.primary_metric.label} ${observation.primary_metric.value}%`}>
                    <i style={{ width: `${Math.min(Math.max(observation.primary_metric.value, 2), 100)}%` }} />
                  </div>
                )}
                {observation.primary_metric && <MetricLine metric={observation.primary_metric} compact />}
                {observation.entity_refs.length > 0 && (
                  <div className="yearly-v2-life-entities">
                    {observation.entity_refs.map((entity) => (
                      <EntityMediaLink
                        key={`${entity.entity_type}-${entity.entity_id}-${entity.name}`}
                        entity={entity}
                        className="yearly-v2-life-entity"
                      />
                    ))}
                  </div>
                )}
              </article>
            )
          })}
      </div>
    </section>
  )
}
