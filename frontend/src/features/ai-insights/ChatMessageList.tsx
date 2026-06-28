import ReactMarkdown from 'react-markdown'
import rehypeSanitize from 'rehype-sanitize'
import { Calendar, RefreshCw, X } from 'lucide-react'
import { AIEvidenceCards } from '@/features/ai-tasks/AIEvidenceCards'
import { AITaskProgress } from '@/features/ai-tasks/AITaskProgress'
import { AIToolTrace } from '@/features/ai-tasks/AIToolTrace'
import type { ChatMessage, ReportType } from '@/types/ai-insights'
import type { AiTaskEvent, AiTaskRun, AiToolCall } from '@/types/ai-tasks'
import { REPORT_LABELS } from './aiInsightsData'

function formatDateRange(start: string | null, end: string | null): string {
  if (!start && !end) return ''
  if (start && end) return `${start} ~ ${end}`
  if (start) return start
  return end || ''
}

function periodLabel(periodInfo: string | null): string {
  if (!periodInfo || periodInfo === 'lifetime') return '全部数据'
  if (periodInfo === 'custom') return '指定范围'
  return periodInfo
}

interface Props {
  messages: ChatMessage[]
  asking: boolean
  activeTask?: {
    task: AiTaskRun | null
    events: AiTaskEvent[]
    toolCalls: AiToolCall[]
  }
  retryingIdx: number | null
  reportContext?: ReportType
  onRetry: (idx: number) => void
  onCancel: () => void
  bottomRef: React.RefObject<HTMLDivElement | null>
}

export function ChatMessageList({
  messages,
  asking,
  activeTask,
  retryingIdx,
  reportContext,
  onRetry,
  onCancel,
  bottomRef,
}: Props) {
  const hasMessages = messages.length > 0

  return (
    <div className="min-h-[320px] max-h-[460px] overflow-y-auto">
      {!hasMessages && (
        <div className="flex flex-col items-center justify-center gap-3 py-20 text-center select-none">
          <div className="font-serif text-[56px] italic leading-none text-muted-foreground/[0.07]">
            AI
          </div>
          <p className="text-[14px] text-muted-foreground/60">
            {reportContext
              ? `基于${REPORT_LABELS[reportContext]}内容继续提问`
              : '向我提问，了解你的听歌数据'}
          </p>
        </div>
      )}

      {hasMessages && (
        <div className="px-4 pt-4 space-y-4">
          {messages.map((msg, i) => (
            <div key={i}>
              {msg.role === 'error' ? (
                <div className="flex justify-start">
                  <div className="flex items-center gap-3 rounded-r-2xl border-l-2 border-destructive/30 bg-destructive/[0.04] backdrop-blur-[8px] px-4 py-2.5">
                    <span className="text-[13px] text-destructive/80">
                      {msg.meta?.error || '回答生成失败'}
                    </span>
                    <button
                      onClick={() => onRetry(i)}
                      disabled={retryingIdx !== null}
                      className="flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[1px] text-destructive/80 transition-opacity hover:opacity-70 disabled:opacity-40"
                    >
                      <RefreshCw
                        className={`h-3 w-3 ${retryingIdx === i ? 'animate-spin' : ''}`}
                      />
                      重试
                    </button>
                  </div>
                </div>
              ) : (
                <div
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {msg.role === 'user' ? (
                    <div className="max-w-[80%] rounded-2xl border border-border/60 bg-accent-foreground/[0.06] backdrop-blur-[8px] px-4 py-2.5 text-[13px] leading-relaxed text-foreground/85">
                      {msg.content}
                    </div>
                  ) : (
                    <div className="max-w-[80%] rounded-r-2xl border-l-2 border-accent-foreground/20 bg-card/40 backdrop-blur-[8px] px-4 py-3">
                      {msg.meta?.period_info && (
                        <div className="mb-2 flex items-center gap-1 text-[10px] text-muted-foreground/40">
                          <Calendar className="h-2.5 w-2.5" />
                          <span>{periodLabel(msg.meta.period_info ?? null)}</span>
                          {formatDateRange(msg.meta.start_date ?? null, msg.meta.end_date ?? null) && (
                            <span>· {formatDateRange(msg.meta.start_date ?? null, msg.meta.end_date ?? null)}</span>
                          )}
                        </div>
                      )}
                      <div className="prose prose-sm max-w-none text-[13px] leading-relaxed [&_strong]:text-foreground">
                        <ReactMarkdown rehypePlugins={[rehypeSanitize]}>
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                      {msg.meta?.evidence_cards && msg.meta.evidence_cards.length > 0 && (
                        <div className="mt-3">
                          <AIEvidenceCards cards={msg.meta.evidence_cards} />
                        </div>
                      )}
                      {msg.meta?.tool_calls && msg.meta.tool_calls.length > 0 && (
                        <div className="mt-3">
                          <AIToolTrace toolCalls={msg.meta.tool_calls} />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}

          {asking && (
            <div className="flex justify-start">
              <div className="max-w-[80%] space-y-3 rounded-r-2xl border-l-2 border-accent-foreground/20 bg-card/40 backdrop-blur-[8px] px-4 py-3">
                <AITaskProgress task={activeTask?.task ?? null} events={activeTask?.events ?? []} />
                <AIToolTrace toolCalls={activeTask?.toolCalls ?? []} />
                <button
                  onClick={onCancel}
                  className="flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.6px] text-muted-foreground/40 transition-colors hover:text-destructive"
                >
                  <X className="h-3 w-3" />
                  取消
                </button>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      )}
    </div>
  )
}
