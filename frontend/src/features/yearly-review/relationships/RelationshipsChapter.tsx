import { EntityCover, EntityLink, EmptyChapter, MetricLine, SectionHeading } from '@/features/yearly-review/YearlyReviewPrimitives'
import type { YearlyReviewResponse } from '@/types/yearly-review-v2'

const RELATIONSHIP_LABELS: Record<string, string> = {
  loyal_companion: '长久陪伴',
  deep_listening: '专辑深听',
  obsession: '集中沉迷',
  return: '旧爱回归',
  new_relationship: '新关系',
}

export function RelationshipsChapter({ report }: { report: YearlyReviewResponse }) {
  return (
    <section className="yearly-v2-section" id="yearly-v2-relationships">
      <SectionHeading number="03" eyebrow="RELATIONSHIPS" title="不只是听过，而是如何喜欢" description="陪伴、沉迷、深听与回归都必须同时得到至少两项事实支持。" />
      {report.relationships.length === 0 ? <EmptyChapter>当前观察范围内，没有达到关系故事门槛的对象。</EmptyChapter> : (
        <div className="yearly-v2-relationship-grid">
          {report.relationships.map((story, index) => (
            <article key={story.story_id} className={index % 5 === 0 ? 'is-featured' : undefined}>
              <div className="yearly-v2-relationship-top"><EntityCover entity={story.entity} size="small" /><span>{RELATIONSHIP_LABELS[story.relationship_type] ?? '年度关系'}</span></div>
              <h3>{story.title}</h3><p>{story.statement}</p>
              <EntityLink entity={story.entity} className="yearly-v2-relationship-entity" />
              <div>{story.metrics.slice(0, 3).map((metric) => <MetricLine key={metric.key} metric={metric} compact />)}</div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
