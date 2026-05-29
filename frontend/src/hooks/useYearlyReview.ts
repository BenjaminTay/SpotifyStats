import { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import type { WrappedFullResponse } from '@/types/yearly-review'

// Module-level cache: year → response
const fullCache = new Map<number, WrappedFullResponse>()
// In-flight request deduplication: year → Promise
const inFlight = new Map<number, Promise<WrappedFullResponse>>()

/** Pre-fetch a year's data into the module cache. Safe to call multiple times. */
export async function prefetchYearlyReview(year: number): Promise<void> {
  if (fullCache.has(year) || inFlight.has(year)) return

  const promise = api.get<WrappedFullResponse>(`/wrapped/${year}/full`)
  inFlight.set(year, promise)

  try {
    const result = await promise
    fullCache.set(year, result)
  } catch {
    // Silently fail — the hook will retry on demand
  } finally {
    inFlight.delete(year)
  }
}

export function useYearlyReview(year: number) {
  const [data, setData] = useState<WrappedFullResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Skip fetch for invalid years
    if (year <= 0) {
      setData(null)
      setError(null)
      setLoading(false)
      return
    }

    let cancelled = false
    setData(null)
    setError(null)

    async function load() {
      // 1. Check module-level cache
      const cached = fullCache.get(year)
      if (cached) {
        if (!cancelled) {
          setData(cached)
          setLoading(false)
        }
        return
      }

      // 2. Deduplicate in-flight requests
      const existing = inFlight.get(year)
      if (existing) {
        setLoading(true)
        try {
          const result = await existing
          if (!cancelled) {
            setData(result)
            setLoading(false)
          }
        } catch {
          if (!cancelled) {
            setError('Failed to load yearly review')
            setLoading(false)
          }
        }
        return
      }

      setLoading(true)
      setError(null)

      // 3. Initiate new request
      const promise = api.get<WrappedFullResponse>(`/wrapped/${year}/full`)
      inFlight.set(year, promise)

      try {
        const result = await promise
        fullCache.set(year, result)
        if (!cancelled) {
          setData(result)
          setLoading(false)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load yearly review')
          setLoading(false)
        }
      } finally {
        inFlight.delete(year)
      }
    }

    load()

    return () => {
      cancelled = true
    }
  }, [year])

  return { data, loading, error }
}
