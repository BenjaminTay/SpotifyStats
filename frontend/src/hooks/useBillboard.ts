import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { api, type BillboardAllTimeResponse, type BillboardDataResponse, type BillboardRecordsResponse, type BillboardWeeklyResponse, type WeeklyTrackEntry, type WeeklyAlbumEntry, type WeeklyArtistEntry } from '@/lib/api'

let cachedBillboard: BillboardDataResponse | null = null
let cachedBillboardRequest: Promise<BillboardDataResponse> | null = null
let cachedWeekIndex = 0
let requestVersion = 0

export function loadBillboardData(force = false): Promise<BillboardDataResponse> {
  if (cachedBillboardRequest) return cachedBillboardRequest
  if (cachedBillboard && !force) return Promise.resolve(cachedBillboard)

  const version = ++requestVersion
  const request = api
    .get<BillboardDataResponse>('/billboard/data')
    .then((d) => {
      if (version === requestVersion) cachedBillboard = d
      return d
    })
    .finally(() => {
      if (cachedBillboardRequest === request) cachedBillboardRequest = null
    })

  cachedBillboardRequest = request
  return cachedBillboardRequest
}

export function preloadBillboardData(): void {
  void loadBillboardData().catch(() => {})
}

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
  goToWeek: (week: string) => void
}

export function useBillboard(initialWeek?: string | null): UseBillboardResult {
  const [data, setData] = useState<BillboardDataResponse | null>(cachedBillboard)
  const [loading, setLoading] = useState(!cachedBillboard)
  const [error, setError] = useState<string | null>(null)
  const [weekIndex, setWeekIndex] = useState(cachedWeekIndex)
  const initialWeekApplied = useRef(false)

  const fetchData = useCallback((force = false) => {
    setLoading(true)
    setError(null)
    loadBillboardData(force)
      .then((d) => {
        const shouldResetWeek = force || weekIndex >= d.meta.all_weeks_desc.length
        setData(d)
        if (shouldResetWeek) {
          cachedWeekIndex = 0
          setWeekIndex(0)
        }
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [weekIndex])

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

  const goToWeek = useCallback((week: string) => {
    const idx = allWeeks.indexOf(week)
    if (idx >= 0) {
      setWeekIndex(idx)
      cachedWeekIndex = idx
    }
  }, [allWeeks])

  return {
    data,
    loading,
    error,
    refetch: () => fetchData(true),
    selectedWeek,
    currentWeekData,
    currentIndex: weekIndex,
    totalWeeks,
    goNext,
    goPrev,
    goToWeek,
  }
}

// ── Split-endpoint hooks (Phase 4B-1) ─────────────────────────────────────

let cachedWeekly: BillboardWeeklyResponse | null = null
let cachedWeeklyRequest: Promise<BillboardWeeklyResponse> | null = null
let wWeeklyRequestVersion = 0
let cachedWeeklyIndex = 0

function loadWeeklyData(force = false): Promise<BillboardWeeklyResponse> {
  if (cachedWeeklyRequest) return cachedWeeklyRequest
  if (cachedWeekly && !force) return Promise.resolve(cachedWeekly)

  const version = ++wWeeklyRequestVersion
  const request = api
    .get<BillboardWeeklyResponse>('/billboard/weekly')
    .then((d) => {
      if (version === wWeeklyRequestVersion) cachedWeekly = d
      return d
    })
    .finally(() => {
      if (cachedWeeklyRequest === request) cachedWeeklyRequest = null
    })

  cachedWeeklyRequest = request
  return cachedWeeklyRequest
}

export function preloadWeeklyData(): void {
  void loadWeeklyData().catch(() => {})
}

export function useBillboardWeekly(initialWeek?: string | null) {
  const [data, setData] = useState<BillboardWeeklyResponse | null>(cachedWeekly)
  const [loading, setLoading] = useState(!cachedWeekly)
  const [error, setError] = useState<string | null>(null)
  const [weekIndex, setWeekIndex] = useState(cachedWeeklyIndex)
  const initialWeekApplied = useRef(false)

  const fetchData = useCallback((force = false) => {
    setLoading(true)
    setError(null)
    loadWeeklyData(force)
      .then((d) => {
        const shouldResetWeek = force || weekIndex >= d.meta.all_weeks_desc.length
        setData(d)
        if (shouldResetWeek) {
          cachedWeeklyIndex = 0
          setWeekIndex(0)
        }
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [weekIndex])

  useEffect(() => {
    if (!cachedWeekly) fetchData()
  }, [fetchData])

  const allWeeks = data?.meta.all_weeks_desc ?? []
  const totalWeeks = allWeeks.length
  const selectedWeek = allWeeks[weekIndex] ?? ''

  useEffect(() => {
    if (initialWeek && data && !initialWeekApplied.current && allWeeks.length > 0) {
      const idx = allWeeks.indexOf(initialWeek)
      if (idx >= 0) {
        setWeekIndex(idx)
        cachedWeeklyIndex = idx
      }
      initialWeekApplied.current = true
    }
  }, [initialWeek, data, allWeeks])

  useEffect(() => {
    initialWeekApplied.current = false
  }, [initialWeek])

  const currentWeekData = useMemo(() => {
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
      cachedWeeklyIndex = next
      return next
    })
  }, [])

  const goPrev = useCallback(() => {
    setWeekIndex((prev) => {
      const next = Math.min(totalWeeks - 1, prev + 1)
      cachedWeeklyIndex = next
      return next
    })
  }, [totalWeeks])

  const goToWeek = useCallback((week: string) => {
    const idx = allWeeks.indexOf(week)
    if (idx >= 0) {
      setWeekIndex(idx)
      cachedWeeklyIndex = idx
    }
  }, [allWeeks])

  return {
    data,
    loading,
    error,
    refetch: () => fetchData(true),
    selectedWeek,
    currentWeekData,
    currentIndex: weekIndex,
    totalWeeks,
    goNext,
    goPrev,
    goToWeek,
  }
}

// ── Records hook ────────────────────────────────────────────────────────────

let cachedRecords: BillboardRecordsResponse | null = null
let cachedRecordsRequest: Promise<BillboardRecordsResponse> | null = null
let wRecordsRequestVersion = 0

function loadRecordsData(force = false): Promise<BillboardRecordsResponse> {
  if (cachedRecordsRequest) return cachedRecordsRequest
  if (cachedRecords && !force) return Promise.resolve(cachedRecords)

  const version = ++wRecordsRequestVersion
  const request = api
    .get<BillboardRecordsResponse>('/billboard/records')
    .then((d) => {
      if (version === wRecordsRequestVersion) cachedRecords = d
      return d
    })
    .finally(() => {
      if (cachedRecordsRequest === request) cachedRecordsRequest = null
    })

  cachedRecordsRequest = request
  return cachedRecordsRequest
}

export function preloadRecordsData(): void {
  void loadRecordsData().catch(() => {})
}

export function useBillboardRecords() {
  const [data, setData] = useState<BillboardRecordsResponse | null>(cachedRecords)
  const [loading, setLoading] = useState(!cachedRecords)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback((force = false) => {
    setLoading(true)
    setError(null)
    loadRecordsData(force)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!cachedRecords) fetchData()
  }, [fetchData])

  return { data: data?.records ?? null, loading, error, refetch: () => fetchData(true) }
}

// ── All-Time hook (NumberOnesPage + AllTimeChartsPage) ──────────────────────

let cachedAllTime: BillboardAllTimeResponse | null = null
let cachedAllTimeRequest: Promise<BillboardAllTimeResponse> | null = null
let wAllTimeRequestVersion = 0

function loadAllTimeData(force = false): Promise<BillboardAllTimeResponse> {
  if (cachedAllTimeRequest) return cachedAllTimeRequest
  if (cachedAllTime && !force) return Promise.resolve(cachedAllTime)

  const version = ++wAllTimeRequestVersion
  const request = api
    .get<BillboardAllTimeResponse>('/billboard/all-time')
    .then((d) => {
      if (version === wAllTimeRequestVersion) cachedAllTime = d
      return d
    })
    .finally(() => {
      if (cachedAllTimeRequest === request) cachedAllTimeRequest = null
    })

  cachedAllTimeRequest = request
  return cachedAllTimeRequest
}

export function preloadAllTimeData(): void {
  void loadAllTimeData().catch(() => {})
}

export function useBillboardAllTime() {
  const [data, setData] = useState<BillboardAllTimeResponse | null>(cachedAllTime)
  const [loading, setLoading] = useState(!cachedAllTime)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback((force = false) => {
    setLoading(true)
    setError(null)
    loadAllTimeData(force)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!cachedAllTime) fetchData()
  }, [fetchData])

  return { data, loading, error, refetch: () => fetchData(true) }
}
