import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { api, type BillboardDataResponse, type WeeklyTrackEntry, type WeeklyAlbumEntry, type WeeklyArtistEntry } from '@/lib/api'

let cachedBillboard: BillboardDataResponse | null = null
let cachedWeekIndex = 0

interface CurrentWeekData {
  tracks: WeeklyTrackEntry[]
  albums: WeeklyAlbumEntry[]
  artists: WeeklyArtistEntry[]
}

interface UseBillboardResult {
  data: BillboardDataResponse | null
  loading: boolean
  error: string | null
  refetch: () => void
  selectedWeek: string
  currentWeekData: CurrentWeekData
  currentIndex: number
  totalWeeks: number
  goNext: () => void
  goPrev: () => void
}

export function useBillboard(initialWeek?: string | null): UseBillboardResult {
  const [data, setData] = useState<BillboardDataResponse | null>(cachedBillboard)
  const [loading, setLoading] = useState(!cachedBillboard)
  const [error, setError] = useState<string | null>(null)
  const [weekIndex, setWeekIndex] = useState(cachedWeekIndex)
  const initialWeekApplied = useRef(false)

  const fetchData = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .get<BillboardDataResponse>('/billboard/data')
      .then((d) => {
        const isFirstLoad = !cachedBillboard
        cachedBillboard = d
        setData(d)
        if (isFirstLoad) setWeekIndex(0)
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!cachedBillboard) {
      fetchData()
    }
  }, [fetchData])

  const allWeeks = data?.meta.all_weeks_desc ?? []
  const totalWeeks = allWeeks.length
  const selectedWeek = allWeeks[weekIndex] ?? ''

  // Apply initialWeek from URL param once data is available
  useEffect(() => {
    if (initialWeek && data && !initialWeekApplied.current && allWeeks.length > 0) {
      const idx = allWeeks.indexOf(initialWeek)
      if (idx >= 0) {
        setWeekIndex(idx)
        cachedWeekIndex = idx
      }
      initialWeekApplied.current = true
    }
  }, [initialWeek, data, allWeeks])

  // Reset the ref when initialWeek changes
  useEffect(() => {
    initialWeekApplied.current = false
  }, [initialWeek])

  const currentWeekData = useMemo<CurrentWeekData>(() => {
    if (!data) return { tracks: [], albums: [], artists: [] }
    return {
      tracks: data.weekly.filter((w) => w.billboard_week === selectedWeek).sort((a, b) => a.rank - b.rank),
      albums: data.weekly_album.filter((w) => w.billboard_week === selectedWeek).sort((a, b) => a.rank - b.rank),
      artists: data.weekly_artist.filter((w) => w.billboard_week === selectedWeek).sort((a, b) => a.rank - b.rank),
    }
  }, [data, selectedWeek])

  const goNext = useCallback(() => {
    setWeekIndex((prev) => {
      const next = Math.max(0, prev - 1)
      cachedWeekIndex = next
      return next
    })
  }, [])

  const goPrev = useCallback(() => {
    setWeekIndex((prev) => {
      const next = Math.min(totalWeeks - 1, prev + 1)
      cachedWeekIndex = next
      return next
    })
  }, [totalWeeks])

  return {
    data,
    loading,
    error,
    refetch: fetchData,
    selectedWeek,
    currentWeekData,
    currentIndex: weekIndex,
    totalWeeks,
    goNext,
    goPrev,
  }
}
