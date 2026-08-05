import { useState, useCallback, useEffect, useMemo, useRef } from 'react'
import { ArrowLeft, X } from 'lucide-react'

import { useChatSession, useCreateSession, useAddMessage, useSuggestedQuestions } from '@/hooks/useAiInsights'
import { useAiTask, useCancelAiTask, useStartChatAgentTask } from '@/hooks/useAiTasks'
import { useSettings } from '@/hooks/useSettings'
import { SuggestedQuestions } from './SuggestedQuestions'
import { ChatMessageList } from './ChatMessageList'
import { ChatComposer } from './ChatComposer'
import { AiDisclaimer } from './AiInsightsPrimitives'
import { buildChatAgentFilterPayload } from './aiTaskFilters'
import { chatAgentMeta, chatMessageToMetaJson, chatTaskAnswer, chatTaskError, recordToChatMessage } from '@/types/ai-insights'
import type { ChatMessage, ReportType } from '@/types/ai-insights'
import type { AiTaskRun } from '@/types/ai-tasks'

interface Props {
  initialQuestion?: string | null
  onQuestionConsumed?: () => void
  reportContext?: ReportType
  reportContextLabel?: string
  onBackToReport?: () => void
  sessionId: number | null
  onSessionCreated: (id: number) => void
}

interface ActiveChatTask {
  taskId: string
  question: string
  sessionId: number | null
}

function isActiveStatus(status: AiTaskRun['status'] | null | undefined): boolean {
  return status === 'queued' || status === 'running'
}

function isTerminalStatus(status: AiTaskRun['status'] | null | undefined): boolean {
  return status === 'done' || status === 'error' || status === 'cancelled'
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
  const [thinkingMode, setThinkingMode] = useState(true)
  const [retryingIdx, setRetryingIdx] = useState<number | null>(null)
  const [sessionError, setSessionError] = useState<string | null>(null)
  const [activeChatTask, setActiveChatTask] = useState<ActiveChatTask | null>(null)
  const { questions, isLoading: questionsLoading } = useSuggestedQuestions(reportContext)
  const bottomRef = useRef<HTMLDivElement>(null)
  const loadedSessionRef = useRef<number | null>(null)
  const justCreatedRef = useRef(false)
  const ignoreInitialRef = useRef(false)
  const handledTaskIdRef = useRef<string | null>(null)

  const createSession = useCreateSession()
  const addMessage = useAddMessage()
  const startChatTask = useStartChatAgentTask()
  const cancelChatTask = useCancelAiTask()
  const { settings } = useSettings()
  const activeTaskState = useAiTask(activeChatTask?.taskId ?? null)
  const activeStatus = activeTaskState.task?.status
  const asking = startChatTask.isPending || isActiveStatus(activeStatus)
  const displayedTask: AiTaskRun | null = activeTaskState.task ?? (startChatTask.isPending
    ? { found: true, status: 'queued', stage: 'starting', progress_pct: 0, message: '正在启动 Agent Chat' }
    : null)

  const { data: loadedSession, isLoading: sessionLoading } = useChatSession(
    sessionId !== null && sessionId !== loadedSessionRef.current && !justCreatedRef.current
      ? sessionId
      : null,
  )

  const chatFilterPayload = useMemo(() => buildChatAgentFilterPayload(settings), [settings])

  const saveMessage = useCallback(
    (sid: number | null, role: string, content: string, metaJson?: string) => {
      if (sid !== null) {
        addMessage.mutate({ sessionId: sid, role, content, metaJson })
      }
    },
    [addMessage],
  )

  const ensureSession = useCallback(async (): Promise<number | null> => {
    if (sessionId !== null) return sessionId
    try {
      const result = await createSession.mutateAsync(undefined)
      if (result.success && result.data) {
        const sid = result.data.id
        loadedSessionRef.current = sid
        justCreatedRef.current = true
        setSessionError(null)
        onSessionCreated(sid)
        return sid
      }
      setSessionError('创建会话失败，请稍后重试')
    } catch (err) {
      const msg = err instanceof Error ? err.message : '创建会话失败'
      console.error('创建会话失败:', err)
      setSessionError(msg)
    }
    return null
  }, [createSession, onSessionCreated, sessionId])

  const startAgentTask = useCallback(
    async (question: string, sid: number | null) => {
      const history = messages
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .slice(-5)
        .map((m) => ({ role: m.role, content: m.content }))

      try {
        handledTaskIdRef.current = null
        const task = await startChatTask.mutateAsync({
          question,
          conversation_history: history,
          question_time: new Date().toISOString(),
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          thinking_mode: thinkingMode,
          ...chatFilterPayload,
        })
        setActiveChatTask({ taskId: task.task_id, question, sessionId: sid })
      } catch (err) {
        const msg = err instanceof Error ? err.message : '回答生成失败'
        const errorMsg: ChatMessage = {
          role: 'error',
          content: question,
          meta: { success: false, answer: '', error: msg, task_id: undefined, result: null, tool_calls: [] },
        }
        setMessages((prev) => [...prev, errorMsg])
        saveMessage(sid, 'error', question, chatMessageToMetaJson(errorMsg))
      }
    },
    [chatFilterPayload, messages, saveMessage, startChatTask, thinkingMode],
  )

  const submitQuestion = useCallback(
    async (question: string, appendUser = true) => {
      const q = question.trim()
      if (!q || asking) return
      setInput('')

      const sid = await ensureSession()
      if (sid === null) {
        // Don't show the message if session creation failed
        return
      }
      if (appendUser) {
        setMessages((prev) => [...prev, { role: 'user', content: q }])
        saveMessage(sid, 'user', q)
      }
      await startAgentTask(q, sid)
    },
    [asking, ensureSession, saveMessage, startAgentTask],
  )

  useEffect(() => {
    if (!loadedSession || loadedSession.id !== sessionId) return
    if (loadedSession.id === loadedSessionRef.current) return
    loadedSessionRef.current = loadedSession.id
    ignoreInitialRef.current = true
    setMessages(loadedSession.messages.map(recordToChatMessage))
  }, [loadedSession, sessionId])

  useEffect(() => {
    if (sessionId === null) {
      loadedSessionRef.current = null
      justCreatedRef.current = false
      ignoreInitialRef.current = false
      setMessages([])
      setInput('')
      setSessionError(null)
      setActiveChatTask(null)
    }
  }, [sessionId])

  useEffect(() => {
    if (initialQuestion && !ignoreInitialRef.current) {
      onQuestionConsumed?.()
      void submitQuestion(initialQuestion)
    }
    ignoreInitialRef.current = false
  }, [initialQuestion]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const task = activeTaskState.task
    if (!activeChatTask || !task || !isTerminalStatus(task.status)) return
    if (task.status === 'done' && activeTaskState.toolCalls.length === 0 && activeTaskState.fetching) return
    if (handledTaskIdRef.current === activeChatTask.taskId) return
    handledTaskIdRef.current = activeChatTask.taskId

    if (task.status === 'done') {
      const answer = chatTaskAnswer(task)
      const meta = chatAgentMeta(task, activeTaskState.toolCalls, { success: Boolean(answer), answer: answer ?? '' })
      const assistantMsg: ChatMessage = answer
        ? { role: 'assistant', content: answer, meta }
        : { role: 'error', content: activeChatTask.question, meta: { ...meta, success: false, error: '回答生成失败' } }
      setMessages((prev) => [...prev, assistantMsg])
      saveMessage(activeChatTask.sessionId, assistantMsg.role, assistantMsg.content, chatMessageToMetaJson(assistantMsg))
    } else {
      const msg = task.status === 'cancelled' ? '回答已取消' : chatTaskError(task)
      const errorMsg: ChatMessage = {
        role: 'error',
        content: activeChatTask.question,
        meta: chatAgentMeta(task, activeTaskState.toolCalls, {
          success: false,
          answer: '',
          error: msg,
          cancelled: task.status === 'cancelled',
        }),
      }
      setMessages((prev) => [...prev, errorMsg])
      saveMessage(activeChatTask.sessionId, 'error', activeChatTask.question, chatMessageToMetaJson(errorMsg))
    }

    setActiveChatTask(null)
    setRetryingIdx(null)
  }, [activeChatTask, activeTaskState.task, activeTaskState.toolCalls, saveMessage])

  const handleSend = () => {
    void submitQuestion(input)
  }

  const handleSendWith = (question: string) => {
    void submitQuestion(question)
  }

  const handleRetry = async (idx: number) => {
    const msg = messages[idx]
    if (!msg || msg.role !== 'error') return
    setRetryingIdx(idx)
    setMessages((prev) => prev.filter((_, i) => i !== idx))
    await submitQuestion(msg.content, false)
    setRetryingIdx(null)
  }

  const handleCancel = async () => {
    if (!activeChatTask) return
    const taskContext = activeChatTask
    try {
      const task = await cancelChatTask.mutateAsync(taskContext.taskId)
      const answer = task.status === 'done' ? chatTaskAnswer(task) : null
      const meta = chatAgentMeta(task, activeTaskState.toolCalls, {
        success: Boolean(answer),
        answer: answer ?? '',
        error: answer ? undefined : task.status === 'cancelled' ? '回答已取消' : chatTaskError(task),
        cancelled: task.status === 'cancelled',
      })
      const message: ChatMessage = answer
        ? { role: 'assistant', content: answer, meta }
        : { role: 'error', content: taskContext.question, meta }
      handledTaskIdRef.current = taskContext.taskId
      setMessages((prev) => [...prev, message])
      saveMessage(taskContext.sessionId, message.role, message.content, chatMessageToMetaJson(message))
    } catch (err) {
      const msg = err instanceof Error ? err.message : '取消失败'
      const message: ChatMessage = {
        role: 'error',
        content: taskContext.question,
        meta: { success: false, answer: '', error: msg, task_id: taskContext.taskId, result: null, tool_calls: activeTaskState.toolCalls },
      }
      setMessages((prev) => [...prev, message])
      saveMessage(taskContext.sessionId, 'error', taskContext.question, chatMessageToMetaJson(message))
    }
    setActiveChatTask(null)
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, asking])

  return (
    <div className="flex flex-col gap-4" data-mobile-chat="conversation">
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
      <div className="mobile-ai-chat-card rounded-[16px] border border-border bg-card/30 backdrop-blur-[12px] overflow-hidden">
        <ChatMessageList
          messages={messages}
          asking={asking}
          sessionLoading={sessionLoading}
          activeTask={{ task: displayedTask, events: activeTaskState.events, toolCalls: activeTaskState.toolCalls }}
          retryingIdx={retryingIdx}
          reportContext={reportContext}
          onRetry={handleRetry}
          onCancel={handleCancel}
          bottomRef={bottomRef}
        />
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

        {!asking && (
          <div className="border-t border-border/40 px-4 py-3">
            <SuggestedQuestions
              questions={questions}
              onSelect={handleSendWith}
              disabled={asking}
              isLoading={questionsLoading}
            />
          </div>
        )}

        <ChatComposer
          value={input}
          disabled={asking}
          thinkingMode={thinkingMode}
          onChange={setInput}
          onThinkingModeChange={setThinkingMode}
          onSend={handleSend}
        />
      </div>

      <AiDisclaimer />
    </div>
  )
}
