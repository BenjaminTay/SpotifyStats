import { describe, expect, it } from 'vitest'

import mobileTopBarSource from '../components/layout/MobileTopBar.tsx?raw'
import recentPlaysSource from '../components/shared/RecentPlaysSection.tsx?raw'
import artistAlbumsSource from '../features/music/details/ArtistAlbumsSection.tsx?raw'
import artistDetailSource from '../features/music/details/ArtistDetailExperience.tsx?raw'
import albumDetailSource from '../features/music/details/AlbumDetailExperience.tsx?raw'
import musicTracksSource from '../features/music/details/MusicTracksSection.tsx?raw'
import trackDetailSource from '../features/music/details/TrackDetailExperience.tsx?raw'
import searchPageSource from '../features/music/search/MusicSearchPage.tsx?raw'
import searchResultsSource from '../features/music/search/MusicSearchResults.tsx?raw'
import mobileDetailSource from '../features/mobile/music/MobileMusicDetail.tsx?raw'

describe('M5 mobile music architecture', () => {
  it('keeps full-page search URL-addressable and safe for composition input', () => {
    expect(searchPageSource).toContain('useSearchParams')
    expect(searchPageSource).toContain('onCompositionStart')
    expect(searchPageSource).toContain('onCompositionEnd')
    expect(searchPageSource).toContain('useMusicSearchCandidates')
    expect(searchPageSource).toContain('useMusicSearchContext')
    expect(searchResultsSource).toContain('MobileEntityRow')
    expect(searchPageSource).toContain('pageSize = kindParam ? 20 : 5')
    expect(searchPageSource).not.toContain('includeChart: true')
    expect(searchResultsSource).not.toContain('weeks_at_no1')
  })

  it('uses separate phone heroes and URL-backed detail tabs for every music entity', () => {
    for (const source of [trackDetailSource, albumDetailSource, artistDetailSource]) {
      expect(source).toContain('useViewportMode')
      expect(source).toContain('MobileMusicDetailHero')
      expect(source).toContain('MobileMusicDetailNav')
      expect(source).toContain('setSearchParams')
    }
    expect(artistDetailSource).toContain("{ key: 'albums', label: '专辑'")
    expect(artistDetailSource).toContain("{ key: 'career', label: '艺人生涯'")
  })

  it('keeps mobile detail lists vertical while preserving desktop tables', () => {
    for (const source of [musicTracksSource, artistAlbumsSource]) {
      expect(source).toContain('MobileRankList')
      expect(source).toContain('<table')
      expect(source).toContain("useViewportMode() === 'phone'")
    }
    expect(recentPlaysSource).toContain('mobile ? (')
    expect(recentPlaysSource).toContain('MobileEntityRow')
    expect(recentPlaysSource).toContain('<table')
    expect(mobileDetailSource).not.toContain('<table')
  })

  it('moves share and metadata governance into the detail More menu', () => {
    expect(mobileTopBarSource).toContain('music-detail-actions')
    expect(mobileTopBarSource).toContain('metadata=track-credits')
    expect(mobileTopBarSource).toContain('metadata=album-projects')
    expect(mobileTopBarSource).toContain('metadata=artist-identities')
    expect(mobileTopBarSource).toContain('return_to=')
  })
})
