import type { ReactNode } from 'react'
import { AlertCircle, Music2, SlidersHorizontal } from 'lucide-react'

import { cn } from '@/lib/utils'

type MobileStateVariant = 'loading' | 'empty' | 'error' | 'config'

interface MobileStatePanelProps {
  variant: MobileStateVariant
  title?: string
  description?: string
  actionLabel?: string
  onAction?: () => void
  icon?: ReactNode
  compact?: boolean
}

const DEFAULT_COPY: Record<Exclude<MobileStateVariant, 'loading'>, { title: string; description: string }> = {
  empty: { title: '这里还没有内容', description: '换一个时间范围或筛选条件再看看。' },
  error: { title: '暂时无法加载', description: '请稍后重试，已应用的条件不会丢失。' },
  config: { title: '需要先完成设置', description: '配置完成后，这里的内容会自动出现。' },
}

export function MobileStatePanel({
  variant,
  title,
  description,
  actionLabel,
  onAction,
  icon,
  compact = false,
}: MobileStatePanelProps) {
  if (variant === 'loading') {
    return (
      <div className={cn('mobile-state-panel mobile-state-loading', compact && 'mobile-state-compact')} role="status" aria-label="正在加载">
        <span className="mobile-state-skeleton mobile-state-skeleton-title" />
        <span className="mobile-state-skeleton" />
        <span className="mobile-state-skeleton mobile-state-skeleton-short" />
      </div>
    )
  }

  const copy = DEFAULT_COPY[variant]
  const defaultIcon = variant === 'error'
    ? <AlertCircle aria-hidden="true" />
    : variant === 'config'
      ? <SlidersHorizontal aria-hidden="true" />
      : <Music2 aria-hidden="true" />

  return (
    <section
      className={cn('mobile-state-panel', compact && 'mobile-state-compact')}
      role={variant === 'error' ? 'alert' : 'status'}
      data-state={variant}
    >
      <div className="mobile-state-icon">{icon ?? defaultIcon}</div>
      <h3 className="mobile-state-title">{title ?? copy.title}</h3>
      <p className="mobile-state-description">{description ?? copy.description}</p>
      {actionLabel && onAction && (
        <button type="button" className="mobile-secondary-button" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </section>
  )
}
