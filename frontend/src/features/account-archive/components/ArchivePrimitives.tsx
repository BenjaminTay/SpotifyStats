import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { AlertCircle, ArrowUpRight, Disc3, LoaderCircle } from 'lucide-react'

import { cn } from '@/lib/utils'

export function ArchiveSectionHeading({
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
    <header className="archive-section-heading">
      <div className="archive-section-number" aria-hidden="true">{number}</div>
      <div>
        <p className="archive-kicker">{eyebrow}</p>
        <h2>{title}</h2>
        <p className="archive-section-deck">{description}</p>
      </div>
    </header>
  )
}

export function ArchiveMetric({
  value,
  label,
  note,
  tone = 'ink',
}: {
  value: ReactNode
  label: string
  note?: string
  tone?: 'ink' | 'red' | 'quiet'
}) {
  return (
    <div className={cn('archive-metric', `archive-metric-${tone}`)}>
      <strong>{value}</strong>
      <span>{label}</span>
      {note && <small>{note}</small>}
    </div>
  )
}

export function ArchiveEntityRow({
  name,
  artist,
  coverUrl,
  href,
  meta,
  index,
}: {
  name: string
  artist: string
  coverUrl?: string | null
  href?: string | null
  meta?: string
  index?: number
}) {
  const content = (
    <>
      {index !== undefined && <span className="archive-entity-index">{String(index).padStart(2, '0')}</span>}
      <span className="archive-entity-cover" aria-hidden="true">
        {coverUrl ? <img src={coverUrl} alt="" loading="lazy" /> : <Disc3 />}
      </span>
      <span className="archive-entity-copy">
        <strong>{name}</strong>
        <span>{artist}</span>
      </span>
      {meta && <span className="archive-entity-meta">{meta}</span>}
      {href && <ArrowUpRight className="archive-entity-arrow" aria-hidden="true" />}
    </>
  )
  return href ? (
    <Link className="archive-entity-row" to={href}>{content}</Link>
  ) : (
    <div className="archive-entity-row">{content}</div>
  )
}

export function ArchiveLoading({ label = '正在整理这一章' }: { label?: string }) {
  return (
    <div className="archive-inline-state" aria-live="polite">
      <LoaderCircle className="animate-spin" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

export function ArchiveError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="archive-inline-state archive-inline-error" role="alert">
      <AlertCircle aria-hidden="true" />
      <span>这一章暂时无法读取。</span>
      <button type="button" onClick={onRetry}>重新加载</button>
    </div>
  )
}

export function ArchiveUnavailable({ children }: { children: ReactNode }) {
  return <div className="archive-unavailable">{children}</div>
}
