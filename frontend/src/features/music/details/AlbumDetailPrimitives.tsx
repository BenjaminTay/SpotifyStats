import { useState } from 'react'
import { ChevronDown, ChevronUp, ExternalLink } from 'lucide-react'

import { GlassCard } from '@/components/shared/GlassCard'
import { FormattedText } from '@/components/shared/FormattedText'

export function AlbumStoryCard({
  summary,
  background,
  url,
}: {
  summary: string
  background: string
  url: string
}) {
  const [expanded, setExpanded] = useState(false)
  const text = (background || summary || '').trim()
  if (!text) return null

  const preview = text.slice(0, 280)
  const hasMore = text.length > 280

  return (
    <GlassCard className="p-5">
      <FormattedText
        text={expanded || !hasMore ? text : `${preview}...`}
        className="font-sans text-[14px] leading-relaxed text-foreground/85"
      />
      <div className="mt-3 flex items-center gap-3">
        {hasMore && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="inline-flex items-center gap-1 font-sans text-[12px] font-semibold text-accent-foreground transition-opacity hover:opacity-80"
          >
            {expanded ? (
              <>
                <ChevronUp className="h-3.5 w-3.5" />
                收起
              </>
            ) : (
              <>
                <ChevronDown className="h-3.5 w-3.5" />
                展开全文
              </>
            )}
          </button>
        )}
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
          >
            <ExternalLink className="h-3 w-3" />
            Wikipedia
          </a>
        )}
      </div>
    </GlassCard>
  )
}

export function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-0.5 font-sans text-[13px] text-foreground/85">{value}</dd>
    </div>
  )
}

export function MiniStat({
  label,
  value,
  accent,
}: {
  label: string
  value: string
  accent?: boolean
}) {
  return (
    <div>
      <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
        {label}
      </p>
      <p
        className="mt-1 font-serif text-[26px] font-bold leading-none"
        style={accent ? { color: 'var(--accent-foreground)' } : undefined}
      >
        {value}
      </p>
    </div>
  )
}

export function formatHalfLife(weeks: number | null | undefined): string {
  if (weeks == null) return '>24 周'
  return `${weeks} 周`
}

export function MatrixCell({ value, max }: { value: number; max: number }) {
  const opacity = value <= 0 ? 0 : 0.15 + 0.75 * (value / Math.max(max, 1))
  return (
    <td className="min-w-12 border-b border-border/50 px-2 py-2 text-right font-sans text-[12px] tabular-nums">
      <span
        className="inline-flex min-w-8 justify-end rounded-[4px] px-1.5 py-0.5"
        style={value > 0 ? { backgroundColor: `rgba(184,134,11,${opacity})` } : undefined}
      >
        {value > 0 ? value : '·'}
      </span>
    </td>
  )
}
