import { useState, useEffect, useCallback, useMemo } from 'react'
import { api, type BillboardDataResponse, type WeeklyTrackEntry, type WeeklyAlbumEntry, type WeeklyArtistEntry } from '@/lib/api'

let cachedBillboard: BillboardDataResponse | null = null

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

export function useBillboard(): UseBillboardResult {
  const [data, setData] = useState<BillboardDataResponse | null>(cachedBillboard)
  const [loading, setLoading] = useState(!cachedBillboard)
  const [error, setError] = useState<string | null>(null)
  const [weekIndex, setWeekIndex] = useState(0)

  const fetchData = useCallback(() => {
    setLoading(true)
    setError(null)
    api
      .get<BillboardDataResponse>('/billboard/data')
      .then((d) => {
        cachedBillboard = d
        setData(d)
        setWeekIndex(0)
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

  const currentWeekData = useMemo<CurrentWeekData>(() => {
    if (!data) return { tracks: [], albums: [], artists: [] }
    return {
      tracks: data.weekly.filter((w) => w.billboard_week === selectedWeek).sort((a, b) => a.rank - b.rank),
      albums: data.weekly_album.filter((w) => w.billboard_week === selectedWeek).sort((a, b) => a.rank - b.rank),
      artists: data.weekly_artist.filter((w) => w.billboard_week === selectedWeek).sort((a, b) => a.rank - b.rank),
    }
  }, [data, selectedWeek])

  const goNext = useCallback(() => {
    setWeekIndex((prev) => Math.max(0, prev - 1))
  }, [])

  const goPrev = useCallback(() => {
    setWeekIndex((prev) => Math.min(totalWeeks - 1, prev + 1))
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
