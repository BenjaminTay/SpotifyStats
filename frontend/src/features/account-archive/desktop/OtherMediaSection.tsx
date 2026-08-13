import { Headphones, Radio, Video } from 'lucide-react'

import { useArchiveOtherMedia } from '@/features/account-archive/hooks/useAccountArchive'
import { useArchiveSection } from '@/features/account-archive/hooks/useArchiveSection'
import { formatArchiveHours, formatArchiveNumber } from '@/features/account-archive/model/archiveModel'
import {
  ArchiveError,
  ArchiveLoading,
  ArchiveSectionHeading,
  ArchiveUnavailable,
} from '@/features/account-archive/components/ArchivePrimitives'

export function OtherMediaSection() {
  const { ref, enabled } = useArchiveSection()
  const query = useArchiveOtherMedia(enabled)

  return (
    <section ref={ref} id="archive-other-media" className="archive-chapter archive-other-chapter" data-archive-section="other-media">
      <ArchiveSectionHeading
        number="07"
        eyebrow="Beyond the record shelf"
        title="音乐之外"
        description="播客和视频只保留足够可靠的累计事实。没有单集总时长，就不展示完播率；视频样本有限，也不硬凑趋势。"
      />
      {!enabled || query.isLoading ? <ArchiveLoading /> : null}
      {query.isError && <ArchiveError onRetry={() => void query.refetch()} />}
      {query.data?.status === 'unavailable' && (
        <ArchiveUnavailable>当前导入没有播客或视频记录，本章不会占用额外空间。</ArchiveUnavailable>
      )}
      {query.data && query.data.status !== 'unavailable' && (
        <div className="archive-media-grid">
          <article className="archive-media-card archive-media-podcast">
            <Radio aria-hidden="true" />
            <p>Podcast ledger</p>
            <strong>{formatArchiveHours(query.data.podcast.effective_ms)}</strong>
            <span>{formatArchiveNumber(query.data.podcast.unique_shows)} 个节目 · {formatArchiveNumber(query.data.podcast.active_months)} 个活跃月</span>
            <div className="archive-show-list">
              {query.data.podcast.top_shows.map((show, index) => (
                <div key={show.show_name}>
                  <small>{String(index + 1).padStart(2, '0')}</small>
                  <span>{show.show_name}</span>
                  <strong>{formatArchiveHours(show.effective_ms)}</strong>
                </div>
              ))}
            </div>
            <small>{formatArchiveNumber(query.data.podcast.returning_shows)} 个节目在至少两个不同日期出现</small>
          </article>

          <article className="archive-media-card archive-media-video">
            <Video aria-hidden="true" />
            <p>Video trace</p>
            <strong>{formatArchiveHours(query.data.video.effective_ms, 2)}</strong>
            <span>{formatArchiveNumber(query.data.video.effective_events)} 个有效逻辑事件 · {formatArchiveNumber(query.data.video.active_days)} 个活跃日</span>
            <div className="archive-media-comparison">
              <div>
                <span><Headphones />音频</span>
                <i style={{ width: '100%' }} />
                <strong>{formatArchiveHours(query.data.audio_video_comparison.audio_effective_ms, 0)}</strong>
              </div>
              <div>
                <span><Video />视频</span>
                <i style={{ width: `${Math.max(Math.min((query.data.audio_video_comparison.video_effective_ms / Math.max(query.data.audio_video_comparison.audio_effective_ms, 1)) * 100, 100), 1)}%` }} />
                <strong>{formatArchiveHours(query.data.audio_video_comparison.video_effective_ms, 2)}</strong>
              </div>
            </div>
            <small>音频与视频使用同一播放观察期和有效播放口径。</small>
          </article>
        </div>
      )}
    </section>
  )
}
