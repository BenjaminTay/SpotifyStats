import { GlassCard } from '@/components/shared/GlassCard'
import { displayName } from '@/lib/chinese'
import { Video } from 'lucide-react'
import { fmtInt } from './habitsPrimitives'
import type { VideoData } from '@/types/account'

function fmtPct(n: number, total: number): string {
  if (total === 0) return '0%'
  return `${Math.round((n / total) * 100)}%`
}

interface Props {
  video: VideoData
}

export function VideoSection({ video }: Props) {
  return (
    <GlassCard className="p-6">
      <div className="space-y-6">
        <div className="flex items-center gap-2.5">
          <Video className="h-5 w-5 text-rose-500" />
          <h2 className="mb-5 font-serif text-xl font-semibold">视频分析</h2>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {/* left: stats */}
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg border border-border bg-muted/30 p-3">
                <p className="font-serif text-xl font-bold">
                  {fmtInt(video.total_video_plays)}
                </p>
                <p className="font-sans text-[10px] uppercase tracking-[0.5px] text-muted-foreground">
                  视频播放
                </p>
              </div>
              <div className="rounded-lg border border-border bg-muted/30 p-3">
                <p className="font-serif text-xl font-bold">
                  {fmtInt(video.total_audio_plays)}
                </p>
                <p className="font-sans text-[10px] uppercase tracking-[0.5px] text-muted-foreground">
                  音频播放
                </p>
              </div>
              <div className="rounded-lg border border-border bg-muted/30 p-3">
                <p className="font-serif text-xl font-bold">
                  {Math.round(video.avg_duration_sec)}s
                </p>
                <p className="font-sans text-[10px] uppercase tracking-[0.5px] text-muted-foreground">
                  平均时长
                </p>
              </div>
              <div className="rounded-lg border border-border bg-muted/30 p-3">
                <p className="font-serif text-xl font-bold">
                  {fmtPct(
                    video.total_video_plays,
                    video.total_video_plays + video.total_audio_plays,
                  )}
                </p>
                <p className="font-sans text-[10px] uppercase tracking-[0.5px] text-muted-foreground">
                  视频占比
                </p>
              </div>
            </div>
          </div>

          {/* right: top video tracks */}
          <div className="space-y-3">
            <p className="font-sans text-[11px] font-semibold uppercase tracking-[1px] text-muted-foreground">
              视频播放 Top 5
            </p>
            {video.top_video_tracks.length === 0 ? (
              <p className="font-sans text-sm text-muted-foreground">
                暂无视频曲目数据
              </p>
            ) : (
              <div className="space-y-2">
                {video.top_video_tracks.slice(0, 5).map((t, idx) => (
                  <div
                    key={`${t.track_name}-${t.artist_name}`}
                    className="flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-muted/30"
                  >
                    <span className="w-5 text-right font-sans text-xs tabular-nums text-muted-foreground">
                      {idx + 1}
                    </span>
                    {t.cover_url && (
                      <img
                        src={t.cover_url}
                        alt={t.track_name}
                        className="h-10 w-10 shrink-0 rounded border border-border object-cover"
                      />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-sans text-sm">
                        {displayName(t.track_name)}
                      </p>
                      <p className="truncate font-sans text-xs text-muted-foreground">
                        {displayName(t.artist_name)}
                      </p>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="font-sans text-xs font-semibold tabular-nums">
                        {fmtInt(t.video_plays)}
                      </p>
                      <p className="font-sans text-[9px] text-muted-foreground">
                        视频 · {fmtInt(t.audio_plays)} 音频
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </GlassCard>
  )
}
