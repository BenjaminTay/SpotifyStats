import type { AiAgentSteeringInput, AiTaskEvent, AiTaskRun } from '@/types/ai-tasks'

type JsonRecord = Record<string, unknown>
type SteeringState = 'pending' | 'consumed' | 'applied' | 'rejected'

const PERIOD_LABELS: Record<string, string> = {
  lifetime: '全部时间',
  this_year: '今年',
  last_6_months: '最近六个月',
  last_4_weeks: '最近四周',
  custom: '指定范围',
}

const METRIC_LABELS: Record<string, string> = {
  plays: '播放次数',
  hours: '收听时长',
  duration: '收听时长',
  ranking: '排名',
  trend: '趋势',
  personal_billboard: '个人 Billboard',
  time_of_day: '收听时段',
}

function recordValue(value: unknown): JsonRecord | null {
  return value != null && typeof value === 'object' && !Array.isArray(value)
    ? value as JsonRecord
    : null
}

function stringValue(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

function listLabels(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    const direct = stringValue(item)
    if (direct) return [direct]
    const row = recordValue(item)
    if (!row) return []
    const label = stringValue(row.label) ?? stringValue(row.name) ?? stringValue(row.value)
    return label ? [label] : []
  })
}

function constraintRecord(source: unknown): JsonRecord | null {
  const root = recordValue(source)
  if (!root) return null
  if (
    root.time_range != null
    || root.entities != null
    || root.metrics != null
    || root.excluded_dimensions != null
  ) return root
  for (const key of ['current_constraints', 'active_constraints', 'constraints']) {
    const candidate = recordValue(root[key])
    if (candidate) return candidate
  }
  for (const key of ['state', 'session_state', 'agent_state']) {
    const state = recordValue(root[key])
    if (!state) continue
    const nested = constraintRecord(state)
    if (nested) return nested
  }
  return null
}

function idLabels(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    if (typeof item === 'number' || typeof item === 'string') return [String(item)]
    const row = recordValue(item)
    const id = row?.inbox_id ?? row?.id
    return typeof id === 'number' || typeof id === 'string' ? [String(id)] : []
  })
}

function latestConstraints(task: AiTaskRun | null, events: AiTaskEvent[]): JsonRecord | null {
  for (const event of [...events].reverse()) {
    const constraints = constraintRecord(event.payload)
    if (constraints) return constraints
  }
  return constraintRecord(task?.result) ?? constraintRecord(task?.request)
}

function timeLabel(constraints: JsonRecord): string | null {
  const value = constraints.time_range
    ?? constraints.timeRange
    ?? constraints.time_scope
    ?? constraints.period
  const direct = stringValue(value)
  if (direct) return PERIOD_LABELS[direct] ?? direct
  const range = recordValue(value)
  if (!range) return null
  const label = stringValue(range.label) ?? stringValue(range.period)
  const start = stringValue(range.start_date) ?? stringValue(range.start)
  const end = stringValue(range.end_date) ?? stringValue(range.end)
  const dates = start && end ? `${start} 至 ${end}` : start ?? end
  return [label ? (PERIOD_LABELS[label] ?? label) : null, dates].filter(Boolean).join(' · ') || null
}

function constraintItems(constraints: JsonRecord | null) {
  if (!constraints) return []
  const entities = listLabels(constraints.entities ?? constraints.entity_names)
  const metrics = listLabels(constraints.metrics ?? constraints.requested_metrics)
    .map((metric) => METRIC_LABELS[metric] ?? metric)
  const excluded = listLabels(
    constraints.excluded_dimensions ?? constraints.excluded ?? constraints.remove_requirements,
  )
  return [
    ...(timeLabel(constraints) ? [{ label: '时间', value: timeLabel(constraints) as string }] : []),
    ...(entities.length ? [{ label: '实体', value: entities.join('、') }] : []),
    ...(metrics.length ? [{ label: '指标', value: metrics.join('、') }] : []),
    ...(excluded.length ? [{ label: '排除', value: excluded.join('、') }] : []),
  ]
}

function normalizedSteeringState(value: unknown): SteeringState | null {
  const status = stringValue(value)?.toLowerCase()
  if (!status) return null
  if (['applied', 'completed'].includes(status)) return 'applied'
  if (['consumed', 'read', 'processing'].includes(status)) return 'consumed'
  if (['rejected', 'failed'].includes(status)) return 'rejected'
  if (['pending', 'accepted', 'received'].includes(status)) return 'pending'
  return null
}

function steeringState(
  input: AiAgentSteeringInput,
  task: AiTaskRun | null,
  events: AiTaskEvent[],
): SteeringState {
  let state = normalizedSteeringState(input.status) ?? 'pending'
  const stateRank: Record<SteeringState, number> = { pending: 0, consumed: 1, applied: 2, rejected: 3 }
  const sources = [task?.result, ...events.map((event) => event.payload)]
  for (const source of sources) {
    const payload = recordValue(source)
    if (!payload) continue
    const appliedIds = idLabels(payload.applied_inbox_ids)
    const consumedIds = idLabels(payload.consumed_inbox_ids)
    if (input.inboxId != null && appliedIds.includes(String(input.inboxId))) state = 'applied'
    if (input.inboxId != null && consumedIds.includes(String(input.inboxId)) && state !== 'applied') {
      state = 'consumed'
    }
  }
  for (const event of events) {
    const payload = recordValue(event.payload)
    const eventInboxId = payload?.inbox_id
    if (input.inboxId != null && Number(eventInboxId) !== input.inboxId) continue
    const explicit = normalizedSteeringState(payload?.status)
    const inferred = event.event_type.includes('applied')
      || event.event_type.includes('constraints_updated')
      || event.event_type === 'session_state_updated'
      ? 'applied'
      : event.event_type.includes('consumed')
        ? 'consumed'
        : event.event_type.includes('rejected')
          ? 'rejected'
          : null
    const next = explicit ?? inferred
    if (next && stateRank[next] > stateRank[state]) state = next
  }
  return state
}

const STEERING_LABELS: Record<SteeringState, string> = {
  pending: '已接收，等待 Agent 读取',
  consumed: 'Agent 已读取',
  applied: '已应用到当前分析',
  rejected: '未能应用',
}

interface Props {
  task: AiTaskRun | null
  events: AiTaskEvent[]
  steeringInputs: AiAgentSteeringInput[]
}

export function AgentConstraintStatus({ task, events, steeringInputs }: Props) {
  const items = constraintItems(latestConstraints(task, events))
  if (items.length === 0 && steeringInputs.length === 0) return null

  return (
    <section
      aria-label="当前分析约束"
      className="rounded-[8px] border border-border/60 bg-card/30 p-3"
    >
      {items.length > 0 && (
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[1px] text-muted-foreground">
            当前分析约束
          </p>
          <dl className="mt-2 flex flex-wrap gap-1.5">
            {items.map((item) => (
              <div
                className="min-w-0 max-w-full rounded-full border border-border/60 bg-background/30 px-2.5 py-1 text-[11px] text-muted-foreground"
                key={item.label}
              >
                <dt className="inline font-semibold text-foreground/70">{item.label} · </dt>
                <dd className="inline break-words">{item.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
      {steeringInputs.length > 0 && (
        <div className={items.length > 0 ? 'mt-3 border-t border-border/40 pt-2.5' : ''}>
          <p className="text-[10px] font-semibold uppercase tracking-[1px] text-muted-foreground">
            运行中补充
          </p>
          <ul className="mt-1.5 space-y-1.5">
            {steeringInputs.map((input, index) => {
              const state = steeringState(input, task, events)
              return (
                <li className="flex min-w-0 items-start justify-between gap-3 text-[11px]" key={input.inboxId ?? index}>
                  <span className="min-w-0 break-words text-foreground/70">{input.content}</span>
                  <span className="shrink-0 text-right text-muted-foreground">{STEERING_LABELS[state]}</span>
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </section>
  )
}
