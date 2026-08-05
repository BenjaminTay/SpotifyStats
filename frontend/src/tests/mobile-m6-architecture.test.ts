import { describe, expect, it } from 'vitest'

import accountPageSource from '../pages/AccountCenterPage.tsx?raw'
import aiExperienceSource from '../features/ai-insights/AiInsightsExperience.tsx?raw'
import chatComposerSource from '../features/ai-insights/ChatComposer.tsx?raw'
import chatDrawerSource from '../features/ai-insights/ChatSessionDrawer.tsx?raw'
import communityExperienceSource from '../features/community/CommunityExperience.tsx?raw'
import communityDrawerSource from '../features/community/MobileSidebarDrawer.tsx?raw'
import routeContextSource from '../components/layout/routeContext.ts?raw'
import settingsPageSource from '../pages/SettingsPage.tsx?raw'
import mobileSettingsSource from '../features/mobile/settings/MobileSettingsExperience.tsx?raw'
import savedTracksSource from '../features/account/collection/components/SavedTracksBrowser.tsx?raw'
import accountLeaderboardSource from '../features/account/collection/components/LeaderboardBlock.tsx?raw'
import playlistBrowserSource from '../features/account/collection/components/PlaylistsBrowser.tsx?raw'
import habitsTabSource from '../features/account/habits/HabitsTab.tsx?raw'
import mobileHabitSectionSource from '../features/mobile/account/MobileHabitSection.tsx?raw'

describe('M6 mobile community, AI, account and settings architecture', () => {
  it('consolidates community controls into sheets without a competing floating action', () => {
    expect(communityExperienceSource).toContain('MobileCommunityFilters')
    expect(communityExperienceSource).toContain('MobileCommunityFilterBar')
    expect(communityExperienceSource).not.toContain('fixed bottom-6 right-6')
    expect(communityExperienceSource).toContain('isCompact')
    expect(communityExperienceSource).toContain('社区趋势')
    expect(communityDrawerSource).toContain('MobileBottomSheet')
    expect(communityDrawerSource).toContain('community-trending')
  })

  it('uses top-bar history and shared sheets for mobile AI while retaining keyboard mode', () => {
    expect(aiExperienceSource).not.toContain('fixed bottom-6 right-6')
    expect(aiExperienceSource).toContain('isCompact')
    expect(chatDrawerSource).toContain('MobileBottomSheet')
    expect(chatDrawerSource).toContain('ai-history')
    expect(chatComposerSource).toContain('data-mobile-input-mode="true"')
    expect(aiExperienceSource).toContain('mobile-ai-mode-switch')
  })

  it('gives account center a dedicated phone hero and accessible tab presentation', () => {
    expect(accountPageSource).toContain('MobileAccountHero')
    expect(accountPageSource).toContain('role="tablist"')
    expect(accountPageSource).toContain('aria-selected={activeTab === tab.key}')
    for (const source of [savedTracksSource, accountLeaderboardSource, playlistBrowserSource]) {
      expect(source).toContain('MobileEntityRow')
      expect(source).toContain("useViewportMode() === 'phone'")
      expect(source).toContain('<table')
    }
    expect(habitsTabSource).toContain('MobileHabitSection')
    expect(mobileHabitSectionSource).toContain('aria-expanded={open}')
  })

  it('short-circuits phone settings before desktop governance workbenches mount', () => {
    const mobileReturn = settingsPageSource.indexOf('if (isPhone)')
    const metadataRender = settingsPageSource.indexOf('<MusicMetadataSection />')
    expect(mobileReturn).toBeGreaterThan(0)
    expect(metadataRender).toBeGreaterThan(mobileReturn)
    expect(mobileSettingsSource).not.toContain('MusicMetadataSection')
    expect(mobileSettingsSource).not.toContain('DataImportSection')
    expect(mobileSettingsSource).toContain('在电脑上管理')
    expect(mobileSettingsSource).toContain("searchParams.get('return_to')")
    expect(mobileSettingsSource).toContain('Preferences / Mobile')
  })

  it('keeps community detail routes push-only and bottom-nav free', () => {
    expect(routeContextSource).toContain("pathname.startsWith('/community/post/')")
    expect(routeContextSource).toContain("pathname.startsWith('/community/account/')")
    const detailBlock = routeContextSource.slice(
      routeContextSource.indexOf("pathname.startsWith('/community/post/')"),
      routeContextSource.indexOf("pathname === '/ai-insights'"),
    )
    expect(detailBlock).toContain("mobileTopBarMode: 'push'")
    expect(detailBlock).not.toContain('showMobileBottomNav: true')
  })
})
