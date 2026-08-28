import { Radio, Video } from 'lucide-react'

import { useArchiveOtherMedia } from '@/features/account-archive/hooks/useAccountArchive'
import { useArchiveSection } from '@/features/account-archive/hooks/useArchiveSection'
import { formatArchiveHours, formatArchiveNumber } from '@/features/account-archive/model/archiveModel'
import { PhoneArchiveError, PhoneArchiveLoading, PhoneArchiveUnavailable, PhoneChapterHeading, PhoneEntityCard } from './PhoneArchivePrimitives'
import { useDisplayName } from '@/lib/chinese'

function PhonePodcastName({ name, publisher }: { name: string; publisher?: string | null }) {
  const displayShowName = useDisplayName(name)
  const displayPublisher = useDisplayName(publisher ?? '')
  return <span className="phone-archive-podcast-copy"><strong>{displayShowName}</strong>{publisher ? <span>{displayPublisher}</span> : null}</span>
}

export function PhoneOtherMediaChapter() {
  const { ref, enabled } = useArchiveSection()
  const query = useArchiveOtherMedia(enabled)
  return (
    <section ref={ref} id="archive-other-media" className="phone-archive-chapter" data-archive-section="other-media">
      <PhoneChapterHeading number="07" title="音乐之外" />
      {!enabled || query.isLoading ? <PhoneArchiveLoading /> : null}
      {query.isError ? <PhoneArchiveError onRetry={() => void query.refetch()} /> : null}
      {query.data?.status === 'unavailable' ? <PhoneArchiveUnavailable>当前导入没有播客或视频记录，本章不会占用额外空间。</PhoneArchiveUnavailable> : null}
      {query.data && query.data.status !== 'unavailable' ? (
        <div className="phone-archive-media-stack">
          <article>
            <Radio />
            <div className="phone-archive-media-head">
              <div><p>播客</p><span>{formatArchiveNumber(query.data.podcast.unique_shows)} 个节目 · {formatArchiveNumber(query.data.podcast.active_months)} 个活跃月</span></div>
              <strong>{formatArchiveHours(query.data.podcast.effective_ms)}</strong>
            </div>
            <div className="phone-archive-podcast-list">
              <p>播放最多的电台和播客</p>
              {query.data.podcast.top_shows.slice(0, 3).map((show, index) => (
                <div
                  key={show.show_name}
                  className={show.cover_url ? 'phone-archive-podcast-row' : 'phone-archive-podcast-row phone-archive-podcast-row-no-cover'}
                >
                  <small>{String(index + 1).padStart(2, '0')}</small>
                  {show.cover_url ? (
                    <span className="phone-archive-podcast-cover" aria-hidden="true">
                      <img src={show.cover_url} alt="" loading="lazy" />
                    </span>
                  ) : null}
                  <PhonePodcastName name={show.show_name} publisher={show.publisher} />
                  <b>{formatArchiveHours(show.effective_ms)}</b>
                </div>
              ))}
            </div>
          </article>
          <article>
            <Video />
            <div className="phone-archive-media-head">
              <div><p>视频</p><span>{formatArchiveNumber(query.data.video.effective_events)} 次播放 · {formatArchiveNumber(query.data.video.active_days)} 个活跃日</span></div>
              <strong>{formatArchiveHours(query.data.video.effective_ms, 2)}</strong>
            </div>
            <div className="phone-archive-video-list">
              <p>播放最多的视频</p>
              {query.data.video.top_tracks.map((track, index) => (
                <PhoneEntityCard
                  key={`${track.track_name}-${track.artist_name}`}
                  ordinal={index + 1}
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
      ) : null}
    </section>
  )
}
