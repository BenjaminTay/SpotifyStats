import { useEffect, useRef, useState } from 'react'

export function useArchiveSection(preload = false) {
  const ref = useRef<HTMLElement | null>(null)
  const [enabled, setEnabled] = useState(
    () => preload || typeof IntersectionObserver === 'undefined',
  )

  useEffect(() => {
    if (enabled || typeof IntersectionObserver === 'undefined') return
    const node = ref.current
    if (!node) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setEnabled(true)
          observer.disconnect()
        }
      },
      { rootMargin: '640px 0px', threshold: 0 },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [enabled])

  return { ref, enabled }
}
