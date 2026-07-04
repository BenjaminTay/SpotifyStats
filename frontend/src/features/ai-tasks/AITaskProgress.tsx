import type { AiTaskEvent, AiTaskRun } from '@/types/ai-tasks'

interface AITaskProgressProps {
  task: AiTaskRun | null
  events: AiTaskEvent[]
}

function progressPercent(value: number | null | undefined): number {
  const normalized = value == null ? 0 : value <= 1 ? value * 100 : value
  return Math.max(0, Math.min(100, Math.round(normalized)))
}

const STAGE_LABELS: Record<string, string> = {
  checking_cache: '检查报告缓存',
  gathering_local_data: '汇总本地播放数据',
  calling_llm: '调用 LLM 生成',
  saving_cache: '保存报告缓存',
  researching: '只读调研数据',
  synthesizing_insights: '综合证据洞见',
  outlining: '生成文章大纲',
  drafting: '撰写长篇报告',
  critic_review: '编辑审稿',
  building_narrative_brief: '提炼年度故事线',
  planning_visuals: '选择年报图表',
  building_chart_data: '准备图表数据',
  building_research_brief: '整理年度研究简报',
  planning_storyline: '规划文章主线',
  writing_article: '撰写年报文章',
  composing_artifact: '生成图文年报',
  editing_article: '编辑年报文风',
  checking_claims: '核对文章事实',
  scoring_taste: '评估文章可读性',
  reviewing_visual_artifact: '检查文风与事实口径',
  selecting_artists: '选择待补全艺人',
  fetching_external_data: '获取外部资料',
  saving_suggestions: '保存 genre 建议',
  done: '完成',
  cancelled: '已取消',
  error: '失败',
}

function stageLabel(stage: string | null | undefined): string | null {
  if (!stage) return null
  return STAGE_LABELS[stage] ?? stage
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
  const readableStage = stageLabel(stage)
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
              {readableStage}
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
