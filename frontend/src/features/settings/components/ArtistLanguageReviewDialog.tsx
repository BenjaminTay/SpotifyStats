import { useMemo, useState } from 'react'
import { Minus, Plus, Search } from 'lucide-react'

import { ApiError } from '@/api/errors'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { useMusicSearchInputController } from '@/features/music/search/searchInputController'
import { useMusicSearchCandidates } from '@/features/music/search/useMusicSearch'
import { useAnalysisFilters } from '@/hooks/useAnalysis'
import {
  useDecideArtistLanguageReview,
  useSaveArtistLanguageSource,
} from '@/hooks/useArtistLanguageMetadata'
import type {
  ArtistLanguageEvidenceInput,
  ArtistLanguageEvidenceKind,
  ArtistLanguagePerformerAttribution,
  ArtistLanguageReviewAction,
  ArtistLanguageReviewItem,
  LanguageClassification,
} from '@/types/artist-language-metadata'
import { displayName, useChineseTextVersion } from '@/lib/chinese'

interface EvidenceDraft extends ArtistLanguageEvidenceInput {
  client_id: string
}

interface ArtistLanguageReviewDialogProps {
  open: boolean
  review: ArtistLanguageReviewItem | null
  onOpenChange: (open: boolean) => void
}

const CLASSIFICATIONS: Array<{ value: LanguageClassification; label: string }> = [
  { value: 'single_language', label: '单一语言' },
  { value: 'multilingual', label: '多语言' },
  { value: 'instrumental', label: '器乐为主' },
]

const EVIDENCE_KINDS: Array<{ value: ArtistLanguageEvidenceKind; label: string }> = [
  { value: 'artist_profile', label: '艺人官方资料' },
  { value: 'artist_repertoire', label: '作品目录' },
  { value: 'editorial_source', label: '编辑资料' },
  { value: 'track_credit', label: '曲目署名' },
  { value: 'track_language', label: '曲目语言' },
]

const ATTRIBUTIONS: Array<{ value: ArtistLanguagePerformerAttribution; label: string }> = [
  { value: 'artist_vocal_confirmed', label: '确认艺人演唱' },
  { value: 'artist_instrumental_confirmed', label: '确认艺人为器乐表演者' },
  { value: 'track_language_only', label: '仅确认曲目语言' },
  { value: 'not_applicable', label: '不适用' },
]

function blankEvidence(index: number): EvidenceDraft {
  return {
    client_id: `evidence-${Date.now()}-${index}`,
    local_track_id: null,
    claimed_language_code: null,
    claimed_language_variant: null,
    evidence_kind: 'artist_profile',
    performer_attribution: 'artist_vocal_confirmed',
    evidence_url: '',
    evidence_title: '',
    evidence_summary: '',
  }
}

function evidenceFromReview(review: ArtistLanguageReviewItem): EvidenceDraft[] {
  const rows = review.source?.evidence ?? []
  if (!rows.length) return [blankEvidence(0)]
  return rows.map((row, index) => ({
    client_id: `evidence-${row.evidence_id}-${index}`,
    local_track_id: row.local_track_id,
    claimed_language_code: row.claimed_language_code,
    claimed_language_variant: row.claimed_language_variant,
    evidence_kind: row.evidence_kind,
    performer_attribution: row.performer_attribution,
    evidence_url: row.evidence_url,
    evidence_title: row.evidence_title,
    evidence_summary: row.evidence_summary,
  }))
}

function readableError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.detail) {
      try {
        const parsed = JSON.parse(error.detail) as { message?: unknown }
        if (typeof parsed.message === 'string' && parsed.message.trim()) return parsed.message
      } catch {
        const messageMatch = error.detail.match(/"message"\s*:\s*"([^"]+)"/)
        if (messageMatch?.[1]) return messageMatch[1]
        return error.detail
      }
    }
    if (error.status === 422) return '候选事实或证据未满足批准条件，请检查后重试。'
  }
  return error instanceof Error ? error.message : '审核操作失败'
}

function isEvidenceStarted(evidence: EvidenceDraft): boolean {
  return Boolean(
    evidence.evidence_url.trim()
      || evidence.evidence_title.trim()
      || evidence.evidence_summary.trim()
      || evidence.claimed_language_code?.trim()
      || evidence.local_track_id,
  )
}

function isEvidenceComplete(evidence: EvidenceDraft): boolean {
  return evidence.evidence_url.trim().startsWith('https://')
    && Boolean(evidence.evidence_title.trim())
    && Boolean(evidence.evidence_summary.trim())
}

function compactEvidence(evidence: EvidenceDraft, classification: LanguageClassification): ArtistLanguageEvidenceInput {
  return {
    local_track_id: evidence.local_track_id || null,
    claimed_language_code: classification === 'instrumental' ? null : evidence.claimed_language_code?.trim() || null,
    claimed_language_variant: classification === 'instrumental' ? null : evidence.claimed_language_variant?.trim() || null,
    evidence_kind: evidence.evidence_kind,
    performer_attribution: evidence.performer_attribution,
    evidence_url: evidence.evidence_url.trim(),
    evidence_title: evidence.evidence_title.trim(),
    evidence_summary: evidence.evidence_summary.trim(),
  }
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="block min-w-0 text-[12px] font-medium text-foreground">
      <span>{label}</span>
      <div className="mt-1.5">{children}</div>
    </div>
  )
}

function EvidenceEditor({
  evidence,
  index,
  classification,
  canRemove,
  onChange,
  onRemove,
}: {
  evidence: EvidenceDraft
  index: number
  classification: LanguageClassification
  canRemove: boolean
  onChange: (value: EvidenceDraft) => void
  onRemove: () => void
}) {
  const trackInput = useMusicSearchInputController('')
  const trackQuery = trackInput.draft
  const { filters } = useAnalysisFilters()
  const trackSearch = useMusicSearchCandidates({
    query: trackInput.canSearch ? trackInput.settledQuery : '',
    filters,
    kind: 'track',
    pageSize: 5,
    eligibility: 'any_local',
  })
  const tracks = trackInput.canSearch ? (trackSearch.data?.tracks ?? []) : []
  const update = <K extends keyof EvidenceDraft>(key: K, value: EvidenceDraft[K]) => {
    onChange({ ...evidence, [key]: value })
  }

  return (
    <fieldset aria-label={`证据 ${index + 1}`} className="min-w-0 rounded-[8px] bg-muted/25 p-3">
      <legend className="sr-only">证据 {index + 1}</legend>
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">
          证据 {index + 1}
        </span>
        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                aria-label={`移除证据 ${index + 1}`}
                disabled={!canRemove}
                onClick={onRemove}
                size="icon-xs"
                title={`移除证据 ${index + 1}`}
                type="button"
                variant="ghost"
              />
            }
          >
            <Minus />
          </TooltipTrigger>
          <TooltipContent>移除此证据</TooltipContent>
        </Tooltip>
      </div>

      <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2">
        <Field label="证据类型">
          <Select
            onValueChange={(value) => update('evidence_kind', value as ArtistLanguageEvidenceKind)}
            value={evidence.evidence_kind}
          >
            <SelectTrigger aria-label={`证据类型 ${index + 1}`} className="w-full">
              <SelectValue>
                {EVIDENCE_KINDS.find((option) => option.value === evidence.evidence_kind)?.label}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {EVIDENCE_KINDS.map((option) => (
                <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label="表演归属">
          <Select
            onValueChange={(value) => update('performer_attribution', value as ArtistLanguagePerformerAttribution)}
            value={evidence.performer_attribution}
          >
            <SelectTrigger aria-label={`表演归属 ${index + 1}`} className="w-full">
              <SelectValue>
                {ATTRIBUTIONS.find((option) => option.value === evidence.performer_attribution)?.label}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {ATTRIBUTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      </div>

      {classification !== 'instrumental' && (
        <div className="mt-3 grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="语言代码">
            <input
              aria-label="语言代码"
              className="h-8 w-full min-w-0 rounded-[8px] border border-input bg-background px-2.5 text-[12.5px] outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
              onChange={(event) => update('claimed_language_code', event.target.value)}
              placeholder="如 en、zh"
              value={evidence.claimed_language_code ?? ''}
            />
          </Field>
          <Field label="主张变体">
            <input
              aria-label={`证据语言变体 ${index + 1}`}
              className="h-8 w-full min-w-0 rounded-[8px] border border-input bg-background px-2.5 text-[12.5px] outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
              onChange={(event) => update('claimed_language_variant', event.target.value)}
              placeholder="可选"
              value={evidence.claimed_language_variant ?? ''}
            />
          </Field>
        </div>
      )}

      <div className="mt-3 grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2">
        <Field label="证据 URL">
          <input
            aria-label="证据 URL"
            className="h-8 w-full min-w-0 rounded-[8px] border border-input bg-background px-2.5 text-[12.5px] outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
            onChange={(event) => update('evidence_url', event.target.value)}
            placeholder="https://…"
            type="url"
            value={evidence.evidence_url}
          />
        </Field>
        <Field label="证据标题">
          <input
            aria-label="证据标题"
            className="h-8 w-full min-w-0 rounded-[8px] border border-input bg-background px-2.5 text-[12.5px] outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
            onChange={(event) => update('evidence_title', event.target.value)}
            value={evidence.evidence_title}
          />
        </Field>
      </div>

      <Field label="证据摘要">
        <textarea
          aria-label="证据摘要"
          className="min-h-20 w-full min-w-0 resize-y rounded-[8px] border border-input bg-background px-2.5 py-2 text-[12.5px] leading-relaxed outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
          onChange={(event) => update('evidence_summary', event.target.value)}
          value={evidence.evidence_summary}
        />
      </Field>

      <div className="mt-3">
        <label className="text-[12px] font-medium text-foreground" htmlFor={`track-search-${evidence.client_id}`}>
          本地证据曲目
        </label>
        <div className="relative mt-1.5">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
          <input
            aria-label={`查找证据曲目 ${index + 1}`}
            className="h-9 w-full min-w-0 rounded-[8px] border border-input bg-background pl-8 pr-3 text-[12.5px] outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
            id={`track-search-${evidence.client_id}`}
            onChange={(event) => trackInput.setDraft(event.target.value)}
            onCompositionStart={trackInput.onCompositionStart}
            onCompositionEnd={(event) => trackInput.onCompositionEnd(event.currentTarget.value)}
            placeholder="可选，按曲名查找"
            type="search"
            value={trackQuery}
          />
        </div>
        {tracks.length > 0 && (
          <div className="mt-1 max-h-32 overflow-y-auto rounded-[8px] border border-border bg-background p-1">
            {tracks.map((track) => (
              <button
                aria-label={`选择曲目 ${displayName(track.label)}`}
                className="flex w-full min-w-0 items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-[12px] hover:bg-muted"
                key={`${track.track_id}:${track.label}`}
                onClick={() => {
                  update('local_track_id', track.track_id)
                  trackInput.setDraft('')
                }}
                type="button"
              >
                <span className="min-w-0 truncate text-foreground">{displayName(track.label)}</span>
                <span className="min-w-0 truncate text-muted-foreground">{displayName(track.artist_name ?? '')}</span>
              </button>
            ))}
          </div>
        )}
        {evidence.local_track_id != null && (
          <p className="mt-1.5 break-words text-[11.5px] text-muted-foreground">
            本地曲目 #{evidence.local_track_id}
          </p>
        )}
      </div>
    </fieldset>
  )
}

function ReadonlyReview({ review }: { review: ArtistLanguageReviewItem }) {
  const source = review.source
  return (
    <div className="space-y-4">
      <div className="rounded-[8px] bg-muted/25 p-3 text-[12.5px] leading-relaxed">
        <p><span className="text-muted-foreground">状态：</span>{review.status}</p>
        {review.pre_review_recommendation && <p><span className="text-muted-foreground">Codex 预审：</span>{review.pre_review_recommendation}{review.pre_review_confidence != null ? ` · ${Math.round(review.pre_review_confidence * 100)}%` : ''}</p>}
        {review.pre_review_note && <p className="mt-1 break-words text-muted-foreground">{review.pre_review_note}</p>}
        {source && <p><span className="text-muted-foreground">事实：</span>{source.classification}{source.primary_language_code ? ` · ${source.primary_language_code}` : ''}</p>}
        {source?.replaces_source_id != null && <p>替换来源 #{source.replaces_source_id}</p>}
        {review.reviewed_by && <p><span className="text-muted-foreground">审核人：</span>{review.reviewed_by}</p>}
        {review.reviewed_at && <p><span className="text-muted-foreground">审核时间：</span>{review.reviewed_at}</p>}
        {review.resolution_note && <p className="mt-2 break-words">{review.resolution_note}</p>}
      </div>
      {source?.evidence.map((evidence) => (
        <article className="rounded-[8px] bg-muted/25 p-3" key={evidence.evidence_id}>
          <a className="break-words text-[12.5px] font-medium text-foreground underline underline-offset-2" href={evidence.evidence_url} rel="noreferrer" target="_blank">
            {evidence.evidence_title}
          </a>
          <p className="mt-1 break-words text-[12px] leading-relaxed text-muted-foreground">{evidence.evidence_summary}</p>
          <p className="mt-2 break-words font-mono text-[10.5px] text-muted-foreground">
            {evidence.evidence_kind} · {evidence.performer_attribution}
            {evidence.claimed_language_code ? ` · ${evidence.claimed_language_code}` : ''}
          </p>
        </article>
      ))}
    </div>
  )
}

function ArtistLanguageReviewDialogContent({
  open,
  review,
  onOpenChange,
}: ArtistLanguageReviewDialogProps) {
  useChineseTextVersion()
  const [classification, setClassification] = useState<LanguageClassification>(
    review?.source?.classification ?? 'single_language',
  )
  const [primaryLanguageCode, setPrimaryLanguageCode] = useState(
    review?.source?.primary_language_code ?? '',
  )
  const [languageVariant, setLanguageVariant] = useState(
    review?.source?.language_variant ?? '',
  )
  const [evidence, setEvidence] = useState<EvidenceDraft[]>(() =>
    review ? evidenceFromReview(review) : [blankEvidence(0)],
  )
  const [resolutionNote, setResolutionNote] = useState(review?.resolution_note ?? '')
  const [error, setError] = useState<string | null>(null)

  const saveSource = useSaveArtistLanguageSource(review?.review_id ?? 0)
  const decideReview = useDecideArtistLanguageReview(review?.review_id ?? 0)

  const terminal = review?.status !== 'open'
  const hasSuggestedSource = review?.suggested_source_id != null
  const startedEvidence = useMemo(() => evidence.filter(isEvidenceStarted), [evidence])
  const candidateReady = useMemo(() => {
    if (startedEvidence.some((row) => !isEvidenceComplete(row))) return false
    return classification !== 'single_language' || Boolean(primaryLanguageCode.trim())
  }, [classification, primaryLanguageCode, startedEvidence])
  const approvalReady = useMemo(() => {
    if (!resolutionNote.trim() || !startedEvidence.length) return false
    if (startedEvidence.some((row) => !isEvidenceComplete(row))) return false
    if (classification === 'single_language') {
      const sourceCode = primaryLanguageCode.trim().toLowerCase()
      const sourceVariant = languageVariant.trim().toLowerCase()
      return Boolean(sourceCode)
        && startedEvidence.some((row) => {
          const claimCode = row.claimed_language_code?.trim().toLowerCase()
          const claimVariant = row.claimed_language_variant?.trim().toLowerCase() ?? ''
          return claimCode === sourceCode && (!sourceVariant || claimVariant === sourceVariant)
        })
    }
    if (classification === 'instrumental') {
      return startedEvidence.some((row) => row.performer_attribution === 'artist_instrumental_confirmed')
    }
    const claims = new Set(
      startedEvidence
        .filter((row) => row.claimed_language_code?.trim())
        .map((row) => `${row.claimed_language_code?.trim()}:${row.claimed_language_variant?.trim() ?? ''}`),
    )
    return claims.size >= 2
  }, [classification, languageVariant, primaryLanguageCode, resolutionNote, startedEvidence])

  const busy = saveSource.isPending || decideReview.isPending
  const decisionReady = Boolean(resolutionNote.trim())
  const rejectReady = decisionReady && (hasSuggestedSource || candidateReady)

  const updateEvidence = (index: number, value: EvidenceDraft) => {
    setEvidence((rows) => rows.map((row, rowIndex) => rowIndex === index ? value : row))
  }

  const decide = async (action: ArtistLanguageReviewAction) => {
    if (!review) return
    setError(null)
    try {
      if (action === 'approve' || (action === 'reject' && !hasSuggestedSource)) {
        await saveSource.mutateAsync({
          classification,
          primary_language_code: classification === 'single_language' ? primaryLanguageCode.trim() : null,
          language_variant: classification === 'single_language' ? languageVariant.trim() || null : null,
          evidence: startedEvidence.map((row) => compactEvidence(row, classification)),
        })
      }
      await decideReview.mutateAsync({ action, resolution_note: resolutionNote.trim() })
      onOpenChange(false)
    } catch (caught) {
      setError(readableError(caught))
    }
  }

  return (
    <Dialog onOpenChange={(nextOpen) => onOpenChange(nextOpen)} open={open}>
      <DialogContent className="max-w-3xl gap-5 overflow-x-hidden p-4 sm:p-6">
        <DialogHeader>
          <DialogTitle className="break-words">审核 {review?.artist_name ? displayName(review.artist_name) : '艺人语言事实'}</DialogTitle>
          <DialogDescription className="break-words">
            {review ? `${review.play_hours_snapshot.toFixed(1)}h 播放 · 仅批准有可审计证据的艺人级结论。` : '选择艺人后开始审核。'}
          </DialogDescription>
        </DialogHeader>

        {!review ? (
          <p className="text-[13px] text-muted-foreground">没有可显示的审核记录。</p>
        ) : terminal ? (
          <ReadonlyReview review={review} />
        ) : (
          <TooltipProvider>
            <div className="space-y-5">
              {review.pre_review_recommendation && (
                <div className="rounded-[8px] border border-accent-foreground/20 bg-accent-foreground/5 px-3 py-2.5 text-[12px] leading-relaxed">
                  <p className="font-semibold text-accent-foreground">
                    Codex 预审：{review.pre_review_recommendation}
                    {review.pre_review_confidence != null ? ` · ${Math.round(review.pre_review_confidence * 100)}%` : ''}
                  </p>
                  {review.pre_review_note && <p className="mt-1 break-words text-muted-foreground">{review.pre_review_note}</p>}
                </div>
              )}
              <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-3">
                <Field label="分类">
                  <Select
                    onValueChange={(value) => setClassification(value as LanguageClassification)}
                    value={classification}
                  >
                    <SelectTrigger aria-label="语言分类" className="w-full">
                      <SelectValue>
                        {CLASSIFICATIONS.find((option) => option.value === classification)?.label}
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      {CLASSIFICATIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                {classification === 'single_language' && (
                  <>
                    <Field label="主要语言代码">
                      <input
                        aria-label="主要语言代码"
                        className="h-8 w-full min-w-0 rounded-[8px] border border-input bg-background px-2.5 text-[12.5px] outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
                        onChange={(event) => setPrimaryLanguageCode(event.target.value)}
                        placeholder="如 en、zh"
                        value={primaryLanguageCode}
                      />
                    </Field>
                    <Field label="语言变体">
                      <input
                        aria-label="语言变体"
                        className="h-8 w-full min-w-0 rounded-[8px] border border-input bg-background px-2.5 text-[12.5px] outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
                        onChange={(event) => setLanguageVariant(event.target.value)}
                        placeholder="可选"
                        value={languageVariant}
                      />
                    </Field>
                  </>
                )}
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-[13px] font-semibold text-foreground">证据</h3>
                  <Tooltip>
                    <TooltipTrigger
                      render={
                        <Button
                          aria-label="添加证据"
                          onClick={() => setEvidence((rows) => [...rows, blankEvidence(rows.length)])}
                          size="icon-sm"
                          title="添加证据"
                          type="button"
                          variant="outline"
                        />
                      }
                    >
                      <Plus />
                    </TooltipTrigger>
                    <TooltipContent>添加一条证据</TooltipContent>
                  </Tooltip>
                </div>
                {evidence.map((row, index) => (
                  <EvidenceEditor
                    canRemove={evidence.length > 1}
                    classification={classification}
                    evidence={row}
                    index={index}
                    key={row.client_id}
                    onChange={(value) => updateEvidence(index, value)}
                    onRemove={() => setEvidence((rows) => rows.filter((_, rowIndex) => rowIndex !== index))}
                  />
                ))}
              </div>

              <Field label="审核说明">
                <textarea
                  aria-label="审核说明"
                  className="min-h-20 w-full min-w-0 resize-y rounded-[8px] border border-input bg-background px-3 py-2 text-[12.5px] leading-relaxed outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
                  onChange={(event) => setResolutionNote(event.target.value)}
                  placeholder="记录批准、拒绝或证据不足的原因"
                  value={resolutionNote}
                />
              </Field>

              {error && (
                <p className="break-words rounded-[8px] bg-destructive/10 px-3 py-2 text-[12.5px] text-destructive" role="alert">
                  {error}
                </p>
              )}

              <DialogFooter className="border-t border-border/70 pt-4">
                <Button
                  aria-label="证据不足"
                  disabled={!decisionReady || busy}
                  onClick={() => void decide('insufficient_evidence')}
                  variant="ghost"
                >
                  证据不足
                </Button>
                <Button
                  aria-label="拒绝候选"
                  disabled={!rejectReady || busy}
                  onClick={() => void decide('reject')}
                  variant="destructive"
                >
                  拒绝
                </Button>
                <Button
                  aria-label="批准审核"
                  disabled={!approvalReady || busy}
                  onClick={() => void decide('approve')}
                >
                  批准
                </Button>
              </DialogFooter>
            </div>
          </TooltipProvider>
        )}
      </DialogContent>
    </Dialog>
  )
}

export function ArtistLanguageReviewDialog(props: ArtistLanguageReviewDialogProps) {
  return (
    <ArtistLanguageReviewDialogContent
      {...props}
      key={`${props.review?.review_id ?? 'none'}:${props.open ? 'open' : 'closed'}`}
    />
  )
}
