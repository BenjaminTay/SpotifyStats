import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

interface MobilePageHeaderProps {
  title: string
  eyebrow?: string
  description?: string
  meta?: ReactNode
  actions?: ReactNode
  compact?: boolean
  className?: string
}

export function MobilePageHeader({
  title,
  eyebrow,
  description,
  meta,
  actions,
  compact = false,
  className,
}: MobilePageHeaderProps) {
  return (
    <header className={cn('mobile-page-header', compact && 'mobile-page-header-compact', className)}>
      <div className="mobile-page-header-rule" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        {eyebrow && <p className="mobile-page-eyebrow">{eyebrow}</p>}
        <h1 className="mobile-page-title">{title}</h1>
        {description && <p className="mobile-page-description">{description}</p>}
        {meta && <div className="mobile-page-meta">{meta}</div>}
      </div>
      {actions && <div className="mobile-page-actions">{actions}</div>}
    </header>
  )
}
