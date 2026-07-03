import type { VisualYearlyArtifact } from './yearlyArtifactTypes'

function periodLabel(period: Record<string, unknown>): string | null {
  const year = typeof period.year === 'number' || typeof period.year === 'string'
    ? String(period.year)
    : null
  const endDate = typeof period.end_date === 'string' ? period.end_date : null
  const isPartial = period.is_partial_year === true
  if (!year) return null
  return isPartial && endDate ? `${year} · 截至 ${endDate}` : year
}

export function YearlyHero({ artifact }: { artifact: VisualYearlyArtifact }) {
  const period = periodLabel(artifact.period)

  return (
    <header className="min-w-0 border-b border-border/60 pb-6">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[1.2px] text-muted-foreground">
          AI 音乐年报
        </p>
        {period && (
          <span className="rounded-full border border-border bg-card/50 px-2 py-0.5 text-[11px] text-muted-foreground">
            {period}
          </span>
        )}
      </div>
      <h2 className="mt-2 text-balance break-words font-serif text-[30px] font-bold leading-tight text-foreground sm:text-[34px]">
        {artifact.title}
      </h2>
      <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-muted-foreground">
        {artifact.subtitle}
      </p>
    </header>
  )
}
