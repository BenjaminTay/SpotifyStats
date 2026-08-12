import { MoonStar, Repeat2, Sparkles, TimerReset } from 'lucide-react'

import { EntityLink, EmptyChapter, MetricLine, SectionHeading } from '@/features/yearly-review/YearlyReviewPrimitives'
import type { YearlyReviewResponse } from '@/types/yearly-review-v2'

const ICONS = [TimerReset, MoonStar, Repeat2, Sparkles]

export function ListeningLifeChapter({ report }: { report: YearlyReviewResponse }) {
  const observations = report.listening_life.observations

  return (
    <section className="yearly-v2-section" id="yearly-v2-listening-life">
      <SectionHeading
        number="04"
        eyebrow="LISTENING LIFE"
        title="音乐如何进入日常"
        description="从收听时段、工作日与周末、深夜占比到复听宽度，把抽象习惯还原成可核验的生活切面。"
      />
      {observations.length === 0 ? (
        <EmptyChapter>当前播放样本不足以形成稳定的生活节奏观察。</EmptyChapter>
      ) : (
        <div className="yearly-v2-life-grid">
          {observations.map((observation, index) => {
            const Icon = ICONS[index % ICONS.length]
            return (
              <article key={observation.headline_id}>
                <div className="yearly-v2-life-index">
                  <Icon aria-hidden="true" />
                  <span>{String(index + 1).padStart(2, '0')}</span>
                </div>
                <p>{observation.title}</p>
                <h3>{observation.statement}</h3>
                {observation.primary_metric && <MetricLine metric={observation.primary_metric} compact />}
                {observation.entity_refs.length > 0 && (
                  <div className="yearly-v2-life-entities">
                    {observation.entity_refs.map((entity) => (
                      <EntityLink
                        key={`${entity.entity_type}-${entity.entity_id}-${entity.name}`}
                        entity={entity}
                        className="yearly-v2-inline-entity"
                      />
                    ))}
                  </div>
                )}
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}
