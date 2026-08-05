import type { TrendingEntity, TrendingData } from '@/hooks/useCommunity'
import type { FeedMeta } from '@/types/community'
import { MobileBottomSheet } from '@/components/mobile'

import { CommunitySidebar } from './CommunitySidebar'

interface MobileSidebarDrawerProps {
  posts: { posted_at: string }[]
  meta: FeedMeta | null
  trendingArtists?: TrendingEntity[]
  trendingTracks?: TrendingEntity[]
  latestNo1?: TrendingData['latest_no1']
  latestDebut?: TrendingData['latest_debut']
  open: boolean
  onClose: () => void
}

export function MobileSidebarDrawer({
  posts, meta, trendingArtists, trendingTracks,
  latestNo1, latestDebut, open, onClose,
}: MobileSidebarDrawerProps) {
  return (
    <MobileBottomSheet
      open={open}
      onOpenChange={(next) => { if (!next) onClose() }}
      eyebrow="Community / Pulse"
      title="社区趋势"
      description="查看当前榜单快讯、热议音乐与社区账号。"
      dataSheet="community-trending"
    >
      <CommunitySidebar
        posts={posts}
        meta={meta}
        trendingArtists={trendingArtists}
        trendingTracks={trendingTracks}
        latestNo1={latestNo1}
        latestDebut={latestDebut}
      />
    </MobileBottomSheet>
  )
}
