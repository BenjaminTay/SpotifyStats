import { useMemo } from 'react'
import { HabitsPersonalityHero } from './HabitsPersonalityHero'
import { SearchHistorySection } from './SearchHistorySection'
import { FanTiersSection } from './FanTiersSection'
import { PodcastSection } from './PodcastSection'
import { MarqueeSection } from './MarqueeSection'
import { VideoSection } from './VideoSection'
import { UnavailableBlock } from './habitsPrimitives'
import { inferPersonality } from './habitsData'
import type {
  SearchData,
  ArtistTiersData,
  MarqueeData,
  PodcastData,
  VideoData,
} from '@/types/account'

interface HabitsTabProps {
  search: SearchData
  tiers: ArtistTiersData
  marquee: MarqueeData
  podcast: PodcastData
  video: VideoData
}

export function HabitsTab({
  search,
  tiers,
  marquee,
  podcast,
  video,
}: HabitsTabProps) {
  const personality = useMemo(
    () => inferPersonality(search, video),
    [search, video],
  )

  return (
    <div className="space-y-8">
      {/* 1. Listening Personality Hero */}
      <HabitsPersonalityHero personality={personality} />

      {/* 2. Search Chronicles */}
      {!search.available || search.empty ? (
        <UnavailableBlock title="搜索" />
      ) : (
        <SearchHistorySection search={search} />
      )}

      {/* 3. Fan Tiers */}
      {!tiers.available || tiers.empty ? (
        <UnavailableBlock title="粉丝层级" />
      ) : (
        <FanTiersSection tiers={tiers} />
      )}

      {/* 4. Podcast + Marquee */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {!podcast.available || podcast.empty ? (
          <UnavailableBlock title="播客" />
        ) : (
          <PodcastSection podcast={podcast} />
        )}
        {!marquee.available || marquee.empty ? (
          <UnavailableBlock title="Marquee 推广" />
        ) : (
          <MarqueeSection marquee={marquee} />
        )}
      </div>

      {/* 5. Video Analysis */}
      {!video.available || video.empty ? (
        <UnavailableBlock title="视频" />
      ) : (
        <VideoSection video={video} />
      )}
    </div>
  )
}
