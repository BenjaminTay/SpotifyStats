import { useMemo } from 'react'

import { YearlyHero } from './YearlyHero'
import { YearlyInsightCards } from './YearlyInsightCards'
import { YearlySection } from './YearlySection'
import type { VisualYearlyArtifact } from './yearlyArtifactTypes'

function sectionsWithUniqueChartRefs(artifact: VisualYearlyArtifact) {
  const rendered = new Set<string>()
  const available = new Set(artifact.chart_specs.map((spec) => spec.id))

  return artifact.sections.map((section) => ({
    ...section,
    chart_refs: section.chart_refs.filter((chartId) => {
      if (!available.has(chartId)) return false
      if (rendered.has(chartId)) return false
      rendered.add(chartId)
      return true
    }),
  }))
}

export function VisualYearlyReport({ artifact }: { artifact: VisualYearlyArtifact }) {
  const sections = useMemo(() => sectionsWithUniqueChartRefs(artifact), [artifact])

  return (
    <article className="min-w-0 space-y-8 text-foreground">
      <YearlyHero artifact={artifact} />
      <YearlyInsightCards cards={artifact.insight_cards} />
      {sections.map((section) => (
        <YearlySection
          artifact={artifact}
          key={section.id}
          section={section}
        />
      ))}
    </article>
  )
}
