import { useState, useEffect, useCallback } from 'react'
import { api, type AccountSummary } from '@/lib/api'

let cachedData: AccountSummary | null = null
let inFlight: Promise<AccountSummary> | null = null

interface UseAccountResult {
  data: AccountSummary | null
  loading: boolean
  error: string | null
  refetch: () => void
}

export function useAccount(): UseAccountResult {
  const [data, setData] = useState<AccountSummary | null>(cachedData)
  const [loading, setLoading] = useState(!cachedData)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(() => {
    setLoading(true)
    setError(null)

    if (inFlight) {
      inFlight
        .then((result) => {
          cachedData = result
          setData(result)
          setLoading(false)
        })
        .catch((e: Error) => {
          setError(e.message)
          setLoading(false)
        })
      return
    }

    const promise = api.get<AccountSummary>('/account')
    inFlight = promise

    promise
      .then((result) => {
        cachedData = result
        if (inFlight === promise) {
          setData(result)
          setError(null)
        }
      })
      .catch((e: Error) => {
        if (inFlight === promise) {
          setError(e.message)
        }
      })
      .finally(() => {
        if (inFlight === promise) {
          inFlight = null
          setLoading(false)
        }
      })
  }, [])

  useEffect(() => {
    if (!cachedData) {
      refetch()
    }
  }, [refetch])

  return { data, loading, error, refetch }
}

/** Prefetch account data (for Masthead hover or layout preload). Does not trigger re-renders. */
export function prefetchAccount(): void {
  if (cachedData || inFlight) return
  const promise = api.get<AccountSummary>('/account')
  inFlight = promise
  promise
    .then((result) => {
      cachedData = result
    })
    .catch(() => {
      // prefetch failure is silent
    })
    .finally(() => {
      inFlight = null
    })
}
