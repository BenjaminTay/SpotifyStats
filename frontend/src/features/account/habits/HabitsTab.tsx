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
import { useViewportMode } from '@/hooks/useViewportMode'
import { MobileHabitSection } from '@/features/mobile/account/MobileHabitSection'

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
  const isPhone = useViewportMode() === 'phone'
  const personality = useMemo(
    () => inferPersonality(search, video),
    [search, video],
  )

  if (isPhone) {
    return (
      <div className="mobile-account-section space-y-4">
        <HabitsPersonalityHero personality={personality} />
        <MobileHabitSection title="搜索编年史" summary="搜索词、意向与活跃时段" defaultOpen>
          {!search.available || search.empty ? <UnavailableBlock title="搜索" /> : <SearchHistorySection search={search} />}
        </MobileHabitSection>
        <MobileHabitSection title="粉丝层级" summary="超级粉丝与艺人分层">
          {!tiers.available || tiers.empty ? <UnavailableBlock title="粉丝层级" /> : <FanTiersSection tiers={tiers} />}
        </MobileHabitSection>
        <MobileHabitSection title="播客" summary="节目与月度收听趋势">
          {!podcast.available || podcast.empty ? <UnavailableBlock title="播客" /> : <PodcastSection podcast={podcast} />}
        </MobileHabitSection>
        <MobileHabitSection title="Marquee 推广" summary="曝光与真实收听转化">
          {!marquee.available || marquee.empty ? <UnavailableBlock title="Marquee 推广" /> : <MarqueeSection marquee={marquee} />}
        </MobileHabitSection>
        <MobileHabitSection title="视频" summary="视频观看习惯与偏好">
          {!video.available || video.empty ? <UnavailableBlock title="视频" /> : <VideoSection video={video} />}
        </MobileHabitSection>
      </div>
    )
  }

  return (
    <div className="mobile-account-section space-y-8">
      <HabitsPersonalityHero personality={personality} />
      {!search.available || search.empty ? (
        <UnavailableBlock title="搜索" />
      ) : (
        <SearchHistorySection search={search} />
      )}
      {!tiers.available || tiers.empty ? (
        <UnavailableBlock title="粉丝层级" />
      ) : (
        <FanTiersSection tiers={tiers} />
      )}
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
      {!video.available || video.empty ? (
        <UnavailableBlock title="视频" />
      ) : (
        <VideoSection video={video} />
      )}
    </div>
  )
}
