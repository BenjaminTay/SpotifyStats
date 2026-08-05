import { useId, useRef, type ReactNode, type RefObject } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

import { useMobileDialog } from './useMobileDialog'

interface MobileFullscreenChartProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  children: ReactNode
  controls?: ReactNode
  triggerRef?: RefObject<HTMLElement | null>
}

export function MobileFullscreenChart({
  open,
  onOpenChange,
  title,
  description,
  children,
  controls,
  triggerRef,
}: MobileFullscreenChartProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const titleId = useId()
  const descriptionId = useId()
  const { close } = useMobileDialog({
    open,
    onOpenChange,
    containerRef: dialogRef,
    triggerRef,
  })

  if (!open) return null

  return createPortal(
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      tabIndex={-1}
      className="mobile-fullscreen-chart"
      data-mobile-fullscreen="chart"
    >
      <header className="mobile-fullscreen-header">
        <div className="min-w-0 flex-1">
          <p>Immersive / Chart</p>
          <h2 id={titleId}>{title}</h2>
          {description && <span id={descriptionId}>{description}</span>}
        </div>
        <button type="button" className="mobile-icon-button" onClick={close} aria-label={`关闭${title}全屏图表`}>
          <X className="h-5 w-5" aria-hidden="true" />
        </button>
      </header>
      {controls && <div className="mobile-fullscreen-controls">{controls}</div>}
      <div className="mobile-fullscreen-canvas">{children}</div>
    </div>,
    document.body,
  )
}
