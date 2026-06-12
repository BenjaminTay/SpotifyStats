import { GlassCard } from '@/components/shared/GlassCard'
import type { PersonalityResult } from './habitsData'

interface Props {
  personality: PersonalityResult
}

export function HabitsPersonalityHero({ personality }: Props) {
  return (
    <GlassCard className="relative overflow-hidden p-6 md:p-8">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex-1 space-y-2">
          <p className="font-sans text-[11px] font-semibold uppercase tracking-[2px] text-accent-foreground">
            你的收听人格
          </p>
          <h2 className="font-serif text-4xl font-bold tracking-[-0.5px] text-foreground md:text-5xl">
            {personality.type}
          </h2>
          <p className="max-w-lg font-sans text-sm leading-relaxed text-muted-foreground">
            {personality.description}
          </p>
        </div>

        <div className="flex flex-wrap gap-6 lg:gap-10">
          {personality.metrics.map((m) => (
            <div key={m.label} className="text-center">
              <p className="font-serif text-3xl font-bold text-foreground md:text-4xl">
                {m.value}
              </p>
              <p className="mt-1 font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">
                {m.label}
              </p>
              <p className="mt-0.5 font-sans text-[10px] text-muted-foreground/60">
                {m.detail}
              </p>
            </div>
          ))}
        </div>
      </div>
    </GlassCard>
  )
}
