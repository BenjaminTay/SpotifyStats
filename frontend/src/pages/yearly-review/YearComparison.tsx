import type { YearComparison as YearComparisonType } from '@/types/yearly-review'

interface YearComparisonProps {
  comparison: YearComparisonType
}

export function YearComparison({ comparison }: YearComparisonProps) {
  if (comparison.last_year) return null

  return (
    <section className="mb-12">
      <h2 className="font-serif text-[28px] font-bold tracking-[-0.5px] mb-6">年度对比</h2>
      <p className="font-sans text-[14px] text-muted-foreground mb-6">暂无去年数据可供对比。再过一年就能看到了！</p>
    </section>
  )
}
