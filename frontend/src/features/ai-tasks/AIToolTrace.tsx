import type { AiToolCall } from '@/types/ai-tasks'

interface AIToolTraceProps {
  toolCalls: AiToolCall[]
}

export function AIToolTrace({ toolCalls }: AIToolTraceProps) {
  if (toolCalls.length === 0) return null

  return (
    <section className="rounded-[8px] border border-border bg-card/30 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">
        数据查询轨迹
      </p>
      <div className="mt-3 space-y-2">
        {toolCalls.map((call) => (
          <article
            className="rounded-[8px] border border-border/50 bg-muted/20 p-3"
            key={call.tool_call_id}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[12px] text-foreground">
                {call.tool_name}
              </span>
              <span className="rounded-[6px] bg-background px-1.5 py-0.5 text-[11px] text-muted-foreground">
                {call.status}
              </span>
            </div>
            {call.params_summary && (
              <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
                {call.params_summary}
              </p>
            )}
            {call.result_summary && (
              <p className="mt-1 text-[12px] leading-relaxed text-foreground/80">
                {call.result_summary}
              </p>
            )}
            {call.source_range && (
              <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground/70">
                {call.source_range}
              </p>
            )}
            {call.error && (
              <p className="mt-1 text-[11px] leading-relaxed text-destructive">
                {call.error}
              </p>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}
