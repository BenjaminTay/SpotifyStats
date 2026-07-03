export interface YearlyArtifactSection {
  id: string
  role: string
  heading: string
  deck: string
  prose: string
  chart_refs: string[]
  insight_refs: string[]
  evidence_refs: string[]
  pull_quote: string | null
}

export interface YearlyInsightCard {
  id: string
  label: string
  value: string
  caption: string
  tone: string
  evidence_refs: string[]
}

export interface YearlyChartSpec {
  id: string
  chart_type: string
  title: string
  narrative_question: string
  entities: string[]
  data_key: string
  insight: string
  fallback: string
}

export interface VisualYearlyArtifact {
  report_mode: 'visual_yearly_artifact'
  contract_version: string
  title: string
  subtitle: string
  period: Record<string, unknown>
  narrative_brief: Record<string, unknown>
  visual_brief: Record<string, unknown>
  sections: YearlyArtifactSection[]
  insight_cards: YearlyInsightCard[]
  chart_specs: YearlyChartSpec[]
  chart_data: Record<string, unknown>
  metadata: Record<string, unknown>
}

export function isVisualYearlyArtifact(value: unknown): value is VisualYearlyArtifact {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const record = value as Record<string, unknown>
  return (
    record.report_mode === 'visual_yearly_artifact'
    && Array.isArray(record.sections)
    && Array.isArray(record.insight_cards)
    && Array.isArray(record.chart_specs)
    && typeof record.chart_data === 'object'
    && record.chart_data !== null
  )
}
