import { useState, useEffect } from 'react'

type Breakpoint = 'sm' | 'md' | 'lg' | 'xl' | '2xl'

function getBreakpoint(): Breakpoint {
  const width = window.innerWidth
  if (width >= 1536) return '2xl'
  if (width >= 1280) return 'xl'
  if (width >= 1024) return 'lg'
  if (width >= 768) return 'md'
  return 'sm'
}

export function useBreakpoint(): Breakpoint {
  const [bp, setBp] = useState<Breakpoint>(getBreakpoint)

  useEffect(() => {
    const handler = () => setBp(getBreakpoint())
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])

  return bp
}

/** True when viewport < 768px (mobile / narrow). */
export function useIsMobile(): boolean {
  const bp = useBreakpoint()
  return bp === 'sm'
}

/** True when viewport >= 1024px (desktop). */
export function useIsDesktop(): boolean {
  const bp = useBreakpoint()
  return bp === 'lg' || bp === 'xl' || bp === '2xl'
}
