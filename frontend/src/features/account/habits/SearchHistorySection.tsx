import { useMemo } from 'react'
import { GlassCard } from '@/components/shared/GlassCard'
import { KpiCard } from '@/components/shared/KpiCard'
import { cn } from '@/lib/utils'
import { Search, Target, Zap, Compass, Clock } from 'lucide-react'
import { fmtInt } from './habitsPrimitives'
import { getMostActiveDay, getIntentColors, getIntentLabels } from './habitsData'
import type { SearchData } from '@/types/account'

function fmtPct(n: number, total: number): string {
  if (total === 0) return '0%'
  return `${Math.round((n / total) * 100)}%`
}

function safeDiv(a: number, b: number): number {
  return b === 0 ? 0 : a / b
}

interface Props {
  search: SearchData
}

export function SearchHistorySection({ search }: Props) {
  const intentTotal = useMemo(
    () =>
      search.available && !search.empty
        ? search.intent_dist.reduce((s, i) => s + i.count, 0)
        : 0,
    [search],
  )

  const mostActiveDay = useMemo(
    () =>
      search.available && !search.empty
        ? getMostActiveDay(search.heatmap)
        : null,
    [search],
  )

  const topIntent = useMemo(() => {
    if (!search.available || search.empty) return null
    const sorted = [...search.intent_dist].sort((a, b) => b.count - a.count)
    return sorted[0] ?? null
  }, [search])

  const peakSearchDay = useMemo(() => {
    if (!search.available || search.empty || !search.daily_volume.length)
      return null
    return [...search.daily_volume].sort((a, b) => b.count - a.count)[0] ?? null
  }, [search])

  return (
    <GlassCard className="p-6">
      <div className="space-y-6">
        {/* header */}
        <div className="flex items-center gap-2.5">
          <Search className="h-5 w-5 text-amber-500" />
          <h2 className="mb-5 font-serif text-xl font-semibold">搜索编年史</h2>
        </div>

        {/* top row: KPI sidebar + top queries */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* left: KPI + intent bar */}
          <div className="space-y-5 lg:col-span-1">
            <KpiCard
              label="总搜索次数"
              value={fmtInt(search.total_searches)}
            />

            {/* intent distribution stacked bar */}
            <div className="space-y-2">
              <p className="font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">
                搜索意向分布
              </p>
              <div className="flex h-3 w-full overflow-hidden rounded-full">
                {search.intent_dist.map((item) => {
                  const pct = safeDiv(item.count, intentTotal) * 100
                  if (pct === 0) return null
                  return (
                    <div
                      key={item.intent}
                      className={cn(
                        'h-full transition-all',
                        (getIntentColors() as Record<string, string>)[
                          item.intent
                        ] ?? 'bg-slate-300',
                      )}
                      style={{ width: `${pct}%` }}
                    />
                  )
                })}
              </div>
              <div className="flex flex-wrap gap-3">
                {search.intent_dist.map((item) => (
                  <span
                    key={item.intent}
                    className="flex items-center gap-1.5 font-sans text-xs text-muted-foreground"
                  >
                    <span
                      className={cn(
                        'inline-block h-2.5 w-2.5 rounded-full',
                        (getIntentColors() as Record<string, string>)[
                          item.intent
                        ] ?? 'bg-slate-300',
                      )}
                    />
                    {(getIntentLabels() as Record<string, string>)[
                      item.intent
                    ] ?? item.intent}{' '}
                    {fmtPct(item.count, intentTotal)}
                  </span>
                ))}
              </div>
            </div>

            {/* three discovery numbers */}
            <div className="space-y-3 rounded-xl border border-border bg-muted/40 p-4">
              <p className="font-sans text-[10px] font-semibold uppercase tracking-[1.5px] text-muted-foreground">
                搜索发现
              </p>
              {topIntent && (
                <div className="flex items-center gap-3">
                  <Target className="h-4 w-4 shrink-0 text-sky-500" />
                  <div>
                    <p className="font-sans text-xs text-muted-foreground">
                      最爱搜索类型
                    </p>
                    <p className="font-serif text-sm font-semibold">
                      {topIntent.intent}
                    </p>
                  </div>
                </div>
              )}
              {peakSearchDay && (
                <div className="flex items-center gap-3">
                  <Zap className="h-4 w-4 shrink-0 text-amber-500" />
                  <div>
                    <p className="font-sans text-xs text-muted-foreground">
                      搜索最多的一天
                    </p>
                    <p className="font-serif text-sm font-semibold">
                      {peakSearchDay.date}（{peakSearchDay.count} 次）
                    </p>
                  </div>
                </div>
              )}
              <div className="flex items-center gap-3">
                <Compass className="h-4 w-4 shrink-0 text-emerald-500" />
                <div>
                  <p className="font-sans text-xs text-muted-foreground">
                    独特搜索词
                  </p>
                  <p className="font-serif text-sm font-semibold">
                    {fmtInt(search.top_queries.length)} 个
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* right: top queries */}
          <div className="space-y-3 lg:col-span-2">
            <p className="font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">
              热搜词 Top 10
            </p>
            <div className="space-y-1">
              {search.top_queries.slice(0, 10).map((q, idx) => (
                <div
                  key={q.query}
                  className="flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-muted/40"
                >
                  <span className="w-6 text-right font-sans text-xs tabular-nums text-muted-foreground">
                    {idx + 1}
                  </span>
                  <span className="flex-1 truncate font-sans text-sm">
                    {q.query}
                  </span>
                  <span className="font-sans text-xs tabular-nums text-muted-foreground">
                    {q.count} 次
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* bottom: heatmap simplified – most active day */}
        {mostActiveDay && mostActiveDay.total > 0 && (
          <div className="space-y-3 rounded-xl border border-border bg-muted/30 p-5">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <p className="font-sans text-xs font-semibold uppercase tracking-[0.5px] text-muted-foreground">
                最活跃日 · {mostActiveDay.dayLabel} · 共{' '}
                {mostActiveDay.total} 次搜索
              </p>
            </div>
            <div className="flex items-end gap-[2px]">
              {mostActiveDay.hours.map((v, h) => {
                const max = Math.max(...mostActiveDay.hours, 1)
                const heightPct = (v / max) * 100
                return (
                  <div
                    key={h}
                    className="group relative flex-1"
                    title={`${h}:00 – ${v} 次`}
                  >
                    <div
                      className="w-full rounded-t-sm bg-amber-500/70 transition-all group-hover:bg-amber-500"
                      style={{ height: `${Math.max(heightPct, 2)}%` }}
                    />
                  </div>
                )
              })}
            </div>
            <div className="flex justify-between font-sans text-[10px] text-muted-foreground/60">
              <span>0:00</span>
              <span>6:00</span>
              <span>12:00</span>
              <span>18:00</span>
              <span>23:00</span>
            </div>
          </div>
        )}
      </div>
    </GlassCard>
  )
}
