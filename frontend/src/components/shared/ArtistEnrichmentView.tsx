import { FormattedText } from '@/components/shared/FormattedText'
import { GlassCard } from '@/components/shared/GlassCard'
import { KeyFactsCard } from '@/components/shared/KeyFactsCard'
import { CareerTimeline } from '@/components/shared/CareerTimeline'
import { GenreTags } from '@/components/shared/GenreTags'
import { StatsGrid } from '@/components/shared/StatsGrid'
import type { StructuredArtist } from '@/types/billboard'
import { Sparkles } from 'lucide-react'

function SectionHead({ dot, title }: { dot: string; title: string }) {
  return (
    <div className="flex items-center gap-2.5 mb-4">
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-accent/10 text-[13px] leading-none" aria-hidden>
        {dot}
      </span>
      <h4 className="font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-muted-foreground">{title}</h4>
    </div>
  )
}

function Divider() {
  return (
    <div className="flex items-center gap-2" aria-hidden>
      <div className="h-px flex-1 bg-gradient-to-r from-transparent via-border to-transparent" />
    </div>
  )
}

interface ArtistEnrichmentViewProps {
  data: StructuredArtist
}

export function ArtistEnrichmentView({ data }: ArtistEnrichmentViewProps) {
  return (
    <div className="space-y-8">
      {/* Summary */}
      {data.summary && (
        <GlassCard className="overflow-hidden p-5">
          <div className="mb-3 flex items-center gap-2">
            <Sparkles className="h-3.5 w-3.5 text-amber-500 dark:text-amber-400" />
            <span className="font-sans text-[10px] font-bold uppercase tracking-[1.5px] text-muted-foreground">AI 百科</span>
          </div>
          <FormattedText
            text={data.summary}
            className="font-serif text-[15px] leading-relaxed text-foreground/85"
          />
        </GlassCard>
      )}

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        {/* Key Facts */}
        {data.key_facts.length > 0 && (
          <div>
            <SectionHead dot="✦" title="关键信息" />
            <KeyFactsCard facts={data.key_facts} />
          </div>
        )}

        {/* Stats */}
        {data.stats.length > 0 && (
          <div>
            <SectionHead dot="◆" title="关键数据" />
            <StatsGrid stats={data.stats} />
          </div>
        )}
      </div>

      {/* Genres */}
      {data.genres.length > 0 && (
        <div>
          <Divider />
          <div className="mt-5">
            <SectionHead dot="♪" title="音乐风格" />
            <GenreTags genres={data.genres} />
          </div>
        </div>
      )}

      {/* Career Timeline */}
      {data.career_timeline.length > 0 && (
        <div>
          <Divider />
          <div className="mt-5">
            <SectionHead dot="◈" title="生涯时间线" />
            <GlassCard className="p-5">
              <CareerTimeline events={data.career_timeline} />
            </GlassCard>
          </div>
        </div>
      )}

      {/* Achievements */}
      {data.achievements.length > 0 && (
        <div>
          <Divider />
          <div className="mt-5">
            <SectionHead dot="★" title="奖项与荣誉" />
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {data.achievements.map((a, i) => (
                <GlassCard key={i} className="group p-4 transition-colors hover:bg-accent/5">
                  <div className="flex items-start gap-3">
                    <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-amber-500/10 font-sans text-[11px] font-bold tabular-nums text-amber-600 dark:text-amber-400">
                      {a.year}
                    </span>
                    <div className="min-w-0">
                      <p className="font-sans text-[13px] font-semibold text-foreground/85">{a.title}</p>
                      {a.detail && (
                        <p className="mt-0.5 font-sans text-[12px] leading-snug text-muted-foreground">{a.detail}</p>
                      )}
                    </div>
                  </div>
                </GlassCard>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
