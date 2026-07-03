import type { YearlyInsightCard } from './yearlyArtifactTypes'

const CARD_ACCENTS: Record<string, string> = {
  warm: 'border-amber-500/20 bg-amber-500/[0.06]',
  bright: 'border-sky-500/20 bg-sky-500/[0.06]',
  calm: 'border-emerald-500/20 bg-emerald-500/[0.06]',
  dramatic: 'border-rose-500/20 bg-rose-500/[0.06]',
}

export function YearlyInsightCards({ cards }: { cards: YearlyInsightCard[] }) {
  if (!cards.length) return null

  return (
    <section className="grid min-w-0 gap-3 sm:grid-cols-3">
      {cards.map((card) => (
        <div
          className={`min-w-0 rounded-[8px] border p-4 ${CARD_ACCENTS[card.tone] ?? 'border-border bg-card/50'}`}
          key={card.id}
        >
          <p className="break-words text-[11px] font-semibold uppercase tracking-[0.8px] text-muted-foreground">
            {card.label}
          </p>
          <p className="mt-2 break-words font-serif text-[24px] font-semibold text-foreground">
            {card.value}
          </p>
          <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">
            {card.caption}
          </p>
        </div>
      ))}
    </section>
  )
}
