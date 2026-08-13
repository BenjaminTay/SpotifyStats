import { createContext, useContext, useMemo, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'
import {
  FULL_CAPABILITIES,
  normalizeRuntimeCapabilities,
  type RuntimeCapabilities,
} from '@/hooks/runtimeCapabilities'

interface RuntimeCapabilitiesContextValue {
  capabilities: RuntimeCapabilities
  loading: boolean
}

const RuntimeCapabilitiesContext = createContext<RuntimeCapabilitiesContextValue>({
  // App production always mounts the provider. This default supports isolated
  // component stories/tests; discovery failures inside the provider still
  // normalize to the fail-closed public profile.
  capabilities: FULL_CAPABILITIES,
  loading: false,
})

export function RuntimeCapabilitiesProvider({ children }: { children: ReactNode }) {
  const query = useQuery({
    queryKey: ['runtime', 'capabilities'],
    queryFn: () => api.get<unknown>('/runtime/capabilities'),
    staleTime: Number.POSITIVE_INFINITY,
    retry: 1,
  })
  const value = useMemo<RuntimeCapabilitiesContextValue>(() => ({
    // Fail closed for the presentation layer. The backend policy remains the
    // authoritative boundary if this discovery request fails.
    capabilities: normalizeRuntimeCapabilities(query.data),
    loading: query.isLoading,
  }), [query.data, query.isLoading])

  return (
    <RuntimeCapabilitiesContext.Provider value={value}>
      {children}
    </RuntimeCapabilitiesContext.Provider>
  )
}

export function useRuntimeCapabilities(): RuntimeCapabilitiesContextValue {
  return useContext(RuntimeCapabilitiesContext)
}
