import { VersusRankChart } from '@/components/charts/VersusRankChart'
import { GlassCard } from '@/components/shared/GlassCard'
import type { VersusRankPoint } from '@/types/billboard'
import { toChartData } from './versusData'
import { displayName, useChineseTextVersion } from '@/lib/chinese'

interface VersusChartSectionProps {
  rankHistories: (VersusRankPoint[] | null)[] | null
  names: string[]
  topN?: number
}

export function VersusChartSection({
  rankHistories,
  names,
  topN = 30,
}: VersusChartSectionProps) {
  useChineseTextVersion()
  if (!rankHistories || rankHistories.length < 2) return null

  const series = rankHistories
    .map((rh, i) => ({
      name: displayName(names[i] ?? `Entity ${i + 1}`),
      data: rh && rh.length > 0 ? toChartData(rh) : [],
    }))
    .filter((s) => s.data.length > 0)

  if (series.length < 2) return null

  return (
    <div>
      <h3 className="mb-4 font-serif text-xl font-semibold">排名走势对比</h3>
      <GlassCard className="p-6">
        <VersusRankChart series={series} topN={topN} />
      </GlassCard>
    </div>
  )
}
