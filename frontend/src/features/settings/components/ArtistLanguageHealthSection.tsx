import { useState } from 'react'
import { ChevronDown, Languages, RefreshCw, Search } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ArtistLanguageReviewDialog } from '@/features/settings/components/ArtistLanguageReviewDialog'
import { useAnalysisFilters, useMusicSearch } from '@/hooks/useAnalysis'
import {
  useArtistLanguageCoverage,
  useArtistLanguageReviews,
  useStartArtistLanguageReview,
} from '@/hooks/useArtistLanguageMetadata'
import { cn } from '@/lib/utils'
import type {
  ArtistLanguageReviewItem,
  ArtistLanguageReviewStatus,
} from '@/types/artist-language-metadata'
import type { MusicSearchResult } from '@/types/music-search'

const STATUS_OPTIONS: Array<{ value: ArtistLanguageReviewStatus; label: string }> = [
  { value: 'open', label: '待审核' },
  { value: 'approved', label: '已批准' },
  { value: 'rejected', label: '已拒绝' },
  { value: 'insufficient_evidence', label: '证据不足' },
]

const PRE_REVIEW_LABELS: Record<string, string> = {
  recommend_approve: 'Codex 建议通过',
  manual_review: 'Codex 建议重点复核',
  insufficient_evidence: 'Codex 判断证据不足',
  recommend_reject: 'Codex 建议拒绝',
}

function formatHours(hours: number): string {
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(hours)}h`
}

function formatPct(value: number): string {
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(value)}%`
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

function LanguageCollapsibleSection({
  summary,
  children,
}: {
  summary: string
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(false)

  return (
    <section aria-label="艺人语言数据" className="border-t border-border/70 pt-5">
      <button
        aria-expanded={open}
        aria-label="艺人语言数据"
        className="group w-full text-left focus-visible:outline-none"
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[13px] font-semibold text-foreground">
              <Languages className="size-4 text-accent-foreground" />
              艺人语言数据
            </div>
            <p className="mt-1 break-words text-[12px] leading-relaxed text-muted-foreground">
              {open ? '独立于 genre 的已审核艺人常用演唱语言。' : summary}
            </p>
          </div>
          <ChevronDown
            className={cn(
              'mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform',
              open && 'rotate-180',
            )}
          />
        </div>
      </button>
      {open && <div className="mt-5">{children}</div>}
    </section>
  )
}

export function ArtistLanguageHealthSection() {
  const { filters } = useAnalysisFilters()
  const [reviewStatus, setReviewStatus] = useState<ArtistLanguageReviewStatus>('open')
  const [artistQuery, setArtistQuery] = useState('')
  const [selectedArtist, setSelectedArtist] = useState<MusicSearchResult | null>(null)
  const [activeReview, setActiveReview] = useState<ArtistLanguageReviewItem | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const coverageQuery = useArtistLanguageCoverage(filters)
  const reviewsQuery = useArtistLanguageReviews(reviewStatus, 100)
  const openReviewsQuery = useArtistLanguageReviews('open', 100)
  const startReview = useStartArtistLanguageReview(filters)
  const artistSearch = useMusicSearch(artistQuery, 'artist', 5)

  const coverage = coverageQuery.data
  const reviews = reviewsQuery.data?.items ?? []
  const openCount = openReviewsQuery.data?.total ?? 0
  const summary = coverage
    ? `已分类 ${formatPct(coverage.classified_pct)} · 未知 ${formatPct(coverage.unknown_pct)} · 待审核 ${openCount}`
    : `语言覆盖率加载中 · 待审核 ${openCount}`

  const openReview = (review: ArtistLanguageReviewItem) => {
    setActiveReview(review)
    setDialogOpen(true)
  }

  const beginReview = async (artistId: number) => {
    setMessage(null)
    try {
      const review = await startReview.mutateAsync({
        artist_id: artistId,
        reason: 'manual_research',
      })
      openReview(review)
    } catch (error) {
      setMessage(errorMessage(error, '无法开始审核'))
    }
  }

  const refresh = () => {
    void coverageQuery.refetch()
    void reviewsQuery.refetch()
    if (reviewStatus !== 'open') void openReviewsQuery.refetch()
  }

  const searchResults = artistQuery.trim() ? (artistSearch.data?.artists ?? []) : []
  const loading = coverageQuery.isLoading || reviewsQuery.isLoading
  const loadError = coverageQuery.error ?? reviewsQuery.error

  return (
    <>
      <LanguageCollapsibleSection summary={summary}>
        <div className="space-y-5">
          <div className="grid grid-cols-3 gap-2" aria-label="语言数据摘要">
            <div className="min-w-0 rounded-[8px] bg-muted/25 px-3 py-3">
              <p className="text-[10.5px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">已分类</p>
              <p className="mt-1 font-mono text-[20px] font-semibold text-foreground">
                {coverage ? formatPct(coverage.classified_pct) : '—'}
              </p>
            </div>
            <div className="min-w-0 rounded-[8px] bg-muted/25 px-3 py-3">
              <p className="text-[10.5px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">未知</p>
              <p className="mt-1 font-mono text-[20px] font-semibold text-foreground">
                {coverage ? formatPct(coverage.unknown_pct) : '—'}
              </p>
            </div>
            <div className="min-w-0 rounded-[8px] bg-muted/25 px-3 py-3">
              <p className="text-[10.5px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">待审核</p>
              <p className="mt-1 font-mono text-[20px] font-semibold text-foreground">{openCount}</p>
            </div>
          </div>

          {message && (
            <p className="rounded-[8px] bg-destructive/10 px-3 py-2 text-[12px] text-destructive">
              {message}
            </p>
          )}
          {loadError && (
            <p className="rounded-[8px] bg-destructive/10 px-3 py-2 text-[12px] text-destructive">
              {errorMessage(loadError, '语言数据加载失败')}
            </p>
          )}

          <section aria-label="查找待审核艺人">
            <div className="mb-2 flex items-center justify-between gap-3">
              <h3 className="text-[12.5px] font-semibold text-foreground">查找艺人</h3>
              <Button
                aria-label="刷新艺人语言数据"
                disabled={coverageQuery.isFetching || reviewsQuery.isFetching}
                onClick={refresh}
                size="icon-sm"
                title="刷新艺人语言数据"
                variant="ghost"
              >
                <RefreshCw className={cn('size-3.5', (coverageQuery.isFetching || reviewsQuery.isFetching) && 'animate-spin')} />
              </Button>
            </div>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
              <input
                aria-label="查找待审核艺人"
                className="h-9 w-full rounded-[8px] border border-input bg-background pl-8 pr-3 text-[13px] outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
                onChange={(event) => {
                  setArtistQuery(event.target.value)
                  setSelectedArtist(null)
                }}
                placeholder="按艺人名查找"
                type="search"
                value={artistQuery}
              />
            </div>
            {artistSearch.loading && artistQuery.trim() && (
              <p className="mt-2 text-[12px] text-muted-foreground">正在查找…</p>
            )}
            {searchResults.length > 0 && !selectedArtist && (
              <div className="mt-2 max-h-40 overflow-y-auto rounded-[8px] border border-border bg-background p-1">
                {searchResults.map((artist) => (
                  <button
                    aria-label={`选择艺人 ${artist.label}`}
                    className="flex w-full items-center justify-between gap-3 rounded-md px-2.5 py-2 text-left text-[12.5px] hover:bg-muted"
                    key={`${artist.artist_id}:${artist.label}`}
                    onClick={() => setSelectedArtist(artist)}
                    type="button"
                  >
                    <span className="min-w-0 truncate text-foreground">{artist.label}</span>
                    <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
                      {formatHours(artist.total_ms / 3_600_000)}
                    </span>
                  </button>
                ))}
              </div>
            )}
            {selectedArtist?.artist_id != null && (
              <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-[8px] bg-muted/25 px-3 py-2">
                <span className="min-w-0 break-words text-[12.5px] font-medium text-foreground">
                  {selectedArtist.label}
                </span>
                <Button
                  aria-label={`开始审核 ${selectedArtist.label}`}
                  disabled={startReview.isPending}
                  onClick={() => void beginReview(selectedArtist.artist_id!)}
                  size="sm"
                >
                  开始审核
                </Button>
              </div>
            )}
          </section>

          <section aria-label="Top 未知艺人">
            <h3 className="text-[12.5px] font-semibold text-foreground">Top 未知艺人</h3>
            {coverage?.top_missing.length ? (
              <ol className="mt-2 divide-y divide-border/60">
                {coverage.top_missing.slice(0, 10).map((artist, index) => (
                  <li className="flex items-center justify-between gap-3 py-2.5" key={artist.artist_id}>
                    <div className="flex min-w-0 items-center gap-2 text-[12.5px]">
                      <span className="w-4 shrink-0 font-mono text-[11px] text-muted-foreground">{index + 1}</span>
                      <span className="min-w-0 break-words text-foreground">{artist.artist_name}</span>
                      <span className="shrink-0 font-mono text-[11px] text-muted-foreground">{formatHours(artist.hours)}</span>
                    </div>
                    <Button
                      aria-label={`审核 ${artist.artist_name}`}
                      disabled={startReview.isPending}
                      onClick={() => void beginReview(artist.artist_id)}
                      size="xs"
                      variant="outline"
                    >
                      审核
                    </Button>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="mt-2 text-[12px] text-muted-foreground">暂无高播放量未知艺人。</p>
            )}
          </section>

          <section aria-label="艺人语言审核记录">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-[12.5px] font-semibold text-foreground">审核记录</h3>
              <Select
                onValueChange={(value) => setReviewStatus(value as ArtistLanguageReviewStatus)}
                value={reviewStatus}
              >
                <SelectTrigger aria-label="审核状态" className="w-[112px]" size="sm">
                  <SelectValue>
                    {STATUS_OPTIONS.find((option) => option.value === reviewStatus)?.label}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent align="end">
                  {STATUS_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {loading ? (
              <p className="mt-3 text-[12px] text-muted-foreground">正在加载审核记录…</p>
            ) : reviews.length ? (
              <div className="mt-2 divide-y divide-border/60">
                {reviews.slice(0, 100).map((review) => (
                  <div className="flex flex-wrap items-center justify-between gap-2 py-2.5" key={review.review_id}>
                    <div className="min-w-0">
                      <p className="break-words text-[12.5px] font-medium text-foreground">{review.artist_name}</p>
                      <p className="mt-0.5 break-words text-[11.5px] text-muted-foreground">
                        {review.resolution_note
                          || `${formatHours(review.play_hours_snapshot)} · ${review.pre_review_recommendation
                            ? PRE_REVIEW_LABELS[review.pre_review_recommendation] ?? review.pre_review_recommendation
                            : '等待人工审核'}`}
                      </p>
                    </div>
                    <Button
                      aria-label={`打开审核记录 ${review.artist_name}`}
                      onClick={() => openReview(review)}
                      size="xs"
                      variant="ghost"
                    >
                      {review.status === 'open' ? '审核' : '查看'}
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-[12px] text-muted-foreground">当前状态暂无记录。</p>
            )}
          </section>

          {coverage?.caveat && (
            <p className="break-words border-l-2 border-accent-foreground/50 pl-3 font-serif text-[12.5px] italic leading-relaxed text-muted-foreground">
              {coverage.caveat}
            </p>
          )}
        </div>
      </LanguageCollapsibleSection>

      <ArtistLanguageReviewDialog
        onOpenChange={setDialogOpen}
        open={dialogOpen}
        review={activeReview}
      />
    </>
  )
}
