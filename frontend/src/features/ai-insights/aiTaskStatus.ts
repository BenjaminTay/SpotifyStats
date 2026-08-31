import type { AiTaskRun } from '@/types/ai-tasks'

export function isActiveAiTask(status: AiTaskRun['status'] | null | undefined): boolean {
  return status === 'queued' || status === 'running' || status === 'cancelling'
}

export function isTerminalAiTask(status: AiTaskRun['status'] | null | undefined): boolean {
  return status === 'done' || status === 'error' || status === 'cancelled'
}
