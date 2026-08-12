import { EntityMediaLink, MetricLine } from '@/features/yearly-review/YearlyReviewPrimitives'
import { formatMetric } from '@/features/yearly-review/yearlyReviewData'
import type { YearlyHeadline, YearlyReviewResponse } from '@/types/yearly-review-v2'

function metricRepeatsStatement(observation: YearlyHeadline) {
  if (!observation.primary_metric) return false
  const normalize = (value: string) => value.replace(/[\s·，。+\-↑↓]/g, '').toLowerCase()
  return normalize(observation.statement).includes(normalize(formatMetric(observation.primary_metric)))
}

function ObservationEntities({ observation }: { observation: YearlyHeadline }) {
  if (observation.entity_refs.length === 0) return null
  return (
    <div className="mobile-yearly-v2-life-entities">
      {observation.entity_refs.map((entity) => (
        <EntityMediaLink
          key={`${entity.entity_type}-${entity.entity_id ?? entity.name}`}
          entity={entity}
          className="mobile-yearly-v2-life-entity"
        />
      ))}
    </div>
  )
}

export function MobileListeningLifeChapter({ report }: { report: YearlyReviewResponse }) {
  const { metrics, observations } = report.listening_life
  const [leadObservation, ...otherObservations] = observations
  const primaryMetricKeys = new Set(
    observations.flatMap((observation) => observation.primary_metric?.key ?? []),
  )
  const supportingMetrics = metrics
    .filter((metric) => !primaryMetricKeys.has(metric.key))
    .slice(0, 4)
  if (!leadObservation && metrics.length === 0) return null

  return (
    <section
      className="mobile-yearly-v2-section mobile-yearly-v2-listening-life"
      id="phone-yearly-listening-life"
      aria-labelledby="phone-yearly-listening-life-title"
    >
      <header className="mobile-yearly-v2-chapter-heading">
        <span className="mobile-yearly-v2-section-number" aria-hidden="true">04</span>
        <div>
          <p className="mobile-yearly-v2-eyebrow">LISTENING LIFE</p>
          <h2 id="phone-yearly-listening-life-title">音乐如何进入日常</h2>
        </div>
      </header>

      {leadObservation && (
        <article className="mobile-yearly-v2-life-lead">
          <p>{leadObservation.title}</p>
          <h3>{leadObservation.statement}</h3>
          {leadObservation.primary_metric && !metricRepeatsStatement(leadObservation) && (
            <MetricLine metric={leadObservation.primary_metric} compact />
          )}
          <ObservationEntities observation={leadObservation} />
        </article>
      )}

      {supportingMetrics.length > 0 && (
        <div className="mobile-yearly-v2-life-facts" aria-label="听歌日常的补充数字">
          {supportingMetrics.map((metric) => (
            <article key={metric.key}>
              <MetricLine metric={metric} compact />
            </article>
          ))}
        </div>
      )}

      {otherObservations.length > 0 && (
        <div className="mobile-yearly-v2-life-observations">
          {otherObservations.map((observation, index) => (
            <article key={observation.headline_id} className="mobile-yearly-v2-life-observation">
              <header>
                <span aria-hidden="true">{String(index + 2).padStart(2, '0')}</span>
                <p>{observation.title}</p>
              </header>
              <h3>{observation.statement}</h3>
              {observation.primary_metric && !metricRepeatsStatement(observation) && (
                <MetricLine metric={observation.primary_metric} compact />
              )}
              <ObservationEntities observation={observation} />
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
