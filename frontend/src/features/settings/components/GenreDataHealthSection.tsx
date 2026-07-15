import { useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  ChevronDown,
  CheckCircle2,
  RefreshCw,
  Search,
  Sparkles,
  XCircle,
} from 'lucide-react'

import { queryKeys } from '@/api/query-keys'
import { GlassCard } from '@/components/shared/GlassCard'
import { AITaskProgress } from '@/features/ai-tasks/AITaskProgress'
import { CollapsibleSection } from '@/features/settings/components/SettingsHelpers'
import { ArtistLanguageHealthSection } from '@/features/settings/components/ArtistLanguageHealthSection'
import {
  useApproveArtistGenreReview,
  useArtistGenreAxisGaps,
  useArtistGenreCoverage,
  useArtistGenreReviews,
  useArtistGenreTaxonomy,
  useRejectArtistGenreReview,
  useStartArtistGenreBackfillTask,
  useUpdateArtistGenreEvidence,
} from '@/hooks/useArtistGenreMetadata'
import { useAiTask } from '@/hooks/useAiTasks'
import { useAnalysisFilters } from '@/hooks/useAnalysis'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type {
  ArtistGenreAxisSummaryItem,
  ArtistGenreCanonicalItem,
  ArtistGenreRawMappingItem,
  ArtistGenreRiskFlag,
  ArtistGenreReviewItem,
} from '@/types/artist-genre-metadata'

type GenreHealthPanel = 'overview' | 'reviews' | 'audit'
type GenreReviewStatus = 'open' | 'approved' | 'rejected'

const BACKFILL_PAYLOAD = {
  limit: 10,
  min_hours: 8,
  include_ai: true,
  approve_high_confidence_external: true,
}
const REVIEW_PAGE_SIZE = 10

const SOURCE_LABELS: Record<string, string> = {
  spotify: 'Spotify',
  curated_seed: '人工种子',
  manual_override: '手动覆盖',
  llm: 'LLM',
  lastfm: 'Last.fm',
  musicbrainz: 'MusicBrainz',
  wikidata: 'Wikidata',
  unknown: '未知',
}

const CONFIDENCE_LABELS: Record<string, string> = {
  high: '高可信',
  medium: '中可信',
  low: '低可信',
}

const PRE_REVIEW_LABELS: Record<string, string> = {
  recommend_approve: 'Codex 建议通过',
  manual_review: 'Codex 建议重点复核',
  insufficient_evidence: 'Codex 判断证据不足',
  recommend_reject: 'Codex 建议拒绝',
}

function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source
}

function confidenceLabel(tier: string): string {
  return CONFIDENCE_LABELS[tier] ?? tier
}

function confidenceClass(tier: string): string {
  if (tier === 'high') return 'border-green-500/30 bg-green-500/10 text-green-700 dark:text-green-300'
  if (tier === 'low') return 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300'
  return 'border-border bg-background text-muted-foreground'
}

function formatHours(hours: number): string {
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(hours)}h`
}

function formatPct(value: number): string {
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(value)}%`
}

function isTerminalStatus(status: string | null | undefined): boolean {
  return status === 'done' || status === 'error' || status === 'cancelled'
}

function LoadingState() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <Skeleton key={index} className="h-20 w-full rounded-[8px]" />
        ))}
      </div>
      <Skeleton className="h-24 w-full rounded-[8px]" />
      <Skeleton className="h-28 w-full rounded-[8px]" />
    </div>
  )
}

function EmptyReviews({ status, searching }: { status: GenreReviewStatus; searching: boolean }) {
  const statusLabel = status === 'open' ? '待审核' : status === 'approved' ? '已批准' : '已拒绝'
  return (
    <div className="rounded-[8px] border border-border bg-muted/20 px-4 py-5 text-center">
      <CheckCircle2 className="mx-auto size-5 text-green-600 dark:text-green-400" />
      <p className="mt-2 text-[13px] font-medium text-foreground">
        {searching ? '没有匹配的审核记录' : `暂无${statusLabel}记录`}
      </p>
      <p className="mt-1 text-[12px] text-muted-foreground">
        {searching ? '可尝试缩短关键词或切换审核状态。' : '新的外部或 LLM 建议会在对应状态下显示。'}
      </p>
    </div>
  )
}

function PanelSwitch({
  activePanel,
  items,
  onChange,
}: {
  activePanel: GenreHealthPanel
  items: Array<{ value: GenreHealthPanel; label: string; meta: string }>
  onChange: (panel: GenreHealthPanel) => void
}) {
  return (
    <div
      aria-label="Genre 数据视图"
      className="flex gap-1 overflow-x-auto rounded-[8px] border border-border bg-muted/30 p-1"
      role="tablist"
    >
      {items.map((item) => {
        const active = activePanel === item.value
        return (
          <button
            aria-label={item.label}
            aria-selected={active}
            className={cn(
              'flex min-w-fit items-center gap-2 rounded-md px-3 py-2 text-[12.5px] font-medium transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50',
              active
                ? 'border border-border bg-background text-foreground shadow-sm'
                : 'border border-transparent text-muted-foreground hover:bg-background/70 hover:text-foreground',
            )}
            key={item.value}
            onClick={() => onChange(item.value)}
            role="tab"
            type="button"
          >
            <span>{item.label}</span>
            <span
              className={cn(
                'rounded-full px-1.5 py-0.5 font-mono text-[10.5px] leading-none',
                active
                  ? 'bg-accent-foreground/10 text-accent-foreground'
                  : 'bg-background text-muted-foreground',
              )}
            >
              {item.meta}
            </span>
          </button>
        )
      })}
    </div>
  )
}

function GenrePill({ children, subtle = false }: { children: string; subtle?: boolean }) {
  return (
    <span
      className={cn(
        'rounded-md px-2 py-1 text-[11.5px]',
        subtle
          ? 'border border-border bg-background text-muted-foreground'
          : 'bg-accent-foreground/10 text-accent-foreground',
      )}
    >
      {children}
    </span>
  )
}

function MappingRow({ item }: { item: ArtistGenreRawMappingItem }) {
  return (
    <li className="rounded-[8px] border border-border bg-background/70 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <GenrePill subtle>{item.raw_genre}</GenrePill>
        <span className="text-[12px] text-muted-foreground">→</span>
        {item.canonical_genres.map((genre) => (
          <GenrePill key={genre}>{genre}</GenrePill>
        ))}
      </div>
      <p className="mt-2 text-[11.5px] text-muted-foreground">
        {formatHours(item.hours)} · {item.artist_count} 位艺人
      </p>
    </li>
  )
}

function CanonicalGenreAuditRow({ genre }: { genre: ArtistGenreCanonicalItem }) {
  const label = genre.label || genre.name
  const axis = genre.axis || 'style'
  const topSource = genre.source_mix?.[0]
  const topArtists = (genre.top_artists ?? []).slice(0, 2)
  const riskFlags: ArtistGenreRiskFlag[] =
    genre.risk_flags?.length
      ? genre.risk_flags
      : genre.dominance_warning
        ? [
            {
              code: 'single_artist_dominance',
              severity: 'medium',
              message: genre.dominance_warning,
            },
          ]
        : []

  return (
    <div className="border-b border-border/70 pb-3 last:border-b-0 last:pb-0">
      <div className="mb-1 flex items-start justify-between gap-3 text-[12px]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-medium text-foreground">{label}</span>
            {label !== genre.name && (
              <span className="font-mono text-[11px] text-muted-foreground">{genre.name}</span>
            )}
            <span className="rounded-full border border-border bg-background px-1.5 py-0.5 text-[10.5px] font-medium text-muted-foreground">
              {axis}
            </span>
            <span
              className={cn(
                'rounded-full border px-1.5 py-0.5 text-[10.5px] font-medium',
                confidenceClass(genre.confidence_tier),
              )}
            >
              {confidenceLabel(genre.confidence_tier)}
            </span>
          </div>
          <p className="mt-1 text-[11.5px] text-muted-foreground">{formatHours(genre.hours)}</p>
        </div>
        <span className="shrink-0 font-mono text-muted-foreground">{formatPct(genre.share_pct)}</span>
      </div>

      <div className="h-1.5 overflow-hidden rounded-full bg-background">
        <div
          className="h-full rounded-full bg-accent-foreground"
          style={{ width: `${Math.max(2, Math.min(100, genre.share_pct))}%` }}
        />
      </div>

      {(topSource || topArtists.length > 0) && (
        <details className="mt-2 text-[11.5px] leading-relaxed text-muted-foreground">
          <summary className="cursor-pointer select-none font-medium text-foreground/80">
            来源与代表艺人
          </summary>
          <div className="mt-2 space-y-1.5">
            {topSource && (
              <p className="flex flex-wrap items-center gap-x-1.5 gap-y-1">
                <span className="font-medium text-foreground/80">来源占比</span>
                <span className="font-mono">{topSource.source}</span>
                <span className="font-mono">{formatPct(topSource.share_pct)}</span>
                <span className="font-mono">{formatHours(topSource.hours)}</span>
                <span>来源记录置信度 {formatPct(topSource.confidence * 100)}</span>
                <span>证据链接覆盖 {formatPct(topSource.evidence_pct)}</span>
              </p>
            )}
            {topArtists.length > 0 && (
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="font-medium text-foreground/80">代表艺人</span>
                {topArtists.map((artist) => (
                  <span className="min-w-0" key={artist.artist_name}>
                    <span className="font-medium text-foreground">{artist.artist_name}</span>
                    <span className="font-mono">
                      {' '}
                      · {formatPct(artist.share_pct)}
                    </span>
                    {artist.raw_genres.length > 0 && (
                      <span> · 原始标签: {artist.raw_genres.slice(0, 3).join(', ')}</span>
                    )}
                  </span>
                ))}
              </div>
            )}
          </div>
        </details>
      )}

      {riskFlags.length > 0 && (
        <div className="mt-2 space-y-1">
          {riskFlags.map((flag) => (
            <p
              className="flex items-start gap-1.5 text-[11.5px] leading-relaxed text-amber-700 dark:text-amber-300"
              key={`${genre.name}-${flag.code}-${flag.message}`}
            >
              <AlertCircle className="mt-0.5 size-3 shrink-0" />
              <span>{flag.message}</span>
            </p>
          ))}
        </div>
      )}
    </div>
  )
}

function AxisGenreGroup({
  summary,
  genres,
}: {
  summary: ArtistGenreAxisSummaryItem
  genres: ArtistGenreCanonicalItem[]
}) {
  return (
    <section
      aria-label={`genre axis ${summary.label}`}
      className="rounded-[8px] border border-border bg-background/70 p-3"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h5 className="text-[12.5px] font-semibold text-foreground">{summary.label}</h5>
            <span className="rounded-full border border-border bg-muted/40 px-2 py-0.5 text-[11px] text-muted-foreground">
              {summary.axis}
            </span>
            <span className="rounded-full border border-border bg-muted/40 px-2 py-0.5 text-[11px] tabular-nums text-muted-foreground">
              {summary.canonical_count} 个标签
            </span>
          </div>
          <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
            {summary.interpretation}
          </p>
        </div>
        <div className="shrink-0 text-left sm:text-right">
          <p className="font-mono text-[13px] font-semibold text-foreground">
            覆盖 {formatPct(summary.coverage_pct)}
          </p>
          <p className="mt-1 font-mono text-[11.5px] text-muted-foreground">
            {formatHours(summary.hours)} · 未知 {formatPct(summary.unknown_pct)}
          </p>
        </div>
      </div>
      <div className="mt-3 space-y-3">
        {genres.map((genre) => (
          <CanonicalGenreAuditRow genre={genre} key={genre.name} />
        ))}
      </div>
    </section>
  )
}

function ReviewCard({
  item,
  busy,
  onApprove,
  onReject,
  onSaveEvidence,
}: {
  item: ArtistGenreReviewItem
  busy: boolean
  onApprove: (reviewId: number) => void
  onReject: (reviewId: number) => void
  onSaveEvidence: (reviewId: number, evidenceUrl: string, evidenceSummary: string) => void
}) {
  const [evidenceUrl, setEvidenceUrl] = useState(item.evidence_url ?? '')
  const [evidenceSummary, setEvidenceSummary] = useState(item.evidence_summary ?? '')
  const isOpen = item.review_status === 'open'
  const canApprove = isOpen && item.evidence_url?.startsWith('https://')
  return (
    <article
      aria-label={`审核 ${item.artist_name} 的 genre 建议`}
      className="rounded-[8px] border border-border bg-muted/20 p-4"
    >
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="truncate text-[14px] font-semibold text-foreground">
              {item.artist_name}
            </h4>
            <span className="rounded-full border border-border bg-background px-2 py-0.5 text-[11px] text-muted-foreground">
              {sourceLabel(item.source)}
            </span>
            <span className="rounded-full border border-border bg-background px-2 py-0.5 text-[11px] tabular-nums text-muted-foreground">
              {Math.round(item.confidence * 100)}%
            </span>
          </div>
          <p className="mt-1 text-[12px] text-muted-foreground">
            {formatHours(item.play_hours)} · {item.reason}
          </p>
        </div>
        {isOpen && <div className="flex shrink-0 gap-2">
          <Button
            aria-label={`通过 ${item.artist_name} 的 genre 建议`}
            className="gap-1.5"
            disabled={busy || !canApprove}
            onClick={() => onApprove(item.review_id)}
            size="sm"
            variant="outline"
          >
            <CheckCircle2 className="size-3.5" />
            通过
          </Button>
          <Button
            aria-label={`拒绝 ${item.artist_name} 的 genre 建议`}
            className="gap-1.5"
            disabled={busy}
            onClick={() => onReject(item.review_id)}
            size="sm"
            variant="destructive"
          >
            <XCircle className="size-3.5" />
            拒绝
          </Button>
        </div>}
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {item.genres.map((genre) => (
          <span
            className={cn(
              'rounded-md px-2 py-1 text-[12px]',
              genre === item.primary_genre
                ? 'bg-accent-foreground text-primary-foreground'
                : 'border border-border bg-background text-foreground',
            )}
            key={genre}
          >
            {genre}
          </span>
        ))}
      </div>

      {item.pre_review_recommendation && (
        <div className="mt-3 rounded-[8px] border border-accent-foreground/20 bg-accent-foreground/5 px-3 py-2.5">
          <div className="flex flex-wrap items-center gap-2 text-[11.5px]">
            <span className="font-semibold text-accent-foreground">
              {PRE_REVIEW_LABELS[item.pre_review_recommendation] ?? item.pre_review_recommendation}
            </span>
            {item.pre_review_confidence != null && (
              <span className="font-mono text-muted-foreground">
                {Math.round(item.pre_review_confidence * 100)}%
              </span>
            )}
            {item.pre_reviewed_by && <span className="text-muted-foreground">{item.pre_reviewed_by}</span>}
          </div>
          {item.pre_review_note && (
            <p className="mt-1 break-words text-[12px] leading-relaxed text-muted-foreground">
              {item.pre_review_note}
            </p>
          )}
        </div>
      )}

      {item.evidence_summary && (
        <p className="mt-3 text-[12.5px] leading-relaxed text-muted-foreground">
          {item.evidence_summary}
        </p>
      )}
      {item.evidence_url && (
        <a className="mt-2 block break-all text-[11.5px] text-accent-foreground underline underline-offset-2" href={item.evidence_url} rel="noreferrer" target="_blank">
          {item.evidence_url}
        </a>
      )}
      {isOpen && !item.evidence_url && (
        <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
          <input
            aria-label={`证据链接 ${item.artist_name}`}
            className="h-9 min-w-0 rounded-[8px] border border-input bg-background px-3 text-[12px] outline-none focus-visible:ring-2 focus-visible:ring-ring/30"
            onChange={(event) => setEvidenceUrl(event.target.value)}
            placeholder="https:// 官方或编辑来源"
            type="url"
            value={evidenceUrl}
          />
          <input
            aria-label={`证据摘要 ${item.artist_name}`}
            className="h-9 min-w-0 rounded-[8px] border border-input bg-background px-3 text-[12px] outline-none focus-visible:ring-2 focus-visible:ring-ring/30"
            onChange={(event) => setEvidenceSummary(event.target.value)}
            placeholder="这份来源支持哪些标签"
            value={evidenceSummary}
          />
          <Button
            disabled={busy || !evidenceUrl.startsWith('https://') || !evidenceSummary.trim()}
            onClick={() => onSaveEvidence(item.review_id, evidenceUrl, evidenceSummary)}
            size="sm"
            variant="outline"
          >
            保存证据
          </Button>
        </div>
      )}
      {!isOpen && item.resolution_note && (
        <p className="mt-3 text-[11.5px] text-muted-foreground">
          {item.reviewed_at || item.updated_at} · {item.reviewed_by || '本地审核'} · {item.resolution_note}
        </p>
      )}
    </article>
  )
}

export function GenreDataHealthSection() {
  const { filters } = useAnalysisFilters()
  const queryClient = useQueryClient()
  const [message, setMessage] = useState<string | null>(null)
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  const [activePanel, setActivePanel] = useState<GenreHealthPanel>('overview')
  const [reviewStatus, setReviewStatus] = useState<GenreReviewStatus>('open')
  const [reviewSearch, setReviewSearch] = useState('')
  const [visibleReviewCount, setVisibleReviewCount] = useState(REVIEW_PAGE_SIZE)

  const coverageQuery = useArtistGenreCoverage(filters)
  const taxonomyQuery = useArtistGenreTaxonomy(filters)
  const styleGapsQuery = useArtistGenreAxisGaps(filters, 'style', 50)
  const reviewsQuery = useArtistGenreReviews(reviewStatus, 100)
  const openReviewsQuery = useArtistGenreReviews('open', 1)
  const approveMutation = useApproveArtistGenreReview()
  const rejectMutation = useRejectArtistGenreReview()
  const startBackfillMutation = useStartArtistGenreBackfillTask()
  const evidenceMutation = useUpdateArtistGenreEvidence()
  const activeTask = useAiTask(activeTaskId)

  const coverage = coverageQuery.data
  const taxonomy = taxonomyQuery.data
  const reviews = reviewsQuery.data?.items ?? []
  const filteredReviews = useMemo(() => {
    const query = reviewSearch.trim().toLocaleLowerCase()
    if (!query) return reviews
    return reviews.filter((item) =>
      [item.artist_name, item.primary_genre, ...item.genres, item.evidence_summary]
        .filter(Boolean)
        .some((value) => String(value).toLocaleLowerCase().includes(query)),
    )
  }, [reviewSearch, reviews])
  const visibleReviews = filteredReviews.slice(0, visibleReviewCount)
  const loading = coverageQuery.isLoading || taxonomyQuery.isLoading || styleGapsQuery.isLoading || reviewsQuery.isLoading
  const error = coverageQuery.error ?? taxonomyQuery.error ?? styleGapsQuery.error ?? reviewsQuery.error
  const reviewBusy = approveMutation.isPending || rejectMutation.isPending || evidenceMutation.isPending
  const openReviewCount = openReviewsQuery.data?.total ?? 0

  const sourceRows = useMemo(() => {
    if (!coverage) return []
    return Object.entries(coverage.source_hours)
      .sort((a, b) => b[1] - a[1])
      .map(([source, hours]) => ({
        source,
        hours,
        pct: coverage.known_hours > 0 ? (hours / coverage.known_hours) * 100 : 0,
      }))
  }, [coverage])

  const taxonomyAxisGroups = useMemo(() => {
    if (!taxonomy) return []
    const genresByAxis = new Map<string, ArtistGenreCanonicalItem[]>()
    taxonomy.top_canonical_genres.forEach((genre) => {
      const axis = genre.axis || 'style'
      const rows = genresByAxis.get(axis) ?? []
      rows.push(genre)
      genresByAxis.set(axis, rows)
    })

    const groups = taxonomy.axis_summary
      .filter((summary) => (genresByAxis.get(summary.axis) ?? []).length > 0)
      .map((summary) => ({
        summary,
        genres: genresByAxis.get(summary.axis) ?? [],
      }))

    genresByAxis.forEach((genres, axis) => {
      if (groups.some((group) => group.summary.axis === axis)) return
      groups.push({
        summary: {
          axis,
          label: axis,
          hours: genres.reduce((total, genre) => total + genre.hours, 0),
          share_pct: genres.reduce((total, genre) => total + genre.share_pct, 0),
          coverage_pct: genres.reduce((total, genre) => total + genre.overall_share_pct, 0),
          unknown_hours: 0,
          unknown_pct: 0,
          canonical_count: genres.length,
          interpretation: genres[0]?.interpretation ?? '标准化统计标签，需结合原始来源审计解释。',
        },
        genres,
      })
    })

    return groups
  }, [taxonomy])

  useEffect(() => {
    if (!activeTaskId || !isTerminalStatus(activeTask.task?.status as string | null | undefined)) return
    void queryClient.invalidateQueries({ queryKey: queryKeys.metadata.artistGenres.all })
    void queryClient.invalidateQueries({ queryKey: queryKeys.yearlyReview.all })
  }, [activeTask.task?.status, activeTaskId, queryClient])

  const refresh = () => {
    void coverageQuery.refetch()
    void taxonomyQuery.refetch()
    void styleGapsQuery.refetch()
    void reviewsQuery.refetch()
  }

  const approve = async (reviewId: number) => {
    setMessage(null)
    try {
      await approveMutation.mutateAsync(reviewId)
      setMessage('已通过该 genre 建议')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '审核失败')
    }
  }

  const reject = async (reviewId: number) => {
    setMessage(null)
    try {
      await rejectMutation.mutateAsync(reviewId)
      setMessage('已拒绝该 genre 建议')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '审核失败')
    }
  }

  const saveEvidence = async (
    reviewId: number,
    evidenceUrl: string,
    evidenceSummary: string,
  ) => {
    setMessage(null)
    try {
      await evidenceMutation.mutateAsync({
        reviewId,
        evidence: { evidence_url: evidenceUrl, evidence_summary: evidenceSummary },
      })
      setMessage('已保存 genre 审核证据，现在可以批准该建议。')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '保存证据失败')
    }
  }

  const startBackfill = async () => {
    setMessage(null)
    try {
      const task = await startBackfillMutation.mutateAsync(BACKFILL_PAYLOAD)
      setActiveTaskId(task.task_id)
      setMessage('已启动 genre 补全任务')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '启动补全失败')
    }
  }

  const summary = coverage
    ? `已知 ${formatPct(coverage.known_pct)} · 待补 ${formatPct(coverage.unknown_pct)} · 待审 ${openReviewCount}`
    : undefined
  const panelItems = coverage
    ? [
        { value: 'overview' as const, label: '概览', meta: formatPct(coverage.known_pct) },
        { value: 'reviews' as const, label: '审核', meta: String(openReviewCount) },
        {
          value: 'audit' as const,
          label: '分类审计',
          meta: taxonomy ? String(taxonomy.canonical_genre_count) : '-',
        },
      ]
    : []

  return (
    <GlassCard className="p-6">
      <CollapsibleSection
        defaultOpen
        desc="查看艺人流派与常用演唱语言的覆盖率、来源和人工审核记录。"
        num={6}
        summary={summary}
        title="流派与语言数据健康"
      >
        <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0">
            <p className="text-[12.5px] leading-relaxed text-muted-foreground">
              Spotify 原始 genre 保持优先；某个统计轴缺失时，才使用该轴已审核的本地来源补足。原始标签覆盖率不等于声音风格覆盖率，Style 缺口按播放时长单独排序。
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button
              aria-label="刷新 genre 数据健康"
              className="gap-1.5"
              disabled={coverageQuery.isFetching || taxonomyQuery.isFetching || styleGapsQuery.isFetching || reviewsQuery.isFetching}
              onClick={refresh}
              size="sm"
              tabIndex={coverageQuery.isFetching || taxonomyQuery.isFetching || styleGapsQuery.isFetching || reviewsQuery.isFetching ? -1 : undefined}
              variant="outline"
            >
              <RefreshCw className={cn('size-3.5', (coverageQuery.isFetching || taxonomyQuery.isFetching || styleGapsQuery.isFetching || reviewsQuery.isFetching) && 'animate-spin')} />
              刷新
            </Button>
            <Button
              aria-label="小批量补全 genre"
              className="gap-1.5"
              disabled={startBackfillMutation.isPending}
              onClick={startBackfill}
              size="sm"
            >
              <Sparkles className="size-3.5" />
              小批量补全 genre
            </Button>
          </div>
        </div>

        {loading && <LoadingState />}

        {!loading && error && (
          <div className="flex items-center gap-2 rounded-[8px] border border-destructive/30 bg-destructive/10 px-4 py-3 text-[13px] text-destructive">
            <AlertCircle className="size-4 shrink-0" />
            {error instanceof Error ? error.message : 'Genre 数据加载失败'}
          </div>
        )}

        {!loading && !error && coverage && (
          <div className="space-y-5">
            {message && (
              <div className="flex items-center gap-2 rounded-[8px] bg-accent-foreground/10 px-3 py-2 text-[13px] text-accent-foreground">
                <CheckCircle2 className="size-3.5 shrink-0" />
                {message}
              </div>
            )}

            <div className="space-y-4">
              <PanelSwitch
                activePanel={activePanel}
                items={panelItems}
                onChange={setActivePanel}
              />

              {activePanel === 'overview' && (
                <section className="space-y-5">
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <div className="rounded-[8px] border border-border bg-muted/20 p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">原始标签覆盖</p>
                      <p className="mt-2 font-mono text-[26px] font-semibold leading-none text-foreground">{formatPct(coverage.known_pct)}</p>
                      <p className="mt-2 text-[12px] text-muted-foreground">{formatHours(coverage.known_hours)}</p>
                    </div>
                    <div className="rounded-[8px] border border-border bg-muted/20 p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">无来源标签</p>
                      <p className="mt-2 font-mono text-[26px] font-semibold leading-none text-foreground">{formatPct(coverage.unknown_pct)}</p>
                      <p className="mt-2 text-[12px] text-muted-foreground">{formatHours(coverage.unknown_hours)}</p>
                    </div>
                    <div className="rounded-[8px] border border-border bg-muted/20 p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">待审核</p>
                      <p className="mt-2 font-mono text-[26px] font-semibold leading-none text-foreground">{reviews.length}</p>
                      <p className="mt-2 text-[12px] text-muted-foreground">待处理建议</p>
                    </div>
                    <div className="rounded-[8px] border border-border bg-muted/20 p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">艺人总数</p>
                      <p className="mt-2 font-mono text-[26px] font-semibold leading-none text-foreground">{coverage.artist_count}</p>
                      <p className="mt-2 text-[12px] text-muted-foreground">{formatHours(coverage.total_hours)} 播放量</p>
                    </div>
                  </div>

                  {activeTaskId && (
                    <AITaskProgress task={activeTask.task} events={activeTask.events} />
                  )}

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <section className="rounded-[8px] border border-border bg-muted/20 p-4">
                      <h3 className="text-[13px] font-semibold text-foreground">来源占比</h3>
                      <div className="mt-3 space-y-3">
                        {sourceRows.map((row) => (
                          <div key={row.source}>
                            <div className="mb-1 flex items-center justify-between gap-3 text-[12px]">
                              <span className="font-medium text-foreground">{sourceLabel(row.source)}</span>
                              <span className="font-mono text-muted-foreground">{formatHours(row.hours)}</span>
                            </div>
                            <div className="h-1.5 overflow-hidden rounded-full bg-background">
                              <div
                                className="h-full rounded-full bg-accent-foreground"
                                style={{ width: `${Math.max(2, Math.min(100, row.pct))}%` }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </section>

                    <section className="rounded-[8px] border border-border bg-muted/20 p-4">
                      <div className="flex items-center justify-between gap-2">
                        <h3 className="text-[13px] font-semibold text-foreground">Style 待补艺人</h3>
                        <span className="font-mono text-[11px] text-muted-foreground">
                          {styleGapsQuery.data ? formatHours(styleGapsQuery.data.unknown_hours) : '-'}
                        </span>
                      </div>
                      {!styleGapsQuery.data?.items.length ? (
                        <p className="mt-3 text-[12px] text-muted-foreground">暂无 Style 缺口。</p>
                      ) : (
                        <ol className="mt-3 space-y-2">
                          {styleGapsQuery.data.items.slice(0, 6).map((artist, index) => (
                            <li className="flex items-center justify-between gap-3 text-[12.5px]" key={artist.artist_name}>
                              <div className="min-w-0">
                                <p className="truncate text-foreground">
                                  <span className="mr-2 font-mono text-muted-foreground">{index + 1}</span>
                                  {artist.artist_name}
                                </p>
                                <p className="mt-0.5 truncate pl-5 text-[10.5px] text-muted-foreground">
                                  {artist.raw_genres.join(' · ') || '无原始标签'}
                                  {artist.pre_review_recommendation ? ` · ${PRE_REVIEW_LABELS[artist.pre_review_recommendation] ?? artist.pre_review_recommendation}` : ''}
                                </p>
                              </div>
                              <span className="shrink-0 font-mono text-muted-foreground">{formatHours(artist.hours)}</span>
                            </li>
                          ))}
                        </ol>
                      )}
                    </section>
                  </div>
                </section>
              )}

              {activePanel === 'reviews' && (
                <section className="space-y-4">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <h3 className="text-[13px] font-semibold text-foreground">Genre 审核记录</h3>
                    <span className="font-mono text-[12px] text-muted-foreground">{reviewsQuery.data?.total ?? 0}</span>
                  </div>
                  <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                    <div aria-label="Genre 审核状态" className="flex w-fit gap-1 rounded-[8px] bg-muted/40 p-1">
                      {([
                        ['open', '待审核'],
                        ['approved', '已批准'],
                        ['rejected', '已拒绝'],
                      ] as const).map(([value, label]) => (
                        <button
                          aria-pressed={reviewStatus === value}
                          className={cn(
                            'rounded-md px-3 py-1.5 text-[12px] font-medium',
                            reviewStatus === value ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground',
                          )}
                          key={value}
                          onClick={() => {
                            setReviewStatus(value)
                            setVisibleReviewCount(REVIEW_PAGE_SIZE)
                          }}
                          type="button"
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    <label className="relative block min-w-0 md:w-64">
                      <Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
                      <input
                        aria-label="搜索 Genre 审核记录"
                        className="h-9 w-full rounded-[8px] border border-input bg-background pl-9 pr-3 text-[12px] outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring/30"
                        onChange={(event) => {
                          setReviewSearch(event.target.value)
                          setVisibleReviewCount(REVIEW_PAGE_SIZE)
                        }}
                        placeholder="搜索艺人、标签或证据"
                        type="search"
                        value={reviewSearch}
                      />
                    </label>
                  </div>
                  {filteredReviews.length === 0 ? (
                    <EmptyReviews status={reviewStatus} searching={Boolean(reviewSearch.trim())} />
                  ) : (
                    <div className="space-y-4">
                      <p className="text-[11.5px] text-muted-foreground">
                        显示 {visibleReviews.length} / {filteredReviews.length} 条
                      </p>
                      <div className="space-y-3">
                        {visibleReviews.map((item) => (
                          <ReviewCard
                            busy={reviewBusy}
                            item={item}
                            key={item.review_id}
                            onApprove={approve}
                            onReject={reject}
                            onSaveEvidence={saveEvidence}
                          />
                        ))}
                      </div>
                      {visibleReviews.length < filteredReviews.length && (
                        <div className="flex justify-center">
                          <Button
                            className="gap-1.5"
                            onClick={() => setVisibleReviewCount((count) => count + REVIEW_PAGE_SIZE)}
                            size="sm"
                            variant="outline"
                          >
                            <ChevronDown className="size-3.5" />
                            继续加载
                          </Button>
                        </div>
                      )}
                    </div>
                  )}
                </section>
              )}

              {activePanel === 'audit' && taxonomy && (
                  <section
                    aria-label="统计口径审计"
                    className="rounded-[8px] border border-border bg-muted/20 p-4"
                  >
                    <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                      <div>
                        <h3 className="text-[13px] font-semibold text-foreground">统计口径审计</h3>
                        <p className="mt-1 max-w-2xl text-[12.5px] leading-relaxed text-muted-foreground">
                          {taxonomy.caveat}
                        </p>
                      </div>
                      <span
                        className={cn(
                          'w-fit rounded-full border px-2 py-0.5 text-[11px]',
                          taxonomy.noncanonical_passthrough_count === 0
                            ? 'border-green-500/30 bg-green-500/10 text-green-700 dark:text-green-300'
                            : 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300',
                        )}
                      >
                        {taxonomy.noncanonical_passthrough_count === 0 ? '无透传异常' : '需复核透传'}
                      </span>
                    </div>

                    <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
                      <div className="rounded-[8px] border border-border bg-background/70 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">Raw 标签</p>
                        <p className="mt-2 font-mono text-[22px] font-semibold text-foreground">{taxonomy.raw_genre_count}</p>
                      </div>
                      <div className="rounded-[8px] border border-border bg-background/70 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">Canonical 标签</p>
                        <p className="mt-2 font-mono text-[22px] font-semibold text-foreground">{taxonomy.canonical_genre_count}</p>
                      </div>
                      <div className="rounded-[8px] border border-border bg-background/70 p-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">非标准透传</p>
                        <p className="mt-2 font-mono text-[22px] font-semibold text-foreground">{taxonomy.noncanonical_passthrough_count}</p>
                      </div>
                    </div>

                    <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
                      <div>
                        <h4 className="text-[12.5px] font-semibold text-foreground">Canonical 分轴</h4>
                        <div className="mt-3 space-y-3">
                          {taxonomyAxisGroups.map((group) => (
                            <AxisGenreGroup
                              genres={group.genres.slice(0, 8)}
                              key={group.summary.axis}
                              summary={group.summary}
                            />
                          ))}
                        </div>
                      </div>

                      <div>
                        <h4 className="text-[12.5px] font-semibold text-foreground">Raw → canonical 样例</h4>
                        <ol className="mt-3 grid grid-cols-1 gap-2">
                          {taxonomy.mapping_examples.slice(0, 5).map((item) => (
                            <MappingRow item={item} key={item.raw_genre} />
                          ))}
                        </ol>
                      </div>
                    </div>

                    {taxonomy.noncanonical_passthrough.length > 0 && (
                      <div className="mt-4 rounded-[8px] border border-amber-500/30 bg-amber-500/10 p-3">
                        <h4 className="text-[12.5px] font-semibold text-foreground">待归并透传标签</h4>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {taxonomy.noncanonical_passthrough.slice(0, 10).map((item) => (
                            <GenrePill subtle key={item.raw_genre}>{`${item.raw_genre} · ${formatHours(item.hours)}`}</GenrePill>
                          ))}
                        </div>
                      </div>
                    )}
                  </section>
              )}
            </div>
          </div>
        )}
        <ArtistLanguageHealthSection />
      </CollapsibleSection>
    </GlassCard>
  )
}
