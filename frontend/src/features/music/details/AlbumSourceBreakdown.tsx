import { GlassCard } from '@/components/shared/GlassCard'
import type { AlbumProject } from '@/types/billboard'

type Props = {
  project: AlbumProject
}

const BUCKET_LABELS: Record<string, string> = {
  original_album: '原版专辑',
  deluxe: '豪华版/扩展版',
  single: '单曲版',
  compilation: '精选集/合辑',
  live_acoustic_remix: 'Live / Acoustic / Remix',
  rerecord: '重录版本',
  other: '其他来源',
  inferred: '推断来源',
}

function formatNumber(value: number) {
  return Number(value || 0).toLocaleString()
}

export function AlbumSourceBreakdown({ project }: Props) {
  const total = Math.max(project.play_count, 1)

  return (
    <GlassCard className="p-6">
      <h3 className="mb-5 font-serif text-2xl font-semibold">来源拆分</h3>
      <p className="mb-4 font-sans text-[12px] text-muted-foreground">
        {project.album_project_name} · {project.artist_name}
      </p>

      <div className="space-y-3">
        {project.source_breakdown.map((item) => {
          const pct = Math.round((item.play_count / total) * 100)
          return (
            <div key={`${item.source_bucket}-${item.source_album_id ?? 'none'}`} className="space-y-1.5">
              <div className="flex items-start justify-between gap-3 font-sans text-[13px]">
                <div className="min-w-0">
                  <p className="truncate font-semibold">
                    {item.source_album_name || BUCKET_LABELS[item.source_bucket] || item.source_bucket}
                  </p>
                  <p className="mt-0.5 text-[12px] text-muted-foreground">
                    {BUCKET_LABELS[item.source_bucket] ?? item.source_bucket}
                  </p>
                </div>
                <p className="shrink-0 text-right tabular-nums text-muted-foreground">
                  {formatNumber(item.play_count)} · {pct}%
                </p>
              </div>
              <div className="h-2 overflow-hidden rounded-[4px] bg-muted">
                <div
                  className="h-full rounded-[4px] bg-accent-foreground"
                  style={{ width: `${Math.max(pct, 3)}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
    </GlassCard>
  )
}
