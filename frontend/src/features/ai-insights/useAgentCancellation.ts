import { useCallback, type Dispatch, type SetStateAction } from 'react'

import { useCancelAiTask } from '@/hooks/useAiTasks'
import {
  chatAgentMeta,
  chatMessageToMetaJson,
  chatTaskAnswer,
  chatTaskError,
} from '@/types/ai-insights'
import type { ChatMessage } from '@/types/ai-insights'
import type { AiToolCall } from '@/types/ai-tasks'

export interface ActiveAgentTask {
  taskId: string
  question: string
  sessionId: number | null
}

interface Args {
  task: ActiveAgentTask | null
  toolCalls: AiToolCall[]
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>
  saveMessage: (sessionId: number | null, role: string, content: string, meta?: string) => void
  markHandled: (taskId: string) => void
  clearTask: () => void
}

export function useAgentCancellation({
  task,
  toolCalls,
  setMessages,
  saveMessage,
  markHandled,
  clearTask,
}: Args) {
  const cancelTask = useCancelAiTask()
  return useCallback(async () => {
    if (!task) return
    try {
      const result = await cancelTask.mutateAsync(task.taskId)
      const answer = result.status === 'done' ? chatTaskAnswer(result) : null
      const meta = chatAgentMeta(result, toolCalls, {
        success: Boolean(answer),
        answer: answer ?? '',
        error: answer ? undefined : result.status === 'cancelled' ? '回答已取消' : chatTaskError(result),
        cancelled: result.status === 'cancelled',
      })
      const message: ChatMessage = answer
        ? { role: 'assistant', content: answer, meta }
        : { role: 'error', content: task.question, meta }
      markHandled(task.taskId)
      setMessages((current) => [...current, message])
      saveMessage(task.sessionId, message.role, message.content, chatMessageToMetaJson(message))
    } catch (error) {
      const message: ChatMessage = {
        role: 'error',
        content: task.question,
        meta: {
          success: false,
          answer: '',
          error: error instanceof Error ? error.message : '取消失败',
          task_id: task.taskId,
          result: null,
          tool_calls: toolCalls,
        },
      }
      setMessages((current) => [...current, message])
      saveMessage(task.sessionId, 'error', task.question, chatMessageToMetaJson(message))
    }
    clearTask()
  }, [cancelTask, clearTask, markHandled, saveMessage, setMessages, task, toolCalls])
}
