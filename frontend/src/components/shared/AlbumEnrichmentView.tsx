import { FormattedText } from '@/components/shared/FormattedText'
import { GlassCard } from '@/components/shared/GlassCard'
import { KeyFactsCard } from '@/components/shared/KeyFactsCard'
import { GenreTags } from '@/components/shared/GenreTags'
import { ChartBars } from '@/components/shared/ChartBars'
import type { StructuredAlbum } from '@/types/billboard'
import { Sparkles, Disc3 } from 'lucide-react'

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

interface AlbumEnrichmentViewProps {
  data: StructuredAlbum
}

export function AlbumEnrichmentView({ data }: AlbumEnrichmentViewProps) {
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

        {/* Genres */}
        {data.genres.length > 0 && (
          <div>
            <SectionHead dot="♪" title="音乐风格" />
            <GenreTags genres={data.genres} />
          </div>
        )}
      </div>

      {/* Chart Performance */}
      {data.chart_performance.length > 0 && (
        <div>
          <Divider />
          <div className="mt-5">
            <SectionHead dot="◆" title="榜单表现" />
            <GlassCard className="p-5">
              <ChartBars charts={data.chart_performance} />
            </GlassCard>
          </div>
        </div>
      )}

      {/* Accolades */}
      {data.accolades.length > 0 && (
        <div>
          <Divider />
          <div className="mt-5">
            <SectionHead dot="★" title="荣誉与好评" />
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {data.accolades.map((a, i) => (
                <GlassCard key={i} className="group p-4 transition-colors hover:bg-accent/5">
                  <div className="flex items-start gap-3">
                    <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-amber-500/10 font-sans text-[11px] font-bold tabular-nums text-amber-600 dark:text-amber-400">
                      {a.year}
                    </span>
                    <div className="min-w-0">
                      <p className="font-sans text-[13px] font-semibold text-foreground/85">{a.title}</p>
                      {a.detail && (
                        <p className="mt-0.5 font-sans text-[12px] text-muted-foreground">{a.detail}</p>
                      )}
                    </div>
                  </div>
                </GlassCard>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Singles */}
      {data.singles.length > 0 && (
        <div>
          <Divider />
          <div className="mt-5">
            <SectionHead dot="♫" title="主打单曲" />
            <GlassCard>
              <div className="divide-y divide-border">
                {data.singles.map((s, i) => (
                  <div key={i} className="flex items-center gap-4 px-5 py-3.5 transition-colors hover:bg-muted/30">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-muted font-sans text-[11px] font-bold tabular-nums text-muted-foreground">
                      {i + 1}
                    </span>
                    <Disc3 className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50" />
                    <span className="font-sans text-[13px] font-semibold text-foreground/85 flex-1">{s.name}</span>
                    {s.certification && (
                      <span className="font-sans text-[11px] text-muted-foreground">{s.certification}</span>
                    )}
                    <span className="flex h-6 w-8 items-center justify-center rounded bg-amber-500/10 font-sans text-[12px] font-bold tabular-nums text-amber-600 dark:text-amber-400">
                      #{s.peak}
                    </span>
                  </div>
                ))}
              </div>
            </GlassCard>
          </div>
        </div>
      )}
    </div>
  )
}
