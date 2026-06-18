import { GlassCard } from '@/components/shared/GlassCard'
import { displayName } from '@/lib/chinese'
import type { CollectionInsights, ChemistryType } from '@/types/account'

const MAX_CHEMISTRY_EXAMPLES = 8

function ChemistryCard({
  chem,
  total,
}: {
  chem: ChemistryType
  total: number
}) {
  const rawExamples = chem.examples || []
  const examples = rawExamples.slice(0, MAX_CHEMISTRY_EXAMPLES)
  const pct = total > 0 ? (chem.count / total) * 100 : 0
  const ITEM_H = 44
  const VISIBLE_H = ITEM_H * 2
  const listH = examples.length * ITEM_H

  const scrollKeyframes = `
    @keyframes chem-scroll-${chem.label.replace(/\s/g, '')} {
      0%   { transform: translateY(0); }
      100% { transform: translateY(-${listH}px); }
    }
  `

  return (
    <GlassCard className="flex flex-col p-5">
      <div className="mb-2 flex items-start justify-between">
        <span className="text-3xl">{chem.icon}</span>
        <span className="font-serif text-sm font-bold tabular-nums">
          {chem.count} 首
        </span>
      </div>

      <p className="font-serif text-base font-semibold">{chem.label}</p>
      <p className="mt-0.5 font-sans text-xs leading-relaxed text-muted-foreground">
        {chem.description}
      </p>

      <div className="mt-3 flex items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-accent-foreground/60"
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="font-sans text-[11px] tabular-nums text-muted-foreground">
          {pct.toFixed(0)}%
        </span>
      </div>

      {examples.length > 0 && (
        <>
          <style>{scrollKeyframes}</style>
          <div className="mt-3 relative overflow-hidden rounded-md bg-muted/30"
               style={{ height: VISIBLE_H }}>
            <div
              className="flex flex-col"
              style={{
                animation: `chem-scroll-${chem.label.replace(/\s/g, '')} ${examples.length * 3}s linear infinite`,
                width: '100%',
              }}
            >
              {[...examples, ...examples].map((ex, i) => (
                <div
                  key={`${ex.track_name}-${ex.artist_name}-${i}`}
                  className="flex items-center gap-2.5 shrink-0"
                  style={{ height: ITEM_H }}
                >
                  {ex.cover_url ? (
                    <img src={ex.cover_url} alt={ex.track_name}
                      className="h-8 w-8 flex-shrink-0 rounded object-cover"
                      loading="lazy"
                      decoding="async" />
                  ) : (
                    <div className="h-8 w-8 flex-shrink-0 rounded bg-muted" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="font-sans text-xs font-medium truncate">
                      {displayName(ex.track_name)}
                    </p>
                    <p className="font-sans text-[11px] text-muted-foreground truncate">
                      {displayName(ex.artist_name)}
                    </p>
                  </div>
                  {ex.total_plays != null && (
                    <span className="font-sans text-[10px] text-muted-foreground tabular-nums shrink-0">
                      {ex.total_plays}次
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </GlassCard>
  )
}

export function ChemistryBlock({ insights }: { insights: CollectionInsights }) {
  const { chemistry } = insights

  const types: ChemistryType[] = [
    chemistry.love_at_first_listen,
    chemistry.slow_burn,
    chemistry.flash_in_the_pan,
    chemistry.late_bloomer,
    chemistry.steady_favorite,
    chemistry.shelf_sitter,
  ]

  return (
    <section className="space-y-4">
      <h2 className="mb-5 font-serif text-xl font-semibold">
        收藏化学反应
      </h2>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {types.map((chem) => (
          <ChemistryCard
            key={chem.label}
            chem={chem}
            total={chemistry.total_with_dates}
          />
        ))}
      </div>
    </section>
  )
}
