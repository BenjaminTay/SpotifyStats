import { YearlyHero } from './YearlyHero'
import { YearlyInsightCards } from './YearlyInsightCards'
import { YearlySection } from './YearlySection'
import type { VisualYearlyArtifact } from './yearlyArtifactTypes'

export function VisualYearlyReport({ artifact }: { artifact: VisualYearlyArtifact }) {
  return (
    <article className="min-w-0 space-y-8 text-foreground">
      <YearlyHero artifact={artifact} />
      <YearlyInsightCards cards={artifact.insight_cards} />
      {artifact.sections.map((section) => (
        <YearlySection
          artifact={artifact}
          key={section.id}
          section={section}
        />
      ))}
    </article>
  )
}
