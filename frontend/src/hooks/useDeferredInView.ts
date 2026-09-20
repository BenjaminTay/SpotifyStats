import { useCallback, useEffect, useState } from 'react'

// Observe the actual region; no device-specific delay or eager no-observer fallback.
export const DEFERRED_ROOT_MARGIN = '0px'
export function useDeferredInView(context: string) {
  const [node, setNode] = useState<HTMLElement | null>(null)
  const [seenContext, setSeenContext] = useState<string | null>(null)
  const ready = seenContext === context
  const ref = useCallback((element: HTMLElement | null) => setNode(element), [])
  useEffect(() => {
    if (!node || ready || typeof IntersectionObserver === 'undefined') return
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) {
        setSeenContext(context)
        observer.disconnect()
      }
    }, { rootMargin: DEFERRED_ROOT_MARGIN })
    observer.observe(node)
    return () => observer.disconnect()
  }, [node, context, ready])
  return { ref, ready }
}
