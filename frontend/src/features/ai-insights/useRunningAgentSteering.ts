import { useCallback, useState, type Dispatch, type SetStateAction } from 'react'

import { useSendAiAgentInput } from '@/hooks/useAiTasks'
import type { ChatMessage } from '@/types/ai-insights'
import type { AiAgentSteeringInput } from '@/types/ai-tasks'

interface Args {
  taskId: string | null
  sessionId: number | null
  active: boolean
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>
  saveMessage: (sessionId: number | null, role: string, content: string) => void
  setError: Dispatch<SetStateAction<string | null>>
}

export function useRunningAgentSteering({
  taskId,
  sessionId,
  active,
  setMessages,
  saveMessage,
  setError,
}: Args) {
  const sendInput = useSendAiAgentInput()
  const [receiptState, setReceiptState] = useState<{
    taskId: string | null
    inputs: AiAgentSteeringInput[]
  }>({ taskId: null, inputs: [] })
  const steerRunningAgent = useCallback(async (content: string): Promise<boolean> => {
    if (!active || !taskId) return false
    try {
      const response = await sendInput.mutateAsync({ taskId, action: 'steer', content })
      if (!response.accepted) throw new Error('当前 Agent 回合已结束，请重新发送')
      setReceiptState((current) => ({
        taskId,
        inputs: [
          ...(current.taskId === taskId ? current.inputs : []),
          { inboxId: response.inbox_id ?? null, content, status: response.status },
        ],
      }))
      setMessages((current) => [...current, { role: 'user', content }])
      saveMessage(sessionId, 'user', content)
    } catch (error) {
      setError(error instanceof Error ? error.message : '补充要求发送失败')
    }
    return true
  }, [active, saveMessage, sendInput, sessionId, setError, setMessages, taskId])
  return {
    steerRunningAgent,
    steeringInputs: receiptState.taskId === taskId ? receiptState.inputs : [],
  }
}
