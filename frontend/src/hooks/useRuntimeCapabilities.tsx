import { createContext, useContext, useMemo, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'

export interface RuntimeCapabilities {
  surface: 'private-admin' | 'public-readonly'
  settings: boolean
  editing: boolean
  imports: boolean
  ai: boolean
  spotify_oauth: boolean
  lyrics: boolean
}

interface RuntimeCapabilitiesContextValue {
  capabilities: RuntimeCapabilities
  loading: boolean
}

const PRIVATE_CAPABILITIES: RuntimeCapabilities = {
  surface: 'private-admin',
  settings: true,
  editing: true,
  imports: true,
  ai: true,
  spotify_oauth: true,
  lyrics: true,
}

const PUBLIC_CAPABILITIES: RuntimeCapabilities = {
  surface: 'public-readonly',
  settings: false,
  editing: false,
  imports: false,
  ai: false,
  spotify_oauth: false,
  lyrics: false,
}

const RuntimeCapabilitiesContext = createContext<RuntimeCapabilitiesContextValue>({
  capabilities: PRIVATE_CAPABILITIES,
  loading: false,
})

export function RuntimeCapabilitiesProvider({ children }: { children: ReactNode }) {
  const query = useQuery({
    queryKey: ['runtime', 'capabilities'],
    queryFn: () => api.get<RuntimeCapabilities>('/runtime/capabilities'),
    staleTime: Number.POSITIVE_INFINITY,
    retry: 1,
  })
  const value = useMemo<RuntimeCapabilitiesContextValue>(() => ({
    // Fail closed for the presentation layer. The backend policy remains the
    // authoritative boundary if this discovery request fails.
    capabilities: query.data ?? PUBLIC_CAPABILITIES,
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
