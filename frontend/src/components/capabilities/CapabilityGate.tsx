import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import {
  hasRuntimeCapabilities,
  type RuntimeCapability,
} from '@/hooks/runtimeCapabilities'
import { useRuntimeCapabilities } from '@/hooks/useRuntimeCapabilities'

interface CapabilityGateProps {
  require: RuntimeCapability | readonly RuntimeCapability[]
  children: ReactNode
  fallback?: ReactNode
}

/** Presentation-only guard. The backend remains the authoritative boundary. */
export function CapabilityGate({ require, children, fallback = null }: CapabilityGateProps) {
  const { capabilities } = useRuntimeCapabilities()
  return hasRuntimeCapabilities(capabilities, require) ? children : fallback
}

interface CapabilityRouteProps extends CapabilityGateProps {
  redirectTo?: string
  loadingFallback?: ReactNode
}

/**
 * Blocks the route before its lazy page mounts, so disabled pages cannot start
 * settings, AI, import or metadata requests during capability discovery.
 */
export function CapabilityRoute({
  require,
  children,
  redirectTo = '/',
  loadingFallback = null,
}: CapabilityRouteProps) {
  const { capabilities, loading } = useRuntimeCapabilities()
  const location = useLocation()
  if (loading) return loadingFallback
  if (!hasRuntimeCapabilities(capabilities, require)) {
    return <Navigate to={redirectTo} replace state={{ blockedFrom: `${location.pathname}${location.search}` }} />
  }
  return children
}
