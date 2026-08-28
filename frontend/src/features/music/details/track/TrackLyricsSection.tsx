import { GlassCard } from '@/components/shared/GlassCard'
import { FormattedText } from '@/components/shared/FormattedText'
import { Skeleton } from '@/components/ui/skeleton'
import { ExternalLink } from 'lucide-react'
import type { TrackDetailResponse, LyricsData, TrackEnrichmentResponse } from '@/types/billboard'
import { displayName, useChineseTextVersion } from '@/lib/chinese'

function formatDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  return `${min}:${sec.toString().padStart(2, '0')}`
}

interface Props {
  data: TrackDetailResponse
  enrichment: TrackEnrichmentResponse | null
  lyrics: LyricsData | null
  lyricsLoading: boolean
}

export function TrackLyricsSection({ data, enrichment, lyrics, lyricsLoading }: Props) {
  useChineseTextVersion()
  return (
    <div className="mobile-track-lyrics mb-8">
      {/* Genius Song Info */}
      {enrichment?.genius && (
        <div className="mb-6">
          <h3 className="mb-3 font-serif text-xl font-semibold">歌曲信息</h3>
          <GlassCard className="p-5">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {enrichment.genius.album_name && (
                <div>
                  <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    收录专辑
                  </p>
                  <p className="mt-1 font-sans text-[13px] font-semibold">{displayName(enrichment.genius.album_name)}</p>
                </div>
              )}
              {enrichment.genius.release_date && (
                <div>
                  <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    发行日期
                  </p>
                  <p className="mt-1 font-sans text-[13px] font-semibold">{enrichment.genius.release_date}</p>
                </div>
              )}
              {data.meta?.popularity != null && (
                <div>
                  <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    Spotify 流行度
                  </p>
                  <p className="mt-1 font-sans text-[13px] font-semibold">{data.meta.popularity}/100</p>
                </div>
              )}
              {data.meta?.duration_ms && (
                <div>
                  <p className="font-sans text-[10px] font-bold uppercase tracking-[1.2px] text-muted-foreground">
                    时长
                  </p>
                  <p className="mt-1 font-sans text-[13px] font-semibold">{formatDuration(data.meta.duration_ms)}</p>
                </div>
              )}
            </div>
            {enrichment.genius.url && (
              <a
                href={enrichment.genius.url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 inline-flex items-center gap-1.5 font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
              >
                在 Genius 上查看歌曲详情
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </GlassCard>
        </div>
      )}

      {/* Wikipedia Song Info */}
      {enrichment?.wiki && (
        <div className="mb-6">
          <h3 className="mb-3 font-serif text-xl font-semibold">歌曲背景</h3>
          <GlassCard className="p-5">
            <FormattedText
              text={enrichment.wiki.summary_zh || enrichment.wiki.summary || enrichment.wiki.sections_zh?.background || enrichment.wiki.sections.background || '暂无详细信息'}
              className="font-sans text-[14px] leading-relaxed text-foreground/85"
            />
            {enrichment.wiki.url && (
              <a
                href={enrichment.wiki.url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 inline-flex items-center gap-1.5 font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
              >
                在 Wikipedia 上阅读更多
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </GlassCard>
        </div>
      )}

      {lyricsLoading ? (
        <GlassCard className="mobile-lyrics-card p-8">
          <div className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-4/6" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/6" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-4/6" />
          </div>
        </GlassCard>
      ) : lyrics && lyrics.found ? (
        <GlassCard className="mobile-lyrics-card p-8">
          <div>
            {lyrics.lyrics.split('\n').map((line, i) => {
              const trimmed = line.trim()
              const isSection = trimmed.startsWith('[') && trimmed.endsWith(']')
              return (
                <p
                  key={i}
                  className={
                    isSection
                      ? 'mt-6 mb-3 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-muted-foreground first:mt-0'
                      : line === ''
                        ? 'h-4'
                        : 'mobile-lyric-line font-serif text-[17px] leading-[1.85]'
                  }
                >
                  {isSection ? trimmed : (line || ' ')}
                </p>
              )
            })}
            {lyrics.genius_url && (
              <a
                href={lyrics.genius_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-8 inline-flex items-center gap-1.5 font-sans text-[12px] text-muted-foreground transition-colors hover:text-accent-foreground"
              >
                在 Genius 上查看完整歌词
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </GlassCard>
      ) : (
        <GlassCard className="mobile-lyrics-card p-8 text-center">
          <p className="font-sans text-[14px] text-muted-foreground">
            未找到 Genius 歌词
          </p>
        </GlassCard>
      )}
    </div>
  )
}
