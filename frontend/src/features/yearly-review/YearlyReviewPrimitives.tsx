import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { cn } from '@/lib/utils'
import { displayName, useChineseTextVersion } from '@/lib/chinese'
import type { YearlyEntityRef, YearlyMetric } from '@/types/yearly-review-v2'
import { displayYearlyText, entitySubtitle, formatMetric } from './yearlyReviewData'

export function SectionHeading({
  number,
  eyebrow,
  title,
}: {
  number: string
  eyebrow: string
  title: string
}) {
  return (
    <header className="yearly-v2-section-heading">
      <span aria-hidden="true" className="yearly-v2-section-number">{number}</span>
      <div>
        <p>{eyebrow}</p>
        <h2>{title}</h2>
      </div>
    </header>
  )
}

export function MetricLine({ metric, compact = false }: { metric: YearlyMetric; compact?: boolean }) {
  useChineseTextVersion()
  return (
    <div className={cn('yearly-v2-metric-line', compact && 'is-compact')}>
      <span>{displayYearlyText(metric.label)}</span>
      <strong>{displayYearlyText(formatMetric(metric))}</strong>
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
  useChineseTextVersion()
  const body = children ?? (
    <>
      <strong>{displayName(entity.name)}</strong>
      {entitySubtitle(entity) && <span>{entitySubtitle(entity)}</span>}
    </>
  )
  return entity.deep_link ? (
    <Link className={className} data-entity-type={entity.entity_type} to={entity.deep_link}>{body}</Link>
  ) : (
    <div className={className} data-entity-type={entity.entity_type}>{body}</div>
  )
}

export function EntityCover({ entity, size = 'medium' }: { entity: YearlyEntityRef; size?: 'small' | 'medium' }) {
  useChineseTextVersion()
  const displayEntityName = displayName(entity.name)
  return (
    <div
      className={cn('yearly-v2-entity-cover', size === 'small' && 'is-small')}
      data-entity-type={entity.entity_type}
    >
      <span aria-hidden="true">{displayEntityName.slice(0, 1).toUpperCase()}</span>
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

export function EntityMediaLink({
  entity,
  size = 'small',
  className,
  meta,
}: {
  entity: YearlyEntityRef
  size?: 'small' | 'medium'
  className?: string
  meta?: ReactNode
}) {
  useChineseTextVersion()
  return (
    <EntityLink entity={entity} className={cn('yearly-v2-entity-media', className)}>
      <EntityCover entity={entity} size={size} />
      <span>
        <strong>{displayName(entity.name)}</strong>
        {(meta || entitySubtitle(entity)) && <small>{meta || entitySubtitle(entity)}</small>}
      </span>
    </EntityLink>
  )
}

export function EmptyChapter({ children }: { children: ReactNode }) {
  return <p className="yearly-v2-chapter-empty">{children}</p>
}
