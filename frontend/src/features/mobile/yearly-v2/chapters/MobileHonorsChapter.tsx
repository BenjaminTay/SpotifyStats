import { useMemo, useState } from 'react'

import {
  EntityMediaLink,
  MetricLine,
} from '@/features/yearly-review/YearlyReviewPrimitives'
import { ENTITY_LABELS } from '@/features/yearly-review/yearlyReviewData'
import type {
  YearlyHonorItem,
  YearlyReviewResponse,
} from '@/types/yearly-review-v2'

type EntityType = 'track' | 'album' | 'artist'

const ENTITY_TYPES: EntityType[] = ['track', 'album', 'artist']

function MobileLeaderCard({
  honor,
  label,
  position,
}: {
  honor?: YearlyHonorItem
  label: string
  position: 'play' | 'billboard'
}) {
  if (!honor?.entity) {
    return (
      <article className={`mobile-yearly-v2-leader is-${position} is-empty`}>
        <p>{label}</p>
        <span>这一项暂时没有冠军</span>
      </article>
    )
  }

  return (
    <article className={`mobile-yearly-v2-leader is-${position}`}>
      <header>
        <span>{position === 'play' ? '01' : '02'}</span>
        <p>{label}</p>
      </header>
      <EntityMediaLink
        entity={honor.entity}
        size="medium"
        className="mobile-yearly-v2-leader-entity"
      />
      <div className="mobile-yearly-v2-leader-metrics">
        {honor.metrics.slice(0, 3).map((metric) => (
          <MetricLine key={metric.key} metric={metric} compact />
        ))}
      </div>
    </article>
  )
}

export function MobileHonorsChapter({ report }: { report: YearlyReviewResponse }) {
  const [entityType, setEntityType] = useState<EntityType>('track')
  const { honors } = report
  const groupedHonors = useMemo(() => {
    const groups = new Map<string, YearlyHonorItem[]>()
    for (const honor of honors.annual_honors) {
      if (!honor.entity) continue
      const key = `${honor.entity.entity_type}:${honor.entity.entity_id ?? honor.entity.name}`
      groups.set(key, [...(groups.get(key) ?? []), honor])
    }
    return [...groups.values()]
  }, [honors.annual_honors])

  return (
    <section
      className="mobile-yearly-v2-section mobile-yearly-v2-honors"
      id="phone-yearly-honors"
      aria-labelledby="phone-yearly-honors-title"
    >
      <header className="mobile-yearly-v2-chapter-heading">
        <span className="mobile-yearly-v2-section-number" aria-hidden="true">01</span>
        <div>
          <p className="mobile-yearly-v2-eyebrow">THE HONORS</p>
          <h2 id="phone-yearly-honors-title">谁赢得了这一年</h2>
        </div>
      </header>

      <div className="mobile-yearly-v2-segmented" role="tablist" aria-label="切换荣誉类型">
        {ENTITY_TYPES.map((type) => (
          <button
            key={type}
            type="button"
            role="tab"
            aria-selected={entityType === type}
            aria-controls="phone-yearly-honors-leaders"
            onClick={() => setEntityType(type)}
          >
            {ENTITY_LABELS[type]}
          </button>
        ))}
      </div>

      <div
        className="mobile-yearly-v2-leaders"
        id="phone-yearly-honors-leaders"
        role="tabpanel"
      >
        <MobileLeaderCard
          honor={honors.play_leaders[entityType]}
          label="播放冠军"
          position="play"
        />
        <MobileLeaderCard
          honor={honors.billboard_leaders[entityType]}
          label="个人年榜冠军"
          position="billboard"
        />
      </div>

      {honors.divergence_stories.length > 0 && (
        <div className="mobile-yearly-v2-divergence">
          <h3>两种排名，两种答案</h3>
          <div className="mobile-yearly-v2-divergence-list">
            {honors.divergence_stories.map((story) => (
              <EntityMediaLink
                key={`${story.entity.entity_type}-${story.entity.entity_id}-${story.rank_gap}`}
                entity={story.entity}
                className="mobile-yearly-v2-divergence-row"
                meta={`播放第 ${story.play_rank} · 个人年榜第 ${story.billboard_year_end_rank}`}
              />
            ))}
          </div>
        </div>
      )}

      {groupedHonors.length > 0 && (
        <div className="mobile-yearly-v2-honor-list">
          {groupedHonors.map((items) => {
            const honor = items[0]
            if (!honor.entity) return null
            const metrics = honor.metrics.filter((metric) => metric.key !== 'year_end_score').slice(0, 2)
            return (
              <article key={`${honor.entity.entity_type}-${honor.entity.entity_id ?? honor.entity.name}`}>
                <ul className="mobile-yearly-v2-honor-titles" aria-label="获得的年度荣誉">
                  {items.map((item) => <li key={item.honor_id}>{item.title}</li>)}
                </ul>
                <EntityMediaLink
                  entity={honor.entity}
                  size="medium"
                  className="mobile-yearly-v2-honor-entity"
                />
                {metrics.length > 0 && (
                  <div className="mobile-yearly-v2-honor-metrics">
                    {metrics.map((metric) => <MetricLine key={metric.key} metric={metric} compact />)}
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
