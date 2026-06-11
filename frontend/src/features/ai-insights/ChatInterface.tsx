import { useState, useCallback, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import rehypeSanitize from 'rehype-sanitize'
import { ArrowLeft, Calendar, Eraser, RefreshCw, Send, Sparkles, X } from 'lucide-react'

import { CancelError } from '@/api/errors'
import { useAskQuestion, useSuggestedQuestions } from '@/hooks/useAiInsights'
import { SuggestedQuestions } from './SuggestedQuestions'
import { AiDisclaimer } from './AiInsightsPrimitives'
import { REPORT_LABELS } from './aiInsightsData'
import type { ChatMessage, ReportType } from '@/types/ai-insights'

interface Props {
  initialQuestion?: string | null
  onQuestionConsumed?: () => void
  reportContext?: ReportType
  reportContextLabel?: string
  onBackToReport?: () => void
  onClear?: () => void
}

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

export function ChatInterface({ initialQuestion, onQuestionConsumed, reportContext, reportContextLabel, onBackToReport, onClear }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [retryingIdx, setRetryingIdx] = useState<number | null>(null)
  const [showClearConfirm, setShowClearConfirm] = useState(false)
  const { ask, asking, cancel } = useAskQuestion()
  const { questions, isLoading: questionsLoading } = useSuggestedQuestions(reportContext)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Handle external follow-up question from reports
  useEffect(() => {
    if (initialQuestion) {
      onQuestionConsumed?.()
      handleSendWith(initialQuestion)
    }
  }, [initialQuestion]) // eslint-disable-line react-hooks/exhaustive-deps

  const sendQuestion = useCallback(
    async (question: string) => {
      const history = messages
        .filter((m) => m.role !== 'error')
        .slice(-5)

      try {
        const result = await ask({ question, conversation_history: history })
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: result.answer, meta: result },
        ])
      } catch (err) {
        // User cancelled — don't show error
        if (err instanceof CancelError) return
        if (err instanceof DOMException && err.name === 'AbortError') return
        const msg = err instanceof Error ? err.message : '回答生成失败'
        setMessages((prev) => [...prev, { role: 'error', content: question, meta: { success: false, answer: '', error: msg, period_info: null, start_date: null, end_date: null } }])
      }
    },
    [ask, messages],
  )

  const handleSend = async () => {
    const q = input.trim()
    if (!q || asking) return
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: q }])
    await sendQuestion(q)
  }

  const handleSendWith = async (question: string) => {
    if (!question.trim() || asking) return
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: question }])
    await sendQuestion(question)
  }

  const handleRetry = async (idx: number) => {
    const msg = messages[idx]
    if (!msg || msg.role !== 'error') return

    setRetryingIdx(idx)
    setMessages((prev) => prev.filter((_, i) => i !== idx))
    await sendQuestion(msg.content)
    setRetryingIdx(null)
  }

  const handleClearRequest = () => {
    setShowClearConfirm(true)
  }

  const handleClearConfirm = () => {
    setMessages([])
    setInput('')
    setShowClearConfirm(false)
    onClear?.()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, asking])

  return (
    <div className="flex flex-col gap-4">
      {/* Report context badge — shown when user came from a report follow-up */}
      {reportContext && reportContextLabel && (
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card/60 px-3 py-1 text-[11px] text-muted-foreground backdrop-blur-[4px]">
            {reportContextLabel}
          </span>
          {onBackToReport && (
            <button
              onClick={onBackToReport}
              className="flex items-center gap-1 rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.6px] text-muted-foreground/50 transition-colors hover:text-foreground"
            >
              <ArrowLeft className="h-3 w-3" />
              返回报告
            </button>
          )}
        </div>
      )}

      {/* Chat messages */}
      <div className="min-h-[300px] max-h-[500px] overflow-y-auto space-y-4 rounded-[16px] border border-border bg-card/40 p-4 backdrop-blur-[12px]">
        {messages.length === 0 && (
          <div className="flex flex-col items-center gap-2 py-12 text-center">
            <p className="text-[14px] text-muted-foreground">
              {reportContext
                ? `基于${REPORT_LABELS[reportContext]}内容继续提问`
                : '向我提问，了解你的听歌数据'}
            </p>
          </div>
        )}

        {messages.length > 0 && (
          <div className="mb-3 flex justify-end">
            {showClearConfirm ? (
              <div className="flex items-center gap-2 rounded-full border border-border bg-card/60 px-3 py-1">
                <span className="text-[11px] text-muted-foreground">确定清除对话？</span>
                <button
                  onClick={handleClearConfirm}
                  className="text-[11px] font-semibold text-destructive hover:opacity-70"
                >
                  确定
                </button>
                <button
                  onClick={() => setShowClearConfirm(false)}
                  className="text-[11px] text-muted-foreground hover:text-foreground"
                >
                  取消
                </button>
              </div>
            ) : (
              <button
                onClick={handleClearRequest}
                disabled={asking}
                className="flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.6px] text-muted-foreground/50 transition-colors hover:text-muted-foreground disabled:opacity-40"
              >
                <Eraser className="h-3 w-3" />
                新对话
              </button>
            )}
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i}>
            {msg.role === 'error' ? (
              <div className="flex justify-start">
                <div className="flex items-center gap-3 rounded-2xl bg-destructive/10 px-4 py-2.5">
                  <span className="text-[13px] text-destructive">
                    {msg.meta?.error || '回答生成失败'}
                  </span>
                  <button
                    onClick={() => handleRetry(i)}
                    disabled={retryingIdx !== null}
                    className="flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[1px] text-destructive transition-opacity hover:opacity-70 disabled:opacity-40"
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
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-[13px] leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-accent-foreground text-card'
                      : 'bg-muted/50 text-muted-foreground'
                  }`}
                >
                  {msg.role === 'user' ? (
                    msg.content
                  ) : (
                    <div>
                      {/* Time range badge */}
                      {msg.meta?.period_info && (
                        <div className="mb-2 flex items-center gap-1 text-[10px] text-muted-foreground/50">
                          <Calendar className="h-2.5 w-2.5" />
                          <span>{periodLabel(msg.meta.period_info)}</span>
                          {formatDateRange(msg.meta.start_date, msg.meta.end_date) && (
                            <span>· {formatDateRange(msg.meta.start_date, msg.meta.end_date)}</span>
                          )}
                        </div>
                      )}
                      <div className="prose prose-sm max-w-none text-[13px] [&_strong]:text-foreground">
                        <ReactMarkdown rehypePlugins={[rehypeSanitize]}>
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}

        {asking && (
          <div className="flex justify-start">
            <div className="flex items-center gap-3 rounded-2xl bg-muted/50 px-4 py-3">
              <Sparkles className="h-3.5 w-3.5 animate-pulse text-muted-foreground/60" />
              <span className="text-[12px] text-muted-foreground/70">AI 正在分析你的听歌数据</span>
              <span className="inline-flex gap-1">
                <span className="h-1 w-1 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:0ms]" />
                <span className="h-1 w-1 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:150ms]" />
                <span className="h-1 w-1 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:300ms]" />
              </span>
              <button
                onClick={cancel}
                className="ml-1 flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.6px] text-muted-foreground/40 transition-colors hover:text-destructive"
              >
                <X className="h-3 w-3" />
                取消
              </button>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Suggested questions — always visible, click to send directly */}
      <SuggestedQuestions
        questions={questions}
        onSelect={(q) => handleSendWith(q)}
        disabled={asking}
        isLoading={questionsLoading}
      />

      {/* Input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题，如「我今年听最多的艺人是谁？」"
          disabled={asking}
          maxLength={500}
          className="flex-1 rounded-full border border-border bg-card/40 px-4 py-2.5 text-[13px] text-foreground placeholder:text-muted-foreground/50 backdrop-blur-[8px] outline-none transition-colors focus:border-accent-foreground/30 disabled:opacity-50"
        />
        <button
          onClick={handleSend}
          disabled={asking || !input.trim()}
          className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-foreground text-card transition-opacity hover:opacity-85 disabled:opacity-40"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>

      <AiDisclaimer />
    </div>
  )
}
