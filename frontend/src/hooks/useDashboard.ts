import { useState, useEffect, useCallback } from 'react'
import { api, type DashboardFullResponse } from '@/lib/api'

interface UseDashboardResult {
  data: DashboardFullResponse | null
  loading: boolean
  error: string | null
  refetch: () => void
}

let cachedData: DashboardFullResponse | null = null

export function useDashboard(): UseDashboardResult {
  const [data, setData] = useState<DashboardFullResponse | null>(cachedData)
  const [loading, setLoading] = useState(!cachedData)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .get<DashboardFullResponse>('/dashboard/full')
      .then((d) => {
        cachedData = d
        setData(d)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!cachedData) {
      fetchData()
    }
  }, [fetchData])

  return { data, loading, error, refetch: fetchData }
}
