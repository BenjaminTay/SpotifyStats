import type { ReactNode, RefObject } from 'react'
import { Expand, Lightbulb } from 'lucide-react'

import { cn } from '@/lib/utils'
import { MobileStatePanel } from './MobileStatePanel'

export interface MobileChartSeries {
  id: string
  label: string
  active: boolean
}

interface MobileChartCardProps {
  title: string
  eyebrow?: string
  description?: string
  chart: ReactNode
  conclusion?: string
  interactionHint?: string
  controls?: ReactNode
  series?: MobileChartSeries[]
  onToggleSeries?: (id: string) => void
  onFullscreen?: () => void
  fullscreenTriggerRef?: RefObject<HTMLButtonElement | null>
  loading?: boolean
  empty?: boolean
  className?: string
}

export function MobileChartCard({
  title,
  eyebrow,
  description,
  chart,
  conclusion,
  interactionHint = '点击数据点查看详情',
  controls,
  series = [],
  onToggleSeries,
  onFullscreen,
  fullscreenTriggerRef,
  loading = false,
  empty = false,
  className,
}: MobileChartCardProps) {
  return (
    <section className={cn('mobile-chart-card', className)}>
      <header className="mobile-chart-header">
        <div className="min-w-0 flex-1">
          {eyebrow && <p>{eyebrow}</p>}
          <h2>{title}</h2>
          {description && <span>{description}</span>}
        </div>
        {onFullscreen && (
          <button ref={fullscreenTriggerRef} type="button" className="mobile-icon-button" onClick={onFullscreen} aria-label={`全屏查看${title}`}>
            <Expand className="h-4.5 w-4.5" aria-hidden="true" />
          </button>
        )}
      </header>

      {controls && <div className="mobile-chart-controls">{controls}</div>}

      {series.length > 0 && (
        <div className="mobile-chart-series" aria-label="图表系列">
          {series.map((item) => (
            <button
              key={item.id}
              type="button"
              role="switch"
              aria-checked={item.active}
              className={cn('mobile-chart-series-button', item.active && 'mobile-chart-series-active')}
              onClick={() => onToggleSeries?.(item.id)}
            >
              <span aria-hidden="true" />
              {item.label}
            </button>
          ))}
        </div>
      )}

      <div className="mobile-chart-viewport" data-reduced-motion="supported">
        {loading
          ? <MobileStatePanel variant="loading" />
          : empty
            ? <MobileStatePanel variant="empty" title="当前范围没有图表数据" />
            : chart}
      </div>

      {!loading && !empty && interactionHint && (
        <p className="mobile-chart-interaction-hint">{interactionHint}</p>
      )}

      {conclusion && (
        <p className="mobile-chart-conclusion">
          <Lightbulb className="h-4 w-4" aria-hidden="true" />
          <span>{conclusion}</span>
        </p>
      )}
    </section>
  )
}
