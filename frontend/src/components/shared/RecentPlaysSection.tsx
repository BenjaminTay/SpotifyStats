import { useState, useMemo, useRef, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, ChevronLeft, ChevronRight, Search, CalendarIcon, X } from 'lucide-react'
import { format, parseISO } from 'date-fns'
import { ArtistLinks } from '@/components/shared/ArtistLinks'
import { CoverCell } from '@/components/shared/CoverCell'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Calendar } from '@/components/ui/calendar'
import { cn } from '@/lib/utils'
import { displayName } from '@/lib/chinese'
import type { RecentPlayRow, EntityPlaysResponse, AnalysisFilters, AnalysisPeriod } from '@/types/analysis'
import { MobileEntityRow, MobilePagination, MobileStatePanel } from '@/components/mobile'
import { recentPlayRowKey } from './recentPlaysUtils'

const PAGE_SIZE = 50
const EMPTY_RECENT_ROWS: RecentPlayRow[] = []

function formatMinutes(n: number): string {
  const totalSec = Math.round(n * 3600)
  const m = Math.floor(totalSec / 60)
  const s = totalSec % 60
  return `${m}m${s}s`
}

function formatTime(ts: string): string {
  // ts is stored as UTC ISO string, display as Beijing time (UTC+8)
  const date = new Date(ts)
  const beijing = new Date(date.getTime() + 8 * 60 * 60 * 1000)
  return `${String(beijing.getUTCHours()).padStart(2, '0')}:${String(beijing.getUTCMinutes()).padStart(2, '0')}`
}

function formatDateLabel(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 ${weekdays[d.getDay()]}`
}

type SortKey = 'ts' | 'ms_played'

interface PlayDateEntry {
  date: string
  count: number
}

interface RecentPlaysSectionProps {
  kind: 'track' | 'album' | 'artist' | 'global'
  entityId?: string
  artistName?: string
  filters: AnalysisFilters
  apiParams: { period: AnalysisPeriod; start_date?: string; end_date?: string }
  fetchPage: (page: number, limit: number, search?: string, date?: string) => Promise<EntityPlaysResponse>
  fetchPlayDates: () => Promise<PlayDateEntry[]>
  mobile?: boolean
}

export function RecentPlaysSection(props: RecentPlaysSectionProps) {
  return <RecentPlaysContent key={JSON.stringify(props.apiParams)} {...props} />
}

function RecentPlaysContent({
  apiParams,
  fetchPage,
  fetchPlayDates,
  mobile = false,
}: RecentPlaysSectionProps) {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [sortKey, setSortKey] = useState<SortKey | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [expandedState, setExpandedState] = useState<{ rows: RecentPlayRow[]; dates: Set<string> }>({
    rows: [],
    dates: new Set(),
  })
  const [calendarOpen, setCalendarOpen] = useState(false)
  const [playDates, setPlayDates] = useState<PlayDateEntry[]>([])
  const abortRef = useRef(0)

  const paramsKey = JSON.stringify(apiParams)
  const requestKey = `${paramsKey}:${page}:${debouncedSearch}:${selectedDate ?? ''}`
  const [resultState, setResultState] = useState<{
    key: string
    rows: RecentPlayRow[]
    total: number
  }>({ key: '', rows: [], total: 0 })
  const isCurrentResult = resultState.key === requestKey
  const rows = isCurrentResult ? resultState.rows : EMPTY_RECENT_ROWS
  const total = isCurrentResult ? resultState.total : 0
  const loading = !isCurrentResult
  const defaultExpandedDates = useMemo(() => new Set(rows.map((row) => row.date)), [rows])
  const expandedDates = expandedState.rows === rows ? expandedState.dates : defaultExpandedDates

  // Fetch play dates
  useEffect(() => {
    let active = true
    fetchPlayDates().then((dates) => {
      if (active) setPlayDates(dates)
    })
    return () => { active = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey])

  // Fetch page data
  useEffect(() => {
    let active = true
    const token = ++abortRef.current
    fetchPage(page, PAGE_SIZE, debouncedSearch || undefined, selectedDate || undefined).then((result) => {
      if (!active || token !== abortRef.current) return
      setResultState({ key: requestKey, rows: result.rows, total: result.total })
    }).catch(() => {
      if (!active || token !== abortRef.current) return
      setResultState({ key: requestKey, rows: [], total: 0 })
    })
    return () => { active = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestKey])

  // Debounced search
  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => {
      setDebouncedSearch(search)
      setPage(1)
    }, 300)
    return () => {
      if (searchTimer.current) clearTimeout(searchTimer.current)
    }
  }, [search])

  const toggleDate = (date: string) => {
    setExpandedState(() => {
      const next = new Set(expandedDates)
      if (next.has(date)) next.delete(date)
      else next.add(date)
      return { rows, dates: next }
    })
  }

  // Sort — client-side within current page
  const sortedGroups = useMemo(() => {
    const sorted = [...rows]
    if (sortKey) {
      sorted.sort((a, b) => {
        const aVal = sortKey === 'ts' ? a.ts : a.ms_played
        const bVal = sortKey === 'ts' ? b.ts : b.ms_played
        return sortDir === 'desc' ? (bVal > aVal ? 1 : -1) : (aVal > bVal ? 1 : -1)
      })
    }
    const groups: { date: string; rows: RecentPlayRow[] }[] = []
    for (const row of sorted) {
      const last = groups[groups.length - 1]
      if (last && last.date === row.date) {
        last.rows.push(row)
      } else {
        groups.push({ date: row.date, rows: [row] })
      }
    }
    return groups
  }, [rows, sortKey, sortDir])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const isFiltering = debouncedSearch !== '' || selectedDate !== null

  const sortArrow = (key: SortKey) => {
    if (sortKey !== key) return null
    return sortDir === 'desc' ? ' ▼' : ' ▲'
  }

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      if (sortDir === 'desc') setSortDir('asc')
      else {
        setSortKey(null)
        setSortDir('desc')
      }
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const handleDateSelect = useCallback((day: Date) => {
    setSelectedDate(format(day, 'yyyy-MM-dd'))
    setCalendarOpen(false)
    setPage(1)
  }, [])

  const handleClearDate = useCallback(() => {
    setSelectedDate(null)
    setPage(1)
  }, [])

  const calendarDates = useMemo(() => playDates.map((d) => parseISO(d.date)), [playDates])

  return (
    <div className="space-y-4">
      {/* Toolbar: Search + Calendar */}
      <div className={cn('flex items-center gap-2', mobile && 'mobile-recent-toolbar')}>
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索歌曲、艺人或专辑..."
            className={cn(
              'w-full rounded-lg border border-border bg-background py-1.5 pl-9 pr-3 font-sans text-[13px] placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-accent-foreground/20',
              mobile && 'min-h-11 rounded-xl',
            )}
          />
        </div>
        <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
          <PopoverTrigger asChild>
            <button
              className={cn(
                'flex shrink-0 items-center gap-1.5 rounded-lg border border-border bg-background px-2.5 py-1.5 cursor-pointer transition-colors hover:border-foreground/20',
                mobile && 'min-h-11 rounded-xl',
                selectedDate && 'border-accent-foreground/40 bg-accent-foreground/5',
              )}
            >
              <CalendarIcon className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="font-sans text-[12px] tabular-nums text-muted-foreground">
                {selectedDate || '日历'}
              </span>
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0 bg-card/80 backdrop-blur-xl border-border/60 shadow-xl" side="bottom" align="end" sideOffset={8}>
            <Calendar
              month={selectedDate ? parseISO(selectedDate) : undefined}
              endMonth={new Date()}
              modifiers={{ hasPlays: calendarDates }}
              modifiersClassNames={{ hasPlays: 'has-plays' }}
              onDayClick={handleDateSelect}
              footer="点击日期查看当天记录"
            />
          </PopoverContent>
        </Popover>
        {selectedDate && (
          <button
            onClick={handleClearDate}
            className="flex shrink-0 items-center gap-1 rounded-[6px] px-2 py-1 font-sans text-[12px] text-muted-foreground cursor-pointer transition-colors hover:bg-muted hover:text-foreground"
          >
            <X className="h-3 w-3" />
            清除
          </button>
        )}
      </div>

      {/* Sort controls / desktop table header */}
      <div className={cn(
        'flex items-center border-b border-border pb-2 font-sans text-[11px] uppercase tracking-[1px] text-muted-foreground',
        mobile && 'mobile-recent-sort',
      )}>
        <button
          onClick={() => handleSort('ts')}
          className={cn(
            'w-[90px] cursor-pointer text-left transition-colors hover:text-foreground',
            sortKey === 'ts' && 'font-semibold text-foreground',
          )}
        >
          播放时间{sortArrow('ts')}
        </button>
        {!mobile && <span className="flex-1 pl-4">歌曲</span>}
        {!mobile && <span className="flex-1 pl-4">专辑</span>}
        <button
          onClick={() => handleSort('ms_played')}
          className={cn(
            'w-[60px] cursor-pointer text-right transition-colors hover:text-foreground',
            sortKey === 'ms_played' && 'font-semibold text-foreground',
          )}
        >
          时长{sortArrow('ms_played')}
        </button>
      </div>

      {/* Content */}
      {loading ? (
        mobile ? <MobileStatePanel variant="loading" compact /> : <p className="py-10 text-center font-sans text-[13px] text-muted-foreground">加载中...</p>
      ) : sortedGroups.length === 0 ? (
        mobile
          ? <MobileStatePanel variant="empty" compact title={isFiltering ? '无匹配的播放记录' : '暂无播放记录'} />
          : <p className="py-10 text-center font-sans text-[13px] text-muted-foreground">{isFiltering ? '无匹配的播放记录' : '暂无播放记录'}</p>
      ) : (
        <div className="space-y-1">
          {sortedGroups.map((group) => (
            <div key={group.date}>
              <button
                onClick={() => toggleDate(group.date)}
                className={cn(
                  'flex w-full items-center gap-2 rounded-[6px] px-2 py-1.5 cursor-pointer transition-colors hover:bg-muted/50',
                  mobile && 'mobile-recent-group-trigger',
                )}
              >
                {expandedDates.has(group.date) ? (
                  <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                )}
                <span className="font-sans text-[13px] font-semibold">{formatDateLabel(group.date)}</span>
                <span className="font-sans text-[12px] text-muted-foreground">{group.rows.length} 次</span>
              </button>

              {expandedDates.has(group.date) && (
                mobile ? (
                  <div className="mobile-recent-rows">
                    {group.rows.map((row, rowIndex) => (
                      <MobileEntityRow
                        key={recentPlayRowKey(row, rowIndex)}
                        entityType="track"
                        title={displayName(row.track_name)}
                        subtitle={displayName((row.artist_names?.length ? row.artist_names.join('、') : row.artist_name) || '未知艺人')}
                        coverUrl={row.cover_url}
                        metric={formatTime(row.ts)}
                        metricLabel="播放时间"
                        facts={[
                          { label: '专辑', value: displayName(row.album_name || '—') },
                          { label: '时长', value: formatMinutes(row.hours) },
                        ]}
                        badges={row.platform ? [row.platform] : []}
                        to={row.track_id ? `/music/tracks/${row.track_id}` : undefined}
                      />
                    ))}
                  </div>
                ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[660px] table-fixed border-collapse text-left font-sans text-[13px]">
                    <tbody>
                      {group.rows.map((row, rowIndex) => (
                        <tr key={recentPlayRowKey(row, rowIndex)} className="border-b border-border/40">
                          <td className="w-[90px] py-2.5 tabular-nums text-muted-foreground">
                            {formatTime(row.ts)}
                          </td>
                          <td className="py-2.5 pr-3">
                            <span className="flex items-start gap-3 min-w-0">
                              <Link
                                to={row.track_id ? `/music/tracks/${row.track_id}` : '#'}
                                className="shrink-0"
                              >
                                <CoverCell index={0} coverUrl={row.cover_url} label={displayName(row.track_name)} />
                              </Link>
                              <span className="min-w-0">
                                <Link
                                  to={row.track_id ? `/music/tracks/${row.track_id}` : '#'}
                                  className="block truncate font-semibold transition-colors hover:text-accent-foreground"
                                >
                                  {displayName(row.track_name)}
                                </Link>
                                <ArtistLinks
                                  artistName={row.artist_name}
                                  artistNames={row.artist_names}
                                  className="block truncate text-[12px] italic text-muted-foreground"
                                />
                              </span>
                            </span>
                          </td>
                          <td className="py-2.5 pr-3">
                            <span className="min-w-0">
                              <Link
                                to={
                                  row.album_name
                                    ? `/music/albums/${encodeURIComponent(row.album_name)}${row.artist_name ? `?artist=${encodeURIComponent(row.artist_name)}` : ''}`
                                    : '#'
                                }
                                className="block truncate font-semibold text-muted-foreground transition-colors hover:text-accent-foreground"
                              >
                                {displayName(row.album_name || '—')}
                              </Link>
                              <Link
                                to={
                                  row.artist_name
                                    ? `/music/artists/${encodeURIComponent(row.artist_name)}`
                                    : '#'
                                }
                                className="block truncate text-[12px] italic text-muted-foreground transition-colors hover:text-accent-foreground"
                              >
                                {displayName(row.artist_name || '')}
                              </Link>
                            </span>
                          </td>
                          <td className="w-[60px] py-2.5 text-right tabular-nums font-semibold">
                            {formatMinutes(row.hours)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                )
              )}
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {mobile ? (
        <MobilePagination
          page={page}
          pageCount={totalPages}
          totalLabel={`共 ${total} 条`}
          loading={loading}
          onPageChange={setPage}
        />
      ) : (
      <div className="flex items-center justify-between pt-2">
        <span className="font-sans text-[12px] text-muted-foreground tabular-nums">
          共 {total} 条，第 {page}/{totalPages} 页
        </span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-label="上一页"
            disabled={page <= 1 || loading}
            onClick={() => setPage((p) => p - 1)}
            className={cn(
              'rounded-[6px] p-1.5 cursor-pointer transition-colors text-muted-foreground hover:bg-muted hover:text-foreground',
              (page <= 1 || loading) && 'opacity-30 cursor-not-allowed',
            )}
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          </button>
          {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
            let pageNum: number
            if (totalPages <= 7) {
              pageNum = i + 1
            } else if (page <= 4) {
              pageNum = i + 1
            } else if (page >= totalPages - 3) {
              pageNum = totalPages - 6 + i
            } else {
              pageNum = page - 3 + i
            }
            return (
              <button
                key={pageNum}
                disabled={loading}
                onClick={() => setPage(pageNum)}
                className={cn(
                  'min-w-[28px] rounded-[6px] px-1.5 py-1 font-sans text-[12px] tabular-nums cursor-pointer transition-colors',
                  pageNum === page
                    ? 'bg-accent-foreground text-primary-foreground font-semibold'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                {pageNum}
              </button>
            )
          })}
          <button
            type="button"
            aria-label="下一页"
            disabled={page >= totalPages || loading}
            onClick={() => setPage((p) => p + 1)}
            className={cn(
              'rounded-[6px] p-1.5 cursor-pointer transition-colors text-muted-foreground hover:bg-muted hover:text-foreground',
              (page >= totalPages || loading) && 'opacity-30 cursor-not-allowed',
            )}
          >
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>
      )}
    </div>
  )
}
