import { EntityMediaLink, MetricLine } from '@/features/yearly-review/YearlyReviewPrimitives'
import type { YearlyReviewResponse } from '@/types/yearly-review-v2'

const RELATIONSHIP_LABELS: Record<string, string> = {
  loyal_companion: '长久陪伴',
  deep_listening: '专辑深听',
  obsession: '集中沉迷',
  return: '旧爱回归',
  new_relationship: '新关系',
  long_companion: '长久陪伴',
  deep_album: '专辑深听',
  short_obsession: '短暂着迷',
  broad_artist: '听遍作品',
}

export function MobileRelationshipsChapter({ report }: { report: YearlyReviewResponse }) {
  if (report.relationships.length === 0) return null

  return (
    <section
      className="mobile-yearly-v2-section mobile-yearly-v2-relationships"
      id="phone-yearly-relationships"
      aria-labelledby="phone-yearly-relationships-title"
    >
      <header className="mobile-yearly-v2-chapter-heading">
        <span className="mobile-yearly-v2-section-number" aria-hidden="true">03</span>
        <div>
          <p className="mobile-yearly-v2-eyebrow">RELATIONSHIPS</p>
          <h2 id="phone-yearly-relationships-title">不只是听过，而是如何喜欢</h2>
        </div>
      </header>

      <div className="mobile-yearly-v2-relationship-list">
        {report.relationships.map((story, index) => (
          <article
            key={story.story_id}
            className={`mobile-yearly-v2-relationship-story${index === 0 ? ' is-featured' : ''}`}
          >
            <header>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <p>{RELATIONSHIP_LABELS[story.relationship_type] ?? '年度关系'}</p>
            </header>
            <h3>{story.title}</h3>
            <p>{story.statement}</p>
            <EntityMediaLink
              entity={story.entity}
              size="medium"
              className="mobile-yearly-v2-relationship-entity"
            />
            {story.metrics.length > 0 && (
              <div className="mobile-yearly-v2-relationship-metrics">
                {story.metrics.slice(0, 3).map((metric) => (
                  <MetricLine key={metric.key} metric={metric} compact />
                ))}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}
