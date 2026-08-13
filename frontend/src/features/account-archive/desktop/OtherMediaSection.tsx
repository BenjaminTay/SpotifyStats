import { Radio, Video } from 'lucide-react'

import { useArchiveOtherMedia } from '@/features/account-archive/hooks/useAccountArchive'
import { useArchiveSection } from '@/features/account-archive/hooks/useArchiveSection'
import { formatArchiveHours, formatArchiveNumber } from '@/features/account-archive/model/archiveModel'
import {
  ArchiveEntityRow,
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
        title="音乐之外"
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
            <p>播客</p>
            <strong>{formatArchiveHours(query.data.podcast.effective_ms)}</strong>
            <span>{formatArchiveNumber(query.data.podcast.unique_shows)} 个节目 · {formatArchiveNumber(query.data.podcast.active_months)} 个活跃月</span>
            <div className="archive-podcast-list">
              <p>播放最多的电台和播客</p>
              {query.data.podcast.top_shows.map((show, index) => (
                <div
                  key={show.show_name}
                  className={show.cover_url ? 'archive-podcast-row' : 'archive-podcast-row archive-podcast-row-no-cover'}
                >
                  <small>{String(index + 1).padStart(2, '0')}</small>
                  {show.cover_url ? (
                    <span className="archive-podcast-cover" aria-hidden="true">
                      <img src={show.cover_url} alt="" loading="lazy" />
                    </span>
                  ) : null}
                  <span className="archive-podcast-copy">
                    <strong>{show.show_name}</strong>
                    {show.publisher ? <span>{show.publisher}</span> : null}
                  </span>
                  <b>{formatArchiveHours(show.effective_ms)}</b>
                </div>
              ))}
            </div>
          </article>

          <article className="archive-media-card archive-media-video">
            <Video aria-hidden="true" />
            <p>视频</p>
            <strong>{formatArchiveHours(query.data.video.effective_ms, 2)}</strong>
            <span>{formatArchiveNumber(query.data.video.effective_events)} 次播放 · {formatArchiveNumber(query.data.video.active_days)} 个活跃日</span>
            <div className="archive-video-list">
              <p>播放最多的视频</p>
              {query.data.video.top_tracks.map((track, index) => (
                <ArchiveEntityRow
                  key={`${track.track_name}-${track.artist_name}`}
                  index={index + 1}
                  name={track.track_name}
                  artist={track.artist_name}
                  coverUrl={track.cover_url}
                  href={track.deep_link}
                  meta={`${formatArchiveNumber(track.effective_events)} 次`}
                />
              ))}
            </div>
          </article>
        </div>
      )}
    </section>
  )
}
