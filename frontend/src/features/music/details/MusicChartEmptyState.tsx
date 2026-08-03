import { BarChart3 } from 'lucide-react'
import { GlassCard } from '@/components/shared/GlassCard'

export function MusicChartEmptyState({
  effectivePlayCount = 0,
  title = '暂未入榜',
  description,
}: {
  effectivePlayCount?: number
  title?: string
  description?: string
}) {
  const count = new Intl.NumberFormat('zh-CN').format(effectivePlayCount)
  return (
    <div role="status" aria-live="polite">
      <GlassCard className="p-8 text-center">
        <BarChart3 className="mx-auto mb-3 h-7 w-7 text-accent-foreground" aria-hidden="true" />
        <h2 className="font-serif text-xl font-semibold">{title}</h2>
        <p className="mx-auto mt-2 max-w-xl font-sans text-[13px] leading-6 text-muted-foreground">
          {description ?? `已有 ${count} 次有效播放，尚未进入当前榜单统计范围。播放分析仍会完整保留。`}
        </p>
      </GlassCard>
    </div>
  )
}
