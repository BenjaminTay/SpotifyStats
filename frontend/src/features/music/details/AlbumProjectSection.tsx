import { CalendarDays, Disc3, ListMusic } from 'lucide-react'
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

export function AlbumProjectSection({ project }: Props) {
  const total = Math.max(project.play_count, 1)
  const visibleTracks = project.tracks.slice(0, 12)

  return (
    <section className="space-y-4">
      <div className="grid gap-3 md:grid-cols-3">
        <GlassCard className="p-4">
          <div className="flex items-start gap-3">
            <Disc3 className="mt-0.5 h-4 w-4 text-accent-foreground" />
            <div>
              <p className="font-sans text-[12px] text-muted-foreground">专辑项目播放</p>
              <p className="mt-1 font-serif text-2xl font-semibold">{formatNumber(project.play_count)}</p>
            </div>
          </div>
        </GlassCard>
        <GlassCard className="p-4">
          <div className="flex items-start gap-3">
            <ListMusic className="mt-0.5 h-4 w-4 text-accent-foreground" />
            <div>
              <p className="font-sans text-[12px] text-muted-foreground">项目曲目</p>
              <p className="mt-1 font-serif text-2xl font-semibold">{project.unique_canonical_songs}</p>
            </div>
          </div>
        </GlassCard>
        <GlassCard className="p-4">
          <div className="flex items-start gap-3">
            <CalendarDays className="mt-0.5 h-4 w-4 text-accent-foreground" />
            <div>
              <p className="font-sans text-[12px] text-muted-foreground">榜单发行日</p>
              <p className="mt-1 font-sans text-[15px] font-semibold">{project.release_date || '未知'}</p>
            </div>
          </div>
        </GlassCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(280px,0.75fr)]">
        <GlassCard className="p-4">
          <div className="mb-4 flex items-center justify-between gap-4">
            <div>
              <p className="font-serif text-xl font-semibold">来源拆分</p>
              <p className="mt-1 font-sans text-[12px] text-muted-foreground">
                {project.album_project_name} · {project.artist_name}
              </p>
            </div>
            <span className="shrink-0 rounded-full border border-border px-3 py-1 font-sans text-[12px] text-muted-foreground">
              {formatNumber(project.source_breakdown.length)} 来源
            </span>
          </div>

          <div className="space-y-3">
            {project.source_breakdown.map((item) => {
              const pct = Math.round((item.play_count / total) * 100)
              return (
                <div key={`${item.source_bucket}-${item.source_album_id ?? 'none'}`} className="space-y-1.5">
                  <div className="flex items-start justify-between gap-3 font-sans text-[13px]">
                    <div className="min-w-0">
                      <p className="truncate font-semibold">{item.source_album_name || BUCKET_LABELS[item.source_bucket] || item.source_bucket}</p>
                      <p className="mt-0.5 text-[12px] text-muted-foreground">{BUCKET_LABELS[item.source_bucket] ?? item.source_bucket}</p>
                    </div>
                    <p className="shrink-0 text-right tabular-nums text-muted-foreground">
                      {formatNumber(item.play_count)} · {pct}%
                    </p>
                  </div>
                  <div className="h-2 overflow-hidden rounded-[4px] bg-muted">
                    <div className="h-full rounded-[4px] bg-accent-foreground" style={{ width: `${Math.max(pct, 3)}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        </GlassCard>

        <GlassCard className="p-4">
          <div className="mb-4">
            <p className="font-serif text-xl font-semibold">项目曲目</p>
            <p className="mt-1 font-sans text-[12px] text-muted-foreground">
              {formatNumber(project.tracks.length)} 首归属曲目
            </p>
          </div>

          <div className="space-y-2">
            {visibleTracks.map((track) => (
              <div key={`${track.canonical_song_key}-${track.track_id}`} className="rounded-[6px] border border-border/70 px-3 py-2">
                <p className="truncate font-sans text-[13px] font-semibold">{track.canonical_song_name || track.track_name}</p>
                <p className="mt-0.5 truncate font-sans text-[12px] text-muted-foreground">
                  {BUCKET_LABELS[track.source_bucket ?? ''] ?? track.source_bucket ?? '项目曲目'}
                </p>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>
    </section>
  )
}
