import type { AiTaskEvent, AiTaskRun } from '@/types/ai-tasks'

interface AITaskProgressProps {
  task: AiTaskRun | null
  events: AiTaskEvent[]
}

function progressPercent(value: number | null | undefined): number {
  const normalized = value == null ? 0 : value <= 1 ? value * 100 : value
  return Math.max(0, Math.min(100, Math.round(normalized)))
}

export function AITaskProgress({ task, events }: AITaskProgressProps) {
  if (!task) return null

  if (task.found === false) {
    return (
      <section className="rounded-[8px] border border-border bg-card/40 p-4 backdrop-blur-[12px]">
        <p className="text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">
          AI 任务进度
        </p>
        <p className="mt-2 text-[13px] text-muted-foreground">未找到该 AI 任务</p>
      </section>
    )
  }

  const pct = progressPercent(task.progress_pct)
  const stage = task.stage?.trim()
  const message = task.message?.trim()
  const showError = task.status === 'error' && task.error

  return (
    <section className="rounded-[8px] border border-border bg-card/40 p-4 backdrop-blur-[12px]">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">
            AI 任务进度
          </p>
          {stage && (
            <p className="mt-1 font-mono text-[12px] text-muted-foreground">
              {stage}
            </p>
          )}
          {message && (
            <p className="mt-1 text-[13px] leading-relaxed text-foreground">
              {message}
            </p>
          )}
        </div>
        <span className="shrink-0 text-[12px] tabular-nums text-muted-foreground">
          {pct}%
        </span>
      </div>

      <div
        aria-label="AI 任务完成百分比"
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={pct}
        className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted/30"
        role="progressbar"
      >
        <div
          className="h-full rounded-full bg-accent-foreground transition-[width]"
          style={{ width: `${pct}%` }}
        />
      </div>

      {events.length > 0 && (
        <ol className="mt-3 space-y-1.5">
          {events.map((event, index) => (
            <li
              className="text-[12px] leading-relaxed text-muted-foreground"
              key={event.event_id ?? `${event.stage}-${index}`}
            >
              {event.message || event.stage}
            </li>
          ))}
        </ol>
      )}

      {showError && (
        <p className="mt-3 text-[12px] leading-relaxed text-destructive">
          {task.error}
        </p>
      )}
    </section>
  )
}
