import { useState, useEffect, useCallback } from 'react'
import { api, type DashboardFullResponse } from '@/lib/api'

interface UseDashboardResult {
  data: DashboardFullResponse | null
  loading: boolean
  error: string | null
  refetch: () => void
}

let cachedData: DashboardFullResponse | null = null
let cachedRequest: Promise<DashboardFullResponse> | null = null
let requestVersion = 0

export function loadDashboardData(force = false): Promise<DashboardFullResponse> {
  if (cachedRequest) return cachedRequest
  if (cachedData && !force) return Promise.resolve(cachedData)

  const version = ++requestVersion
  const request = api
    .get<DashboardFullResponse>('/dashboard/full')
    .then((d) => {
      if (version === requestVersion) cachedData = d
      return d
    })
    .finally(() => {
      if (cachedRequest === request) cachedRequest = null
    })

  cachedRequest = request
  return cachedRequest
}

export function preloadDashboardData(): void {
  void loadDashboardData().catch(() => {})
}

export function useDashboard(): UseDashboardResult {
  const [data, setData] = useState<DashboardFullResponse | null>(cachedData)
  const [loading, setLoading] = useState(!cachedData)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback((force = false) => {
    setLoading(true)
    setError(null)
    loadDashboardData(force)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!cachedData) {
      fetchData()
    }
  }, [fetchData])

  return { data, loading, error, refetch: () => fetchData(true) }
}
