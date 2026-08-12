import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { cn } from '@/lib/utils'
import type { YearlyEntityRef, YearlyMetric } from '@/types/yearly-review-v2'
import { entitySubtitle, formatMetric } from './yearlyReviewData'

export function SectionHeading({
  number,
  eyebrow,
  title,
  description,
}: {
  number: string
  eyebrow: string
  title: string
  description: string
}) {
  return (
    <header className="yearly-v2-section-heading">
      <span aria-hidden="true" className="yearly-v2-section-number">{number}</span>
      <div>
        <p>{eyebrow}</p>
        <h2>{title}</h2>
        <span>{description}</span>
      </div>
    </header>
  )
}

export function MetricLine({ metric, compact = false }: { metric: YearlyMetric; compact?: boolean }) {
  return (
    <div className={cn('yearly-v2-metric-line', compact && 'is-compact')}>
      <span>{metric.label}</span>
      <strong>{formatMetric(metric)}</strong>
    </div>
  )
}

export function EntityLink({
  entity,
  children,
  className,
}: {
  entity: YearlyEntityRef
  children?: ReactNode
  className?: string
}) {
  const body = children ?? (
    <>
      <strong>{entity.name}</strong>
      {entitySubtitle(entity) && <span>{entitySubtitle(entity)}</span>}
    </>
  )
  return entity.deep_link ? (
    <Link className={className} to={entity.deep_link}>{body}</Link>
  ) : (
    <div className={className}>{body}</div>
  )
}

export function EntityCover({ entity, size = 'medium' }: { entity: YearlyEntityRef; size?: 'small' | 'medium' }) {
  return (
    <div className={cn('yearly-v2-entity-cover', size === 'small' && 'is-small')}>
      <span aria-hidden="true">{entity.name.slice(0, 1).toUpperCase()}</span>
      {entity.cover_url && (
        <img
          src={entity.cover_url}
          alt=""
          loading="lazy"
          onError={(event) => { event.currentTarget.hidden = true }}
        />
      )}
    </div>
  )
}

export function EmptyChapter({ children }: { children: ReactNode }) {
  return <p className="yearly-v2-chapter-empty">{children}</p>
}
