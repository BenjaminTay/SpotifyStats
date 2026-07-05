import { AiMarkdown } from '@/features/ai-insights/AiMarkdown'
import { YearlyChartBlock } from './YearlyChartBlock'
import type { VisualYearlyArtifact, YearlyArtifactSection } from './yearlyArtifactTypes'

export function YearlySection({
  artifact,
  section,
}: {
  artifact: VisualYearlyArtifact
  section: YearlyArtifactSection
}) {
  return (
    <section className="min-w-0 space-y-4">
      <div className="max-w-3xl">
        <h3 className="break-words font-serif text-[24px] font-semibold leading-tight text-foreground sm:text-[26px]">
          {section.heading}
        </h3>
        {section.deck && (
          <p className="mt-2 text-[14px] leading-relaxed text-muted-foreground">{section.deck}</p>
        )}
        <div className="prose prose-sm mt-4 max-w-none text-[15px] leading-7 text-muted-foreground [&_strong]:text-foreground">
          <AiMarkdown>{section.prose}</AiMarkdown>
        </div>
        {section.pull_quote && (
          <blockquote className="mt-4 border-l-2 border-accent-foreground/50 pl-4 font-serif text-[18px] leading-relaxed text-foreground">
            {section.pull_quote}
          </blockquote>
        )}
      </div>
      {section.chart_refs.map((chartId) => {
        const spec = artifact.chart_specs.find((item) => item.id === chartId) ?? null
        const dataKey = spec?.data_key ?? chartId
        return (
          <YearlyChartBlock
            chartData={artifact.chart_data[chartId] ?? artifact.chart_data[dataKey]}
            key={chartId}
            spec={spec}
          />
        )
      })}
    </section>
  )
}
