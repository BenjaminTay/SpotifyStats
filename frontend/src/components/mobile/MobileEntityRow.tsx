import { useState, type ReactNode } from 'react'
import { Disc3, Mic2, Music2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { rankToneClass } from '@/lib/rank-tone'
import { cn } from '@/lib/utils'

export type MobileEntityType = 'track' | 'album' | 'artist'

export interface MobileEntityFact {
  label: string
  value: string
}

export interface MobileEntityRowProps {
  entityType: MobileEntityType
  title: ReactNode
  subtitle?: ReactNode
  rank?: number
  rankAdornment?: ReactNode
  coverUrl?: string | null
  metric: string
  metricLabel?: string
  metricRank?: number
  facts?: MobileEntityFact[]
  factsLimit?: number
  badges?: string[]
  to?: string
  onClick?: () => void
  trailing?: ReactNode
  className?: string
}

export function MobileEntityArtwork({ type, coverUrl }: { type: MobileEntityType; coverUrl?: string | null }) {
  const [failed, setFailed] = useState(false)
  const fallback = type === 'artist'
    ? <Mic2 aria-hidden="true" />
    : type === 'album'
      ? <Disc3 aria-hidden="true" />
      : <Music2 aria-hidden="true" />

  return (
    <span className={cn('mobile-entity-artwork', `mobile-entity-artwork-${type}`)}>
      {coverUrl && !failed
        ? <img src={coverUrl} alt="" loading="lazy" onError={() => setFailed(true)} />
        : fallback}
    </span>
  )
}

export function MobileEntityRow({
  entityType,
  title,
  subtitle,
  rank,
  rankAdornment,
  coverUrl,
  metric,
  metricLabel,
  metricRank,
  facts = [],
  factsLimit = 2,
  badges = [],
  to,
  onClick,
  trailing,
  className,
}: MobileEntityRowProps) {
  const content = (
    <>
      {rank !== undefined && (
        rankAdornment ? (
          <span className="mobile-entity-rank-cluster">
            <span className="mobile-entity-rank">{String(rank).padStart(2, '0')}</span>
            <span className="mobile-entity-rank-status">{rankAdornment}</span>
          </span>
        ) : <span className="mobile-entity-rank">{rank}</span>
      )}
      <MobileEntityArtwork key={`${entityType}:${coverUrl ?? 'missing'}`} type={entityType} coverUrl={coverUrl} />
      <span className="mobile-entity-copy">
        <span className="mobile-entity-title">{title}</span>
        {subtitle && <span className="mobile-entity-subtitle">{subtitle}</span>}
        {(facts.length > 0 || badges.length > 0) && (
          <span className="mobile-entity-facts">
            {facts.slice(0, factsLimit).map((fact) => (
              <span key={`${fact.label}:${fact.value}`}>{fact.label} {fact.value}</span>
            ))}
            {badges.length > 0 && (
              <span className="mobile-entity-badges">
                {badges.slice(0, 2).map((badge) => <em key={badge}>{badge}</em>)}
              </span>
            )}
          </span>
        )}
      </span>
      <span className="mobile-entity-metric">
        <strong className={metricRank ? rankToneClass(metricRank, true) : undefined}>{metric}</strong>
        {metricLabel && <small>{metricLabel}</small>}
      </span>
      {trailing}
    </>
  )
  const rowClass = cn(
    'mobile-entity-row',
    rank === undefined && 'mobile-entity-row-no-rank',
    (to || onClick) && 'mobile-entity-row-interactive',
    className,
  )

  if (to) return <Link to={to} className={rowClass} onClick={onClick}>{content}</Link>
  if (onClick) return <button type="button" onClick={onClick} className={rowClass}>{content}</button>
  return <div className={rowClass}>{content}</div>
}
