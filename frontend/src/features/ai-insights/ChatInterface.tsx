import { useState, useCallback, useEffect, useRef } from 'react'
import { ArrowLeft, Send, X } from 'lucide-react'

import { CancelError } from '@/api/errors'
import {
  useAskQuestion,
  useChatSession,
  useCreateSession,
  useAddMessage,
  useSuggestedQuestions,
} from '@/hooks/useAiInsights'
import { SuggestedQuestions } from './SuggestedQuestions'
import { ChatMessageList } from './ChatMessageList'
import { AiDisclaimer } from './AiInsightsPrimitives'
import type { AskResponse, ChatMessage, ChatMessageRecord, ReportType } from '@/types/ai-insights'

interface Props {
  initialQuestion?: string | null
  onQuestionConsumed?: () => void
  reportContext?: ReportType
  reportContextLabel?: string
  onBackToReport?: () => void
  sessionId: number | null
  onSessionCreated: (id: number) => void
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

  const createSession = useCreateSession()
  const addMessage = useAddMessage()

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

  useEffect(() => {
    if (initialQuestion && !ignoreInitialRef.current) {
      onQuestionConsumed?.()
      handleSendWith(initialQuestion)
    }
    ignoreInitialRef.current = false
  }, [initialQuestion]) // eslint-disable-line react-hooks/exhaustive-deps

  const saveMessage = useCallback(
    async (sid: number | null, role: string, content: string, metaJson?: string) => {
      if (sid !== null) {
        addMessage.mutate({ sessionId: sid, role, content, metaJson })
      }
    },
    [addMessage],
  )

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
        <ChatMessageList
          messages={messages}
          asking={asking}
          retryingIdx={retryingIdx}
          reportContext={reportContext}
          onRetry={handleRetry}
          onCancel={cancel}
          bottomRef={bottomRef}
        />

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
              aria-label="发送问题"
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
