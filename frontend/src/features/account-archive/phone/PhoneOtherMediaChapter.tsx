import { Headphones, Radio, Video } from 'lucide-react'

import { useArchiveOtherMedia } from '@/features/account-archive/hooks/useAccountArchive'
import { useArchiveSection } from '@/features/account-archive/hooks/useArchiveSection'
import { formatArchiveHours, formatArchiveNumber } from '@/features/account-archive/model/archiveModel'
import { PhoneArchiveError, PhoneArchiveLoading, PhoneArchiveUnavailable, PhoneChapterHeading } from './PhoneArchivePrimitives'

export function PhoneOtherMediaChapter() {
  const { ref, enabled } = useArchiveSection()
  const query = useArchiveOtherMedia(enabled)
  return (
    <section ref={ref} id="archive-other-media" className="phone-archive-chapter" data-archive-section="other-media">
      <PhoneChapterHeading number="07" eyebrow="Beyond the record shelf" title="音乐之外" description="播客和视频只保留足够可靠的累计事实，不用稀疏样本硬凑趋势。" />
      {!enabled || query.isLoading ? <PhoneArchiveLoading /> : null}
      {query.isError ? <PhoneArchiveError onRetry={() => void query.refetch()} /> : null}
      {query.data?.status === 'unavailable' ? <PhoneArchiveUnavailable>当前导入没有播客或视频记录，本章不会占用额外空间。</PhoneArchiveUnavailable> : null}
      {query.data && query.data.status !== 'unavailable' ? (
        <div className="phone-archive-media-stack">
          <article>
            <Radio />
            <p>Podcast ledger</p>
            <strong>{formatArchiveHours(query.data.podcast.effective_ms)}</strong>
            <span>{formatArchiveNumber(query.data.podcast.unique_shows)} 个节目 · {formatArchiveNumber(query.data.podcast.active_months)} 个活跃月</span>
            <ol>{query.data.podcast.top_shows.slice(0, 3).map((show, index) => <li key={show.show_name}><small>{index + 1}</small><span>{show.show_name}</span><b>{formatArchiveHours(show.effective_ms)}</b></li>)}</ol>
          </article>
          <article>
            <Video />
            <p>Video trace</p>
            <strong>{formatArchiveHours(query.data.video.effective_ms, 2)}</strong>
            <span>{formatArchiveNumber(query.data.video.effective_events)} 个有效事件 · {formatArchiveNumber(query.data.video.active_days)} 个活跃日</span>
            <div className="phone-archive-media-compare"><span><Headphones />音频<b>{formatArchiveHours(query.data.audio_video_comparison.audio_effective_ms, 0)}</b></span><span><Video />视频<b>{formatArchiveHours(query.data.audio_video_comparison.video_effective_ms, 2)}</b></span></div>
          </article>
        </div>
      ) : null}
    </section>
  )
}
