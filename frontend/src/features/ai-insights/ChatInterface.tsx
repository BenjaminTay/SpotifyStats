import { useState, useCallback, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import rehypeSanitize from 'rehype-sanitize'
import { ArrowLeft, Calendar, RefreshCw, Send, Sparkles, X } from 'lucide-react'

import { CancelError } from '@/api/errors'
import {
  useAskQuestion,
  useChatSession,
  useCreateSession,
  useAddMessage,
  useSuggestedQuestions,
} from '@/hooks/useAiInsights'
import { SuggestedQuestions } from './SuggestedQuestions'
import { AiDisclaimer } from './AiInsightsPrimitives'
import { REPORT_LABELS } from './aiInsightsData'
import type { AskResponse, ChatMessage, ChatMessageRecord, ReportType } from '@/types/ai-insights'

interface Props {
  initialQuestion?: string | null
  onQuestionConsumed?: () => void
  reportContext?: ReportType
  reportContextLabel?: string
  onBackToReport?: () => void
  /** Active session ID — null means a fresh unsaved conversation. */
  sessionId: number | null
  /** Called when a new session is created from the first sent message. */
  onSessionCreated: (id: number) => void
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

function recordToMessage(r: ChatMessageRecord): ChatMessage {
  const msg: ChatMessage = { role: r.role, content: r.content }
  if (r.meta_json) {
    try {
      msg.meta = JSON.parse(r.meta_json) as AskResponse
    } catch { /* ignore parse errors */ }
  }
  return msg
}

function messageToMetaJson(m: ChatMessage): string | undefined {
  return m.meta ? JSON.stringify(m.meta) : undefined
}

export function ChatInterface({
  initialQuestion,
  onQuestionConsumed,
  reportContext,
  reportContextLabel,
  onBackToReport,
  sessionId,
  onSessionCreated,
}: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [retryingIdx, setRetryingIdx] = useState<number | null>(null)
  const [sessionError, setSessionError] = useState<string | null>(null)
  const { ask, asking, cancel } = useAskQuestion()
  const { questions, isLoading: questionsLoading } = useSuggestedQuestions(reportContext)
  const bottomRef = useRef<HTMLDivElement>(null)
  const loadedSessionRef = useRef<number | null>(null)
  const justCreatedRef = useRef(false)
  const ignoreInitialRef = useRef(false)

  // Persistence mutations
  const createSession = useCreateSession()
  const addMessage = useAddMessage()

  // Load session messages when switching to a saved session (not when just created)
  const { data: loadedSession } = useChatSession(
    sessionId !== null && sessionId !== loadedSessionRef.current && !justCreatedRef.current
      ? sessionId
      : null,
  )

  useEffect(() => {
    if (!loadedSession || loadedSession.id !== sessionId) return
    if (loadedSession.id === loadedSessionRef.current) return
    loadedSessionRef.current = loadedSession.id
    ignoreInitialRef.current = true
    const restored = loadedSession.messages.map(recordToMessage)
    setMessages(restored)
  }, [loadedSession, sessionId])

  // Reset when switching to a new (null) session or when sessionId changes externally
  useEffect(() => {
    if (sessionId === null) {
      loadedSessionRef.current = null
      justCreatedRef.current = false
      ignoreInitialRef.current = false
      setMessages([])
      setInput('')
      setSessionError(null)
    }
  }, [sessionId])

  // Handle external follow-up question from reports
  useEffect(() => {
    if (initialQuestion && !ignoreInitialRef.current) {
      onQuestionConsumed?.()
      handleSendWith(initialQuestion)
    }
    ignoreInitialRef.current = false
  }, [initialQuestion]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Save helper ──────────────────────────────────────────────────────────

  const saveMessage = useCallback(
    async (sid: number | null, role: string, content: string, metaJson?: string) => {
      if (sid !== null) {
        addMessage.mutate({ sessionId: sid, role, content, metaJson })
      }
    },
    [addMessage],
  )

  // ── Core send ────────────────────────────────────────────────────────────

  const sendQuestion = useCallback(
    async (question: string, currentSid: number | null) => {
      const history = messages
        .filter((m) => m.role !== 'error')
        .slice(-5)

      try {
        const result = await ask({ question, conversation_history: history })
        const assistantMsg: ChatMessage = { role: 'assistant', content: result.answer, meta: result }
        setMessages((prev) => [...prev, assistantMsg])
        saveMessage(currentSid, 'assistant', result.answer, messageToMetaJson(assistantMsg))
      } catch (err) {
        if (err instanceof CancelError) return
        if (err instanceof DOMException && err.name === 'AbortError') return
        const msg = err instanceof Error ? err.message : '回答生成失败'
        const errorMsg: ChatMessage = {
          role: 'error',
          content: question,
          meta: { success: false, answer: '', error: msg, period_info: null, start_date: null, end_date: null },
        }
        setMessages((prev) => [...prev, errorMsg])
        saveMessage(currentSid, 'error', question, messageToMetaJson(errorMsg))
      }
    },
    [ask, messages, saveMessage],
  )

  const handleSend = async () => {
    const q = input.trim()
    if (!q || asking) return
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: q }])

    let sid = sessionId
    if (sid === null) {
      try {
        const result = await createSession.mutateAsync(undefined)
        if (result.success && result.data) {
          sid = result.data.id
          loadedSessionRef.current = sid
          justCreatedRef.current = true
          setSessionError(null)
          onSessionCreated(sid)
        } else {
          setSessionError('创建会话失败，请稍后重试')
          return
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : '创建会话失败'
        console.error('创建会话失败:', err)
        setSessionError(msg)
        return
      }
    }

    if (sid !== null) {
      saveMessage(sid, 'user', q)
    }

    await sendQuestion(q, sid)
  }

  const handleSendWith = async (question: string) => {
    if (!question.trim() || asking) return
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: question }])

    let sid = sessionId
    if (sid === null) {
      try {
        const result = await createSession.mutateAsync(undefined)
        if (result.success && result.data) {
          sid = result.data.id
          loadedSessionRef.current = sid
          justCreatedRef.current = true
          setSessionError(null)
          onSessionCreated(sid)
        } else {
          setSessionError('创建会话失败，请稍后重试')
          return
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : '创建会话失败'
        console.error('创建会话失败:', err)
        setSessionError(msg)
        return
      }
    }

    if (sid !== null) {
      saveMessage(sid, 'user', question)
    }

    await sendQuestion(question, sid)
  }

  const handleRetry = async (idx: number) => {
    const msg = messages[idx]
    if (!msg || msg.role !== 'error') return

    setRetryingIdx(idx)
    setMessages((prev) => prev.filter((_, i) => i !== idx))
    await sendQuestion(msg.content, sessionId)
    setRetryingIdx(null)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      handleSend()
    }
  }

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, asking])

  const hasMessages = messages.length > 0

  return (
    <div className="flex flex-col gap-4">
      {/* Report context badge */}
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

      {/* Unified glass panel */}
      <div className="rounded-[16px] border border-border bg-card/30 backdrop-blur-[12px] overflow-hidden">
        {/* Messages area */}
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
                          onClick={() => handleRetry(i)}
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
                              <span>{periodLabel(msg.meta.period_info)}</span>
                              {formatDateRange(msg.meta.start_date, msg.meta.end_date) && (
                                <span>· {formatDateRange(msg.meta.start_date, msg.meta.end_date)}</span>
                              )}
                            </div>
                          )}
                          <div className="prose prose-sm max-w-none text-[13px] leading-relaxed [&_strong]:text-foreground">
                            <ReactMarkdown rehypePlugins={[rehypeSanitize]}>
                              {msg.content}
                            </ReactMarkdown>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}

              {/* Loading shimmer */}
              {asking && (
                <div className="flex justify-start">
                  <div className="max-w-[65%] rounded-r-2xl border-l-2 border-accent-foreground/20 bg-card/40 backdrop-blur-[8px] px-4 py-3">
                    <div className="flex items-center gap-2.5">
                      <Sparkles className="h-3.5 w-3.5 animate-pulse text-muted-foreground/50" />
                      <span className="text-[12px] text-muted-foreground/60">AI 正在分析你的听歌数据</span>
                    </div>
                    <div className="mt-2.5 h-1 w-full rounded-full bg-muted/20 overflow-hidden">
                      <div className="h-full w-2/5 rounded-full bg-gradient-to-r from-transparent via-accent-foreground/10 to-transparent animate-pulse" />
                    </div>
                    <button
                      onClick={cancel}
                      className="mt-2.5 flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.6px] text-muted-foreground/30 transition-colors hover:text-destructive"
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

        {/* Session error */}
        {sessionError && (
          <div className="border-t border-destructive/20 px-4 py-2.5">
            <div className="flex items-center gap-2 text-[12px] text-destructive/80">
              <span>{sessionError}</span>
              <button
                onClick={() => setSessionError(null)}
                className="ml-auto rounded-full p-0.5 text-destructive/50 hover:text-destructive"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          </div>
        )}

        {/* Suggested questions — inside the panel */}
        {!asking && (
          <div className="border-t border-border/40 px-4 py-3">
            <SuggestedQuestions
              questions={questions}
              onSelect={(q) => handleSendWith(q)}
              disabled={asking}
              isLoading={questionsLoading}
            />
          </div>
        )}

        {/* Input — embedded at bottom */}
        <div className="border-t border-border/40 px-4 py-3">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入问题，如「我今年听最多的艺人是谁？」"
              disabled={asking}
              maxLength={500}
              className="flex-1 rounded-full border border-border/60 bg-card/30 px-4 py-2.5 text-[13px] text-foreground placeholder:text-muted-foreground/40 backdrop-blur-[8px] outline-none transition-colors focus:border-accent-foreground/20 disabled:opacity-40"
            />
            <button
              onClick={handleSend}
              disabled={asking || !input.trim()}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent-foreground text-card transition-opacity hover:opacity-85 disabled:opacity-30"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      <AiDisclaimer />
    </div>
  )
}
