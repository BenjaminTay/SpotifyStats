import { useCallback, useEffect, useRef, type RefObject } from 'react'

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

interface UseMobileDialogOptions {
  open: boolean
  onOpenChange: (open: boolean) => void
  containerRef: RefObject<HTMLElement | null>
  triggerRef?: RefObject<HTMLElement | null>
  initialFocusRef?: RefObject<HTMLElement | null>
}

export function useMobileDialog({
  open,
  onOpenChange,
  containerRef,
  triggerRef,
  initialFocusRef,
}: UseMobileDialogOptions) {
  const previousFocusRef = useRef<HTMLElement | null>(null)

  const close = useCallback(() => onOpenChange(false), [onOpenChange])

  useEffect(() => {
    if (!open) return

    previousFocusRef.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null
    const trigger = triggerRef?.current
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const frame = window.requestAnimationFrame(() => {
      const preferred = containerRef.current?.querySelector<HTMLElement>(
        '[data-mobile-autofocus="true"], [aria-current="page"]',
      )
      const fallback = preferred ?? containerRef.current?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR)
      ;(initialFocusRef?.current ?? fallback ?? containerRef.current)?.focus()
    })

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        close()
        return
      }
      if (event.key !== 'Tab' || !containerRef.current) return

      const focusable = Array.from(
        containerRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      ).filter((element) => element.getAttribute('aria-hidden') !== 'true')
      if (focusable.length === 0) {
        event.preventDefault()
        containerRef.current.focus()
        return
      }

      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && (document.activeElement === first || document.activeElement === containerRef.current)) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      window.cancelAnimationFrame(frame)
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKeyDown)
      window.requestAnimationFrame(() => {
        const target = trigger ?? previousFocusRef.current
        if (target?.isConnected) target.focus()
      })
    }
  }, [close, containerRef, initialFocusRef, open, triggerRef])

  return { close }
}
