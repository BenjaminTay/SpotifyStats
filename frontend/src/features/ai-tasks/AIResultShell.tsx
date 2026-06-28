import type { ReactNode } from 'react'

import { AIEvidenceCards } from './AIEvidenceCards'
import { AITaskProgress } from './AITaskProgress'
import { AIToolTrace } from './AIToolTrace'
import type { AiEvidenceCard, AiTaskEvent, AiTaskRun, AiToolCall } from '@/types/ai-tasks'

interface AIResultShellProps {
  task: AiTaskRun | null
  events: AiTaskEvent[]
  evidenceCards?: AiEvidenceCard[]
  toolCalls?: AiToolCall[]
  children: ReactNode
}

export function AIResultShell({
  task,
  events,
  evidenceCards = [],
  toolCalls = [],
  children,
}: AIResultShellProps) {
  return (
    <div className="space-y-4">
      <AITaskProgress task={task} events={events} />
      <AIEvidenceCards cards={evidenceCards} />
      <AIToolTrace toolCalls={toolCalls} />
      {children}
      <p className="text-center text-[11px] text-muted-foreground/60">
        由 AI 基于本地听歌数据生成，仅供参考。
      </p>
    </div>
  )
}
