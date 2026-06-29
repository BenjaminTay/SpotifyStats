import type { AiEvidenceCard, AiEvidenceMetric } from '@/types/ai-tasks'

interface AIEvidenceCardsProps {
  cards: AiEvidenceCard[]
}

function formatMetricValue(metric: AiEvidenceMetric): string {
  if (metric.value == null) return '无数据'
  const value = String(metric.value)
  return metric.unit ? `${value} ${metric.unit}` : value
}

function evidenceCardKey(card: AiEvidenceCard, index: number): string {
  return [
    card.card_id || card.title || 'evidence-card',
    card.source.tool_name,
    card.source.source_range || 'unknown-range',
    index,
  ].join(':')
}

export function AIEvidenceCards({ cards }: AIEvidenceCardsProps) {
  if (cards.length === 0) return null

  return (
    <section className="rounded-[8px] border border-border bg-card/30 p-4">
      <p className="text-[11px] font-semibold text-muted-foreground">
        证据卡片
      </p>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {cards.map((card, index) => (
          <EvidenceCard card={card} index={index} key={evidenceCardKey(card, index)} />
        ))}
      </div>
    </section>
  )
}

function EvidenceCard({ card, index }: { card: AiEvidenceCard; index: number }) {
  const hasNotes = Boolean(card.observations?.length || card.limitations?.length)
  const isComparison = card.question_axis === 'comparison'
  const metricsGridClass = isComparison
    ? 'mt-3 grid grid-cols-1 gap-x-3 gap-y-2 sm:grid-cols-2'
    : 'mt-3 grid grid-cols-2 gap-x-3 gap-y-2'

  return (
    <article className="rounded-[8px] border border-border/50 bg-muted/20 p-3">
      <div className="min-w-0">
        <h4 className="text-[13px] font-semibold leading-snug text-foreground">
          {card.title}
        </h4>
        <div className="mt-1 flex flex-wrap items-center gap-1.5 font-mono text-[11px] text-muted-foreground">
          <span>{card.source.tool_name}</span>
          {card.source.source_range && (
            <>
              <span aria-hidden="true">·</span>
              <span>{card.source.source_range}</span>
            </>
          )}
        </div>
      </div>

      {card.metrics.length > 0 && (
        <dl className={metricsGridClass}>
          {card.metrics.map((metric, metricIndex) => (
            <div className="min-w-0" key={metric.name || `${card.card_id}-${metricIndex}-${index}`}>
              <dt className="text-[11px] leading-snug text-muted-foreground">
                {metric.label}
              </dt>
              <dd className="mt-0.5 break-words text-[13px] font-medium leading-snug text-foreground">
                {formatMetricValue(metric)}
              </dd>
              {metric.note && (
                <dd className="mt-0.5 text-[11px] leading-snug text-muted-foreground/70">
                  {metric.note}
                </dd>
              )}
            </div>
          ))}
        </dl>
      )}

      {hasNotes && (
        <div className="mt-3 space-y-1 text-[11px] leading-relaxed text-muted-foreground">
          {card.observations?.map((line) => (
            <p key={`observation-${line}`}>{line}</p>
          ))}
          {card.limitations?.map((line) => (
            <p key={`limitation-${line}`}>{line}</p>
          ))}
        </div>
      )}
    </article>
  )
}
