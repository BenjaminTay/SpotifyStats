import ReactMarkdown from 'react-markdown'
import rehypeSanitize from 'rehype-sanitize'

import { ReportSkeleton } from './ReportSkeleton'
import { AiDisclaimer, ErrorState } from './AiInsightsPrimitives'

interface ReportCardProps {
  title: string
  report: string | null
  cached: boolean
  loading: boolean
  error: string | null
  onRetry: () => void
}

export function ReportCard({ title, report, cached, loading, error, onRetry }: ReportCardProps) {
  if (loading && !report) return <ReportSkeleton />
  if (error) return <ErrorState message={error} onRetry={onRetry} />
  if (!report) return <ReportSkeleton />

  return (
    <div className="rounded-[16px] border border-border bg-card/40 p-6 backdrop-blur-[12px]">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-serif text-[22px] font-bold">{title}</h2>
        <div className="flex items-center gap-2">
          {cached && (
            <span className="text-[11px] text-muted-foreground/60">缓存</span>
          )}
          {loading && (
            <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-muted-foreground" />
          )}
          <button
            onClick={onRetry}
            disabled={loading}
            className="text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
          >
            重新生成
          </button>
        </div>
      </div>

      <div className="prose prose-sm max-w-none text-[14px] leading-relaxed text-muted-foreground [&_h2]:font-serif [&_h2]:text-[18px] [&_h2]:font-semibold [&_h2]:text-foreground [&_strong]:text-foreground">
        <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{report}</ReactMarkdown>
      </div>

      <div className="mt-6">
        <AiDisclaimer />
      </div>
    </div>
  )
}
