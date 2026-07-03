import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Check, Clock, Copy, RefreshCw, X } from 'lucide-react'

import { ReportSkeleton } from './ReportSkeleton'
import { AiDisclaimer, ErrorState } from './AiInsightsPrimitives'
import { AiMarkdown } from './AiMarkdown'
import { formatRelativeTimeZh } from '@/lib/datetime'
import type { ReportEntities, ReportType } from '@/types/ai-insights'

interface ReportCardProps {
  title: string
  reportType: ReportType
  report: string | null
  cached: boolean
  cachedAt: string | null
  entities: ReportEntities | null
  metadata?: Record<string, unknown> | null
  loading: boolean
  fetching: boolean
  error: string | null
  onRetry: () => void
  onCancel?: () => void
  onFollowUp?: (question: string, label: string) => void
  showGenerateAction?: boolean
  generateLoading?: boolean
  onGenerate?: () => void
  generateLabel?: string
}

function followUpQuestions(
  reportType: ReportType,
  entities: ReportEntities | null,
): string[] {
  const questions: string[] = []
  const topArtist = entities?.artists[0]
  const topTrack = entities?.tracks[0]

  if (reportType === 'weekly') {
    if (topArtist) questions.push(`${topArtist} 这周表现怎么样？`)
    if (topTrack) questions.push(`我这周听了多少次 ${topTrack}？`)
    if (!questions.length) questions.push('和上周相比我的听歌量有什么变化？')
  } else if (reportType === 'monthly') {
    if (topArtist) questions.push(`这个月我听 ${topArtist} 的风格有什么变化？`)
    questions.push('这个月我的情绪画像是什么？')
  } else if (reportType === 'yearly') {
    if (topArtist) questions.push(`${topArtist} 是我今年最爱的艺人吗？`)
    questions.push('今年我发现了哪些新艺人？')
  }

  return questions.slice(0, 2)
}

export function ReportCard({
  title,
  reportType,
  report,
  cached,
  cachedAt,
  entities,
  metadata,
  loading,
  fetching,
  error,
  onRetry,
  onCancel,
  onFollowUp,
  showGenerateAction = false,
  generateLoading = false,
  onGenerate,
  generateLabel = '生成报告',
}: ReportCardProps) {
  const [copied, setCopied] = useState(false)

  if (loading && !report) return <ReportSkeleton onCancel={onCancel} />
  if (error) return <ErrorState message={error} onRetry={onRetry} />
  if (!report && !loading) {
    if (showGenerateAction && onGenerate) {
      return (
        <div className="rounded-[16px] border border-border bg-card/40 p-6 backdrop-blur-[12px]">
          <div className="flex flex-col items-center gap-4 py-12 text-center">
            <div className="space-y-1">
              <h2 className="font-serif text-[22px] font-bold">{title}</h2>
              <p className="text-[13px] text-muted-foreground/60">
                当前范围还没有缓存报告
              </p>
            </div>
            <button
              onClick={onGenerate}
              disabled={generateLoading}
              className="inline-flex items-center gap-2 rounded-full bg-accent-foreground px-5 py-2 text-[12px] font-semibold uppercase tracking-[0.8px] text-card transition-opacity hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${generateLoading ? 'animate-spin' : ''}`} />
              {generateLabel}
            </button>
          </div>
        </div>
      )
    }
    return (
      <div className="rounded-[16px] border border-border bg-card/40 p-6 backdrop-blur-[12px] flex items-center justify-center py-16">
        <p className="text-[13px] text-muted-foreground/60">该时间段暂无听歌数据</p>
      </div>
    )
  }
  if (!report) return <ReportSkeleton />

  const timeAgo = formatRelativeTimeZh(cachedAt)
  const suggestions = onFollowUp ? followUpQuestions(reportType, entities) : []
  const reportMode = typeof metadata?.report_mode === 'string' ? metadata.report_mode : null
  const fallbackLevel = typeof metadata?.fallback_level === 'string' ? metadata.fallback_level : null
  const criticPassed = typeof metadata?.critic_passed === 'boolean' ? metadata.critic_passed : null
  const articleLength = typeof metadata?.article_length === 'number' ? metadata.article_length : null

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(report)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      const ta = document.createElement('textarea')
      ta.value = report
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="rounded-[16px] border border-border bg-card/40 p-6 backdrop-blur-[12px]">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-serif text-[22px] font-bold">{title}</h2>
        <div className="flex items-center gap-2">
          {cached && timeAgo && (
            <span className="flex items-center gap-1 text-[11px] text-muted-foreground/50">
              <Clock className="h-3 w-3" />
              {timeAgo}
            </span>
          )}
          {fetching && report && onCancel && (
            <button
              onClick={onCancel}
              className="flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.6px] text-muted-foreground/50 transition-colors hover:text-destructive"
            >
              <X className="h-3 w-3" />
              取消
            </button>
          )}
          {fetching && report && !onCancel && (
            <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-muted-foreground" />
          )}
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground/50 transition-colors hover:text-muted-foreground"
          >
            {copied ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3" />}
            {copied ? '已复制' : '复制'}
          </button>
          <button
            onClick={onRetry}
            disabled={fetching}
            className="flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
          >
            <RefreshCw className={`h-3 w-3 ${fetching ? 'animate-spin' : ''}`} />
            刷新报告
          </button>
        </div>
      </div>

      {metadata && (
        <div className="mb-4 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
          {reportMode === 'agentic_longform' && (
            <span className="rounded-full border border-border bg-card/60 px-2 py-0.5">
              Agentic 长文
            </span>
          )}
          {criticPassed !== null && (
            <span className="rounded-full border border-border bg-card/60 px-2 py-0.5">
              {criticPassed ? '已通过编辑审稿' : '审稿后回退'}
            </span>
          )}
          {fallbackLevel && (
            <span className="rounded-full border border-border bg-card/60 px-2 py-0.5">
              基础摘要回退
            </span>
          )}
          {articleLength !== null && (
            <span className="rounded-full border border-border bg-card/60 px-2 py-0.5">
              {articleLength.toLocaleString('zh-CN')} 字
            </span>
          )}
        </div>
      )}

      {/* Report content */}
      <div className="prose prose-sm max-w-none max-h-[600px] overflow-y-auto text-[14px] leading-relaxed text-muted-foreground [&_h2]:font-serif [&_h2]:text-[18px] [&_h2]:font-semibold [&_h2]:text-foreground [&_strong]:text-foreground">
        <AiMarkdown>{report}</AiMarkdown>
      </div>

      {/* Entity links */}
      {entities && (entities.artists.length > 0 || entities.tracks.length > 0) && (
        <div className="mt-5 space-y-2 border-t border-border/50 pt-4">
          {entities.artists.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] font-semibold uppercase tracking-[0.8px] text-muted-foreground/50">
                相关艺人
              </span>
              {entities.artists.map((name) => (
                <Link
                  key={name}
                  to={`/music/artists/${encodeURIComponent(name)}`}
                  className="rounded-full border border-border bg-card/60 px-2.5 py-0.5 text-[11px] text-muted-foreground backdrop-blur-[4px] transition-colors hover:border-accent-foreground/20 hover:text-foreground"
                >
                  {name}
                </Link>
              ))}
            </div>
          )}
          {entities.tracks.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] font-semibold uppercase tracking-[0.8px] text-muted-foreground/50">
                相关歌曲
              </span>
              {entities.tracks.map((name) => (
                <Link
                  key={name}
                  to={`/music/tracks/${encodeURIComponent(name)}`}
                  className="rounded-full border border-border bg-card/60 px-2.5 py-0.5 text-[11px] text-muted-foreground backdrop-blur-[4px] transition-colors hover:border-accent-foreground/20 hover:text-foreground"
                >
                  {name}
                </Link>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Follow-up questions */}
      {suggestions.length > 0 && (
        <div className="mt-5 border-t border-border/50 pt-4">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.8px] text-muted-foreground/50">
            追问
          </p>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((q) => (
              <button
                key={q}
                onClick={() => onFollowUp?.(q, title)}
                className="flex items-center gap-1 rounded-full border border-border bg-card/60 px-3 py-1.5 text-[12px] text-muted-foreground backdrop-blur-[4px] transition-colors hover:border-accent-foreground/20 hover:text-foreground"
              >
                {q}
                <ArrowRight className="h-3 w-3" />
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="mt-6">
        <AiDisclaimer />
      </div>
    </div>
  )
}
