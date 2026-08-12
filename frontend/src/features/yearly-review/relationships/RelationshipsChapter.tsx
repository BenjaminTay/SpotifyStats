import { EntityMediaLink, MetricLine, SectionHeading } from '@/features/yearly-review/YearlyReviewPrimitives'
import { displayYearlyText } from '@/features/yearly-review/yearlyReviewData'
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

export function RelationshipsChapter({ report }: { report: YearlyReviewResponse }) {
  if (report.relationships.length === 0) return null
  return (
    <section className="yearly-v2-section" id="yearly-v2-relationships">
      <SectionHeading number="03" eyebrow="RELATIONSHIPS" title="不只是听过，而是如何喜欢" />
      <div className="yearly-v2-relationship-grid">
          {report.relationships.map((story, index) => (
            <article key={story.story_id} className={index % 5 === 0 ? 'is-featured' : undefined}>
              <div className="yearly-v2-relationship-top"><span>{RELATIONSHIP_LABELS[story.relationship_type] ?? '年度关系'}</span></div>
              <h3>{displayYearlyText(story.title)}</h3><p>{displayYearlyText(story.statement)}</p>
              <EntityMediaLink entity={story.entity} size="medium" className="yearly-v2-relationship-entity" />
              <div>{story.metrics.slice(0, 3).map((metric) => <MetricLine key={metric.key} metric={metric} compact />)}</div>
            </article>
          ))}
      </div>
    </section>
  )
}
