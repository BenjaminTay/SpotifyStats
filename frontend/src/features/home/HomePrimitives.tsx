import type { ReactNode } from 'react'
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import { Link } from 'react-router-dom'

import { cn } from '@/lib/utils'
import { displayName } from '@/lib/chinese'
import type { HomeEntityRef, HomeTrendPoint } from '@/types/home'
import { formatHomeDate, formatHomeNumber } from './home-format'

export function HomeSectionHeading({
  number,
  eyebrow,
  title,
  aside,
}: {
  number: string
  eyebrow: string
  title: string
  aside?: ReactNode
}) {
  return (
    <header className="home-section-heading">
      <div className="home-section-heading-copy">
        <span aria-hidden="true">{number}</span>
        <div>
          <p>{eyebrow}</p>
          <h2>{title}</h2>
        </div>
      </div>
      {aside && <div className="home-section-heading-aside">{aside}</div>}
    </header>
  )
}

export function HomeEntityArtwork({
  entity,
  eager = false,
  className,
}: {
  entity: HomeEntityRef | null
  eager?: boolean
  className?: string
}) {
  const name = displayName(entity?.name ?? '音乐档案')
  return (
    <div className={cn('home-entity-artwork', className)} data-entity-type={entity?.entity_type ?? 'archive'}>
      <span aria-hidden="true">{name.slice(0, 1).toUpperCase()}</span>
      {entity?.cover_url && (
        <img
          src={entity.cover_url}
          alt=""
          loading={eager ? 'eager' : 'lazy'}
          fetchPriority={eager ? 'high' : 'auto'}
          onError={(event) => { event.currentTarget.hidden = true }}
        />
      )}
    </div>
  )
}

export function HomeEntityLink({
  entity,
  className,
  children,
}: {
  entity: HomeEntityRef
  className?: string
  children: ReactNode
}) {
  return entity.deep_link ? (
    <Link to={entity.deep_link} className={className}>{children}</Link>
  ) : (
    <div className={className}>{children}</div>
  )
}

export function HomeChange({ value, suffix = '' }: { value: number | null; suffix?: string }) {
  if (value === null) return <span className="home-change is-neutral"><Minus aria-hidden="true" /> 暂无同期</span>
  const rounded = Math.abs(value) < 10 ? value.toFixed(1) : Math.round(value).toString()
  if (value > 0) {
    return <span className="home-change is-up"><ArrowUpRight aria-hidden="true" /> {rounded}%{suffix}</span>
  }
  if (value < 0) {
    return <span className="home-change is-down"><ArrowDownRight aria-hidden="true" /> {Math.abs(Number(rounded))}%{suffix}</span>
  }
  return <span className="home-change is-neutral"><Minus aria-hidden="true" /> 0%{suffix}</span>
}

export function HomeTrend({ points }: { points: HomeTrendPoint[] }) {
  const values = points.map((point) => point.plays)
  if (values.length < 2) {
    return <div className="home-trend-empty">播放记录不足，暂不生成趋势</div>
  }
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = Math.max(max - min, 1)
  const coordinates = values.map((value, index) => {
    const x = (index / (values.length - 1)) * 100
    const y = 92 - ((value - min) / range) * 76
    return `${x.toFixed(2)},${y.toFixed(2)}`
  }).join(' ')
  const area = `0,100 ${coordinates} 100,100`
  const totalPlays = values.reduce((sum, value) => sum + value, 0)
  const trendLabel = `${formatHomeDate(points[0]?.date)}至${formatHomeDate(points.at(-1)?.date ?? null)}播放趋势，合计${formatHomeNumber(totalPlays)}次播放`

  return (
    <div className="home-trend" role="img" aria-label={trendLabel}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <linearGradient id="homeTrendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.22" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={area} fill="url(#homeTrendFill)" />
        <polyline points={coordinates} fill="none" stroke="currentColor" strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="home-trend-labels"><span>{formatHomeDate(points[0]?.date, true)}</span><span>{formatHomeDate(points.at(-1)?.date ?? null, true)}</span></div>
    </div>
  )
}
