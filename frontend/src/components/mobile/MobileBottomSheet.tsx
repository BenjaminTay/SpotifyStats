import { useId, useRef, type ReactNode, type RefObject } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

import { cn } from '@/lib/utils'
import { useMobileDialog } from './useMobileDialog'

interface MobileBottomSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  eyebrow?: string
  description?: string
  children: ReactNode
  footer?: ReactNode
  triggerRef?: RefObject<HTMLElement | null>
  initialFocusRef?: RefObject<HTMLElement | null>
  className?: string
  contentClassName?: string
  dataSheet?: string
}

export function MobileBottomSheet({
  open,
  onOpenChange,
  title,
  eyebrow,
  description,
  children,
  footer,
  triggerRef,
  initialFocusRef,
  className,
  contentClassName,
  dataSheet = 'generic',
}: MobileBottomSheetProps) {
  const sheetRef = useRef<HTMLDivElement>(null)
  const titleId = useId()
  const descriptionId = useId()
  const { close } = useMobileDialog({
    open,
    onOpenChange,
    containerRef: sheetRef,
    triggerRef,
    initialFocusRef,
  })

  if (!open) return null

  return createPortal(
    <div className="mobile-sheet-layer" data-mobile-sheet={dataSheet}>
      <button
        type="button"
        className="mobile-sheet-backdrop"
        aria-hidden="true"
        tabIndex={-1}
        onClick={close}
      />
      <div
        ref={sheetRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
        className={cn('mobile-bottom-sheet', className)}
      >
        <div aria-hidden="true" className="mobile-sheet-handle" />
        <header className="mobile-sheet-header">
          <div className="min-w-0">
            {eyebrow && <p className="mobile-sheet-eyebrow">{eyebrow}</p>}
            <h2 id={titleId} className="mobile-sheet-title">{title}</h2>
            {description && (
              <p id={descriptionId} className="mobile-sheet-description">{description}</p>
            )}
          </div>
          <button type="button" onClick={close} className="mobile-icon-button" aria-label={`关闭${title}`}>
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </header>
        <div className={cn('mobile-sheet-content', contentClassName)}>{children}</div>
        {footer && <footer className="mobile-sheet-footer">{footer}</footer>}
      </div>
    </div>,
    document.body,
  )
}
