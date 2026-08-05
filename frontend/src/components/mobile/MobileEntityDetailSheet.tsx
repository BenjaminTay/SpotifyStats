import { useState, type RefObject } from 'react'
import { ArrowUpRight, Disc3, Mic2, Music2, Share2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { MobileEntityFact, MobileEntityType } from './MobileEntityRow'
import { MobileBottomSheet } from './MobileBottomSheet'

interface MobileEntityDetailSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  entityType: MobileEntityType
  title: string
  subtitle?: string
  coverUrl?: string | null
  metric?: string
  metricLabel?: string
  facts: MobileEntityFact[]
  badges?: string[]
  rangeNote?: string
  detailTo?: string
  onShare?: () => void
  triggerRef?: RefObject<HTMLElement | null>
}

const ENTITY_LABEL: Record<MobileEntityType, string> = {
  track: '歌曲详情',
  album: '专辑详情',
  artist: '艺人详情',
}

function EntityFallback({ type }: { type: MobileEntityType }) {
  if (type === 'artist') return <Mic2 aria-hidden="true" />
  if (type === 'album') return <Disc3 aria-hidden="true" />
  return <Music2 aria-hidden="true" />
}

function EntityDetailArtwork({ type, coverUrl }: { type: MobileEntityType; coverUrl?: string | null }) {
  const [failed, setFailed] = useState(false)
  return (
    <div className="mobile-detail-artwork">
      {coverUrl && !failed
        ? <img src={coverUrl} alt="" onError={() => setFailed(true)} />
        : <EntityFallback type={type} />}
    </div>
  )
}

export function MobileEntityDetailSheet({
  open,
  onOpenChange,
  entityType,
  title,
  subtitle,
  coverUrl,
  metric,
  metricLabel,
  facts,
  badges = [],
  rangeNote,
  detailTo,
  onShare,
  triggerRef,
}: MobileEntityDetailSheetProps) {
  return (
    <MobileBottomSheet
      open={open}
      onOpenChange={onOpenChange}
      title={ENTITY_LABEL[entityType]}
      eyebrow="Inspect / Detail"
      triggerRef={triggerRef}
      dataSheet="entity-detail"
    >
      <article className="mobile-entity-detail">
        <div className="mobile-detail-hero">
          <EntityDetailArtwork key={`${entityType}:${coverUrl ?? 'missing'}`} type={entityType} coverUrl={coverUrl} />
          <div className="min-w-0 flex-1">
            <h3>{title}</h3>
            {subtitle && <p>{subtitle}</p>}
            {(metric || metricLabel) && (
              <div className="mobile-detail-primary-metric">
                {metric && <strong>{metric}</strong>}
                {metricLabel && <span>{metricLabel}</span>}
              </div>
            )}
          </div>
        </div>

        {badges.length > 0 && (
          <div className="mobile-detail-badges">
            {badges.map((badge) => <span key={badge}>{badge}</span>)}
          </div>
        )}

        <dl className="mobile-detail-facts">
          {facts.map((fact) => (
            <div key={`${fact.label}:${fact.value}`}>
              <dt>{fact.label}</dt>
              <dd>{fact.value}</dd>
            </div>
          ))}
        </dl>

        {rangeNote && <p className="mobile-detail-range-note">统计范围：{rangeNote}</p>}
        {(detailTo || onShare) && (
          <div className="mobile-detail-actions">
            {detailTo && (
              <Link to={detailTo} className="mobile-primary-button" onClick={() => onOpenChange(false)}>
                查看完整详情
                <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
              </Link>
            )}
            {onShare && (
              <button type="button" className="mobile-secondary-button" onClick={onShare}>
                <Share2 className="h-4 w-4" aria-hidden="true" />
                分享
              </button>
            )}
          </div>
        )}
      </article>
    </MobileBottomSheet>
  )
}
