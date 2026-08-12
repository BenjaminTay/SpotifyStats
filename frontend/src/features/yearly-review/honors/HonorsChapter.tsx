import { useState } from 'react'
import { ArrowUpRight, Crown, RadioTower } from 'lucide-react'

import { EntityCover, EntityLink, MetricLine, SectionHeading } from '@/features/yearly-review/YearlyReviewPrimitives'
import { ENTITY_LABELS } from '@/features/yearly-review/yearlyReviewData'
import type { YearlyHonorItem, YearlyReviewResponse } from '@/types/yearly-review-v2'

type EntityType = 'track' | 'album' | 'artist'

function LeaderCard({ label, honor, tone }: { label: string; honor?: YearlyHonorItem; tone: 'volume' | 'season' }) {
  if (!honor?.entity) return <div className="yearly-v2-leader-card is-empty">该视角暂无合格对象</div>
  return (
    <article className={`yearly-v2-leader-card is-${tone}`}>
      <p>{tone === 'volume' ? <RadioTower aria-hidden="true" /> : <Crown aria-hidden="true" />}{label}</p>
      <div className="yearly-v2-leader-entity">
        <EntityCover entity={honor.entity} />
        <EntityLink entity={honor.entity} className="yearly-v2-entity-link" />
      </div>
      <div>{honor.metrics.slice(0, 3).map((metric) => <MetricLine key={metric.key} metric={metric} compact />)}</div>
      {honor.entity.deep_link && <EntityLink entity={honor.entity} className="yearly-v2-card-link">查看详情 <ArrowUpRight aria-hidden="true" /></EntityLink>}
    </article>
  )
}

export function HonorsChapter({ report }: { report: YearlyReviewResponse }) {
  const [entity, setEntity] = useState<EntityType>('track')
  const types: EntityType[] = ['track', 'album', 'artist']
  const honors = report.honors

  return (
    <section className="yearly-v2-section" id="yearly-v2-honors" aria-labelledby="yearly-v2-honors-title">
      <SectionHeading number="01" eyebrow="THE HONORS" title="谁赢得了这一年" description="播放总量与个人 Billboard 是两套答案：一套看消费，一套看赛季表现。" />
      <div className="yearly-v2-entity-tabs" role="tablist" aria-label="切换荣誉实体">
        {types.map((type) => <button key={type} role="tab" aria-selected={entity === type} onClick={() => setEntity(type)}>{ENTITY_LABELS[type]}</button>)}
      </div>
      <div className="yearly-v2-leader-duel">
        <LeaderCard label="播放总量冠军" honor={honors.play_leaders[entity]} tone="volume" />
        <div className="yearly-v2-versus" aria-hidden="true">VS</div>
        <LeaderCard label="个人 Billboard 冠军" honor={honors.billboard_leaders[entity]} tone="season" />
      </div>
      {honors.divergence_stories.length > 0 && (
        <div className="yearly-v2-divergence-rail">
          <p>两种视角的分歧</p>
          {honors.divergence_stories.slice(0, 4).map((story) => (
            <EntityLink key={`${story.entity.entity_type}-${story.entity.entity_id}-${story.rank_gap}`} entity={story.entity} className="yearly-v2-divergence-item">
              <strong>{story.entity.name}</strong><span>播放 #{story.play_rank} / 年榜 #{story.billboard_year_end_rank}</span><b>{story.rank_gap > 0 ? '赛季更持久' : '总量更集中'}</b>
            </EntityLink>
          ))}
        </div>
      )}
      <div className="yearly-v2-honor-grid">
        {honors.annual_honors.map((honor) => (
          <article key={honor.honor_id}>
            <span>{honor.title}</span>
            {honor.entity ? <EntityLink entity={honor.entity} className="yearly-v2-honor-link" /> : <strong>—</strong>}
            <small>{honor.metrics.slice(0, 2).map((metric) => `${metric.label} ${metric.value}${metric.unit ?? ''}`).join(' · ')}</small>
          </article>
        ))}
      </div>
    </section>
  )
}
