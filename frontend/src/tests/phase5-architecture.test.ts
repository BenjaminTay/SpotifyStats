import { describe, expect, it } from 'vitest'

import trackDetailSource from '../pages/TrackDetailPage.tsx?raw'
import trackDetailExperienceSource from '../features/music/details/TrackDetailExperience.tsx?raw'
import albumDetailSource from '../pages/AlbumDetailPage.tsx?raw'
import artistDetailSource from '../pages/ArtistDetailPage.tsx?raw'
import recordsPageSource from '../pages/RecordsPage.tsx?raw'
import allTimeChartsPageSource from '../pages/AllTimeChartsPage.tsx?raw'
import numberOnesPageSource from '../pages/NumberOnesPage.tsx?raw'
import billboardPageSource from '../pages/BillboardPage.tsx?raw'
import billboardVersusPageSource from '../pages/BillboardVersusPage.tsx?raw'
import accountCenterPageSource from '../pages/AccountCenterPage.tsx?raw'
import habitsTabSource from '../features/account/habits/HabitsTab.tsx?raw'
import habitsPersonalityHeroSource from '../features/account/habits/HabitsPersonalityHero.tsx?raw'
import searchHistorySectionSource from '../features/account/habits/SearchHistorySection.tsx?raw'
import fanTiersSectionSource from '../features/account/habits/FanTiersSection.tsx?raw'
import podcastSectionSource from '../features/account/habits/PodcastSection.tsx?raw'
import marqueeSectionSource from '../features/account/habits/MarqueeSection.tsx?raw'
import videoSectionSource from '../features/account/habits/VideoSection.tsx?raw'
import collectionTabSource from '../pages/account/CollectionTab.tsx?raw'
import aiInsightsPageSource from '../pages/AiInsightsPage.tsx?raw'
import communityPageSource from '../pages/CommunityPage.tsx?raw'
import communityAccountPageSource from '../pages/CommunityAccountPage.tsx?raw'
import postDetailPageSource from '../pages/PostDetailPage.tsx?raw'

import numberOnesExperienceSource from '../features/billboard/number-ones/NumberOnesExperience.tsx?raw'
import versusExperienceSource from '../features/billboard/versus/VersusExperience.tsx?raw'
import artistDetailExperienceSource from '../features/music/details/ArtistDetailExperience.tsx?raw'
import albumDetailExperienceSource from '../features/music/details/AlbumDetailExperience.tsx?raw'
import albumEraSectionSource from '../features/music/details/AlbumEraSection.tsx?raw'
import albumProjectSectionSource from '../features/music/details/AlbumProjectSection.tsx?raw'
import communityExperienceSource from '../features/community/CommunityExperience.tsx?raw'
import communityAccountExperienceSource from '../features/community/CommunityAccountExperience.tsx?raw'
import postDetailExperienceSource from '../features/community/PostDetailExperience.tsx?raw'
import aiInsightsExperienceSource from '../features/ai-insights/AiInsightsExperience.tsx?raw'
import chatInterfaceSource from '../features/ai-insights/ChatInterface.tsx?raw'
import aiInsightsTimeSelectorsSource from '../features/ai-insights/AiInsightsTimeSelectors.tsx?raw'
import chatMessageListSource from '../features/ai-insights/ChatMessageList.tsx?raw'
import trackOverviewSectionSource from '../features/music/details/track/TrackOverviewSection.tsx?raw'
import trackLyricsSectionSource from '../features/music/details/track/TrackLyricsSection.tsx?raw'

import mastheadSource from '../components/layout/Masthead.tsx?raw'

describe('Phase 5 architecture guardrails', () => {
  it.each([
    ['TrackDetailPage.tsx', trackDetailSource],
    ['AlbumDetailPage.tsx', albumDetailSource],
    ['ArtistDetailPage.tsx', artistDetailSource],
  ])('%s does not keep API responses in module-level Map caches', (_path, content) => {
    expect(content).not.toMatch(/const\s+enrichmentCache\s*=\s*new Map/)
    expect(content).not.toMatch(/const\s+releaseCycleCache\s*=\s*new Map/)
  })

  it('keeps RecordsPage as a route container instead of an all-in-one records module', () => {
    expect(recordsPageSource.split('\n').length).toBeLessThanOrEqual(450)
    expect(recordsPageSource).not.toContain('function MiniRankTable')
    expect(recordsPageSource).not.toContain('function ChampionshipSection')
    expect(recordsPageSource).not.toContain('function LongevitySection')
    expect(recordsPageSource).not.toContain('function MarketSection')
  })

  it('keeps AllTimeChartsPage as a route container with table implementation in feature modules', () => {
    expect(allTimeChartsPageSource.split('\n').length).toBeLessThanOrEqual(450)
    expect(allTimeChartsPageSource).not.toContain('function CoverImg')
    expect(allTimeChartsPageSource).not.toContain('function SortIcon')
    expect(allTimeChartsPageSource).not.toContain('function renderTableCell')
    expect(allTimeChartsPageSource).not.toContain('<table')
  })

  it('keeps NumberOnesPage as a route container instead of a full chart experience module', () => {
    expect(numberOnesPageSource.split('\n').length).toBeLessThanOrEqual(450)
    expect(numberOnesPageSource).not.toContain('function No1BarChart')
    expect(numberOnesPageSource).not.toContain('function AnnualSection')
    expect(numberOnesPageSource).not.toContain('function YearSwitcher')
    expect(numberOnesPageSource).not.toContain('<table')
  })

  it('keeps NumberOnesExperience thin by delegating computation and tab sections', () => {
    expect(numberOnesExperienceSource.split('\n').length).toBeLessThanOrEqual(450)
    expect(numberOnesExperienceSource).not.toContain('function No1BarChart')
    expect(numberOnesExperienceSource).not.toContain('function AnnualSection')
    expect(numberOnesExperienceSource).not.toContain('function YearSwitcher')
    expect(numberOnesExperienceSource).not.toContain('function longestStreak')
  })

  it('keeps music detail pages as route containers', () => {
    expect(artistDetailSource.split('\n').length).toBeLessThanOrEqual(450)
    expect(albumDetailSource.split('\n').length).toBeLessThanOrEqual(450)
    expect(artistDetailSource).not.toContain('function KpiCard')
    expect(albumDetailSource).not.toContain('function KpiCard')
    expect(artistDetailSource).not.toContain('<table')
    expect(albumDetailSource).not.toContain('<table')
  })

  it('keeps shared music detail primitives out of per-entity detail experiences', () => {
    expect(artistDetailExperienceSource).not.toContain('function KpiCard')
    expect(albumDetailExperienceSource).not.toContain('function KpiCard')
    expect(artistDetailExperienceSource).not.toContain('function KpiStrip')
    expect(albumDetailExperienceSource).not.toContain('function KpiStrip')
    expect(artistDetailExperienceSource).not.toContain('function PlaysCell')
    expect(albumDetailExperienceSource).not.toContain('function PlaysCell')
  })

  it('keeps second-pass music detail sections outside large experience files', () => {
    expect(artistDetailExperienceSource).not.toContain('function ReleaseCycleSection')
    expect(artistDetailExperienceSource).not.toContain('function MiniReleaseStat')
    expect(albumDetailExperienceSource).not.toContain('function AlbumStoryCard')
    expect(albumDetailExperienceSource).not.toContain('function InfoRow')
    expect(albumDetailExperienceSource).not.toContain('function MiniStat')
    expect(albumDetailExperienceSource).not.toContain('function MatrixCell')
  })

  it('keeps music detail hero and tab chrome outside large experience files', () => {
    expect(artistDetailExperienceSource.split('\n').length).toBeLessThanOrEqual(860)
    expect(albumDetailExperienceSource.split('\n').length).toBeLessThanOrEqual(820)
    expect(artistDetailExperienceSource).not.toContain('Music / 艺人详情')
    expect(albumDetailExperienceSource).not.toContain('Music / 专辑详情')
    expect(artistDetailExperienceSource).not.toContain('formatFollowers')
    expect(albumDetailExperienceSource).not.toContain('formatReleaseDate')
    expect(albumDetailExperienceSource).not.toContain('formatAlbumType')
  })

  it('keeps music detail overview chart and weekly table outside large experience files', () => {
    expect(artistDetailExperienceSource.split('\n').length).toBeLessThanOrEqual(720)
    expect(albumDetailExperienceSource.split('\n').length).toBeLessThanOrEqual(680)
    expect(artistDetailExperienceSource).not.toContain('艺人排名趋势')
    expect(albumDetailExperienceSource).not.toContain('专辑排名趋势')
    expect(artistDetailExperienceSource).not.toContain('周榜历史')
    expect(albumDetailExperienceSource).not.toContain('周榜历史')
  })

  it('keeps music detail tracks and albums tables outside large experience files', () => {
    expect(artistDetailExperienceSource.split('\n').length).toBeLessThanOrEqual(380)
    expect(albumDetailExperienceSource.split('\n').length).toBeLessThanOrEqual(500)
    expect(artistDetailExperienceSource).not.toContain('入榜曲目')
    expect(albumDetailExperienceSource).not.toContain('入榜曲目')
    expect(artistDetailExperienceSource).not.toContain('暂无专辑入榜数据')
    expect(artistDetailExperienceSource).not.toContain('上榜播放')
    expect(albumDetailExperienceSource).not.toContain('上榜播放')
  })

  it('keeps album release era section outside AlbumDetailExperience', () => {
    expect(albumDetailExperienceSource.split('\n').length).toBeLessThanOrEqual(340)
    expect(albumDetailExperienceSource).not.toContain('发行概览')
    expect(albumDetailExperienceSource).not.toContain('发行走势')
    expect(albumDetailExperienceSource).not.toContain('发行构成')
    expect(albumDetailExperienceSource).not.toContain('收听展开')
    expect(albumDetailExperienceSource).not.toContain('外溢影响')
    expect(albumDetailExperienceSource).not.toContain('你的收听故事')
  })

  it('keeps album project explanation in a feature section', () => {
    expect(albumProjectSectionSource.split('\n').length).toBeLessThanOrEqual(300)
    expect(albumDetailExperienceSource).toContain('AlbumProjectSection')
    expect(albumDetailExperienceSource).not.toContain('source_breakdown')
    expect(albumProjectSectionSource).toContain('source_breakdown')
  })

  it('keeps AlbumEraSection as orchestration instead of a monolithic release archive', () => {
    expect(albumEraSectionSource.split('\n').length).toBeLessThanOrEqual(180)
    expect(albumEraSectionSource).not.toContain('ReleaseTimelineChart')
    expect(albumEraSectionSource).not.toContain('AlbumEnrichmentView')
    expect(albumEraSectionSource).not.toContain('<table')
    expect(albumEraSectionSource).not.toContain('发行构成')
    expect(albumEraSectionSource).not.toContain('收听展开')
    expect(albumEraSectionSource).not.toContain('外溢影响')
  })

  it('keeps community search responsive instead of fixed-width on mobile', () => {
    expect(communityExperienceSource).not.toContain('relative w-[240px]')
  })

  it('keeps masthead navigation contained on mobile', () => {
    expect(mastheadSource).toContain('overflow-x-auto')
    expect(mastheadSource).toContain('whitespace-nowrap')
  })

  it('keeps artist release archive outside ArtistDetailExperience', () => {
    expect(artistDetailExperienceSource.split('\n').length).toBeLessThanOrEqual(300)
    expect(artistDetailExperienceSource).not.toContain('RankTrendChart')
    expect(artistDetailExperienceSource).not.toContain('发行事件与艺人走势')
    expect(artistDetailExperienceSource).not.toContain('发行列表')
    expect(artistDetailExperienceSource).not.toContain('formatReleaseType')
  })

  /* ─────────────────────────────────────── */
  /*  Phase 5.4-A: 新增页面架构护栏          */
  /* ─────────────────────────────────────── */

  // ── TrackDetail route container ──────────────────────────────────────────

  it('keeps TrackDetailPage as a thin route container delegating to TrackDetailExperience', () => {
    expect(trackDetailSource.split('\n').length).toBeLessThanOrEqual(10)
    expect(trackDetailSource).toContain('TrackDetailExperience')
    expect(trackDetailSource).not.toContain('<table')
    expect(trackDetailSource).not.toContain('function KpiItem')
    expect(trackDetailSource).not.toContain('const enrichmentCache = new Map')
    expect(trackDetailSource).not.toContain('const releaseCycleCache = new Map')
  })

  it('keeps TrackDetailExperience using queryKeys for data fetching and delegating sections', () => {
    expect(trackDetailExperienceSource.split('\n').length).toBeLessThanOrEqual(250)
    expect(trackDetailExperienceSource).toContain('queryKeys.music.trackDetail')
    expect(trackDetailExperienceSource).toContain('queryKeys.music.trackEnrichment')
    expect(trackDetailExperienceSource).toContain('queryKeys.music.trackLyrics')
    expect(trackDetailExperienceSource).toContain('TrackOverviewSection')
    expect(trackDetailExperienceSource).toContain('TrackLyricsSection')
    expect(trackDetailExperienceSource).not.toContain('function KpiItem')
    expect(trackDetailExperienceSource).not.toContain('function parseChange')
    expect(trackDetailExperienceSource).not.toContain('setLyrics')
    expect(trackDetailExperienceSource).not.toContain('fetchLyrics')
  })

  it('keeps TrackOverviewSection under section cap with KPI and history table', () => {
    expect(trackOverviewSectionSource.split('\n').length).toBeLessThanOrEqual(300)
    expect(trackOverviewSectionSource).toContain('<table')
    expect(trackOverviewSectionSource).not.toContain('function TrackDetailSkeleton')
  })

  it('keeps TrackLyricsSection under section cap with enrichment and lyrics display', () => {
    expect(trackLyricsSectionSource.split('\n').length).toBeLessThanOrEqual(300)
    expect(trackLyricsSectionSource).not.toContain('function TrackDetailSkeleton')
    expect(trackLyricsSectionSource).not.toContain('queryKeys')
  })

  // ── BillboardPage ────────────────────────────────────────────────────────

  it('keeps BillboardPage as a route container under the size cap', () => {
    expect(billboardPageSource.split('\n').length).toBeLessThanOrEqual(450)
    expect(billboardPageSource).not.toContain('function MiniRankTable')
  })

  // ── Billboard Versus ─────────────────────────────────────────────────────

  it('keeps BillboardVersusPage as a thin route container', () => {
    expect(billboardVersusPageSource.split('\n').length).toBeLessThanOrEqual(10)
    expect(billboardVersusPageSource).toContain('VersusExperience')
    expect(billboardVersusPageSource).not.toContain('<table')
  })

  it('keeps VersusExperience under the experience size cap', () => {
    expect(versusExperienceSource.split('\n').length).toBeLessThanOrEqual(450)
    expect(versusExperienceSource).not.toContain('const enrichmentCache = new Map')
    expect(versusExperienceSource).not.toContain('const releaseCycleCache = new Map')
  })

  // ── AI Insights ──────────────────────────────────────────────────────────

  it('keeps AiInsightsPage as a thin route container', () => {
    expect(aiInsightsPageSource.split('\n').length).toBeLessThanOrEqual(10)
    expect(aiInsightsPageSource).toContain('AiInsightsExperience')
  })

  it('keeps AiInsightsExperience under baseline and free of deprecated module-level caches', () => {
    expect(aiInsightsExperienceSource.split('\n').length).toBeLessThanOrEqual(430)
    expect(aiInsightsExperienceSource).not.toContain('const enrichmentCache = new Map')
    expect(aiInsightsExperienceSource).not.toContain('const releaseCycleCache = new Map')
    expect(aiInsightsExperienceSource).not.toContain('const detailCache = new Map')
    expect(aiInsightsExperienceSource).toContain('AiInsightsTimeSelectors')
  })

  it('keeps ChatInterface under baseline with message list delegated', () => {
    expect(chatInterfaceSource.split('\n').length).toBeLessThanOrEqual(350)
    expect(chatInterfaceSource).toContain('ChatMessageList')
    expect(chatInterfaceSource).not.toContain('const enrichmentCache = new Map')
    expect(chatInterfaceSource).not.toContain('const releaseCycleCache = new Map')
  })

  it('keeps AiInsightsTimeSelectors as a standalone primitives component', () => {
    expect(aiInsightsTimeSelectorsSource.split('\n').length).toBeLessThanOrEqual(250)
    expect(aiInsightsTimeSelectorsSource).toContain('QuickPills')
  })

  it('keeps ChatMessageList as a standalone section component', () => {
    expect(chatMessageListSource.split('\n').length).toBeLessThanOrEqual(200)
    expect(chatMessageListSource).not.toContain('useAskQuestion')
    expect(chatMessageListSource).not.toContain('useCreateSession')
  })

  // ── Community ────────────────────────────────────────────────────────────

  it('keeps CommunityPage as a thin route container', () => {
    expect(communityPageSource.split('\n').length).toBeLessThanOrEqual(10)
    expect(communityPageSource).toContain('CommunityExperience')
  })

  it('keeps CommunityAccountPage as a thin route container', () => {
    expect(communityAccountPageSource.split('\n').length).toBeLessThanOrEqual(10)
    expect(communityAccountPageSource).toContain('CommunityAccountExperience')
  })

  it('keeps PostDetailPage as a thin route container', () => {
    expect(postDetailPageSource.split('\n').length).toBeLessThanOrEqual(10)
    expect(postDetailPageSource).toContain('PostDetailExperience')
  })

  it('keeps community experiences under baseline and free of module-level API caches', () => {
    expect(communityExperienceSource.split('\n').length).toBeLessThanOrEqual(450)
    expect(communityAccountExperienceSource.split('\n').length).toBeLessThanOrEqual(450)
    expect(postDetailExperienceSource.split('\n').length).toBeLessThanOrEqual(450)
    expect(communityExperienceSource).not.toContain('const feedCache = new Map')
    expect(communityAccountExperienceSource).not.toContain('const accountCache = new Map')
    expect(postDetailExperienceSource).not.toContain('const postCache = new Map')
  })

  // ── Account Habits (migrated to feature) ──────────────────────────────

  it('keeps AccountCenterPage as a tab-composing route container', () => {
    expect(accountCenterPageSource.split('\n').length).toBeLessThanOrEqual(450)
    expect(accountCenterPageSource).not.toContain('<table')
    expect(accountCenterPageSource).not.toContain('function inferPersonality')
    expect(accountCenterPageSource).not.toContain('function SearchHeatmap')
  })

  it('keeps HabitsTab as a thin orchestrator in features/account/habits', () => {
    expect(habitsTabSource.split('\n').length).toBeLessThanOrEqual(100)
    expect(habitsTabSource).toContain('HabitsPersonalityHero')
    expect(habitsTabSource).toContain('SearchHistorySection')
    expect(habitsTabSource).toContain('FanTiersSection')
    expect(habitsTabSource).toContain('PodcastSection')
    expect(habitsTabSource).toContain('MarqueeSection')
    expect(habitsTabSource).toContain('VideoSection')
    expect(habitsTabSource).not.toContain('function inferPersonality')
    expect(habitsTabSource).not.toContain('const medalBorder')
  })

  it('keeps habits sections within size caps and JSX-only', () => {
    expect(habitsPersonalityHeroSource.split('\n').length).toBeLessThanOrEqual(60)
    expect(searchHistorySectionSource.split('\n').length).toBeLessThanOrEqual(250)
    expect(fanTiersSectionSource.split('\n').length).toBeLessThanOrEqual(170)
    expect(podcastSectionSource.split('\n').length).toBeLessThanOrEqual(90)
    expect(marqueeSectionSource.split('\n').length).toBeLessThanOrEqual(80)
    expect(videoSectionSource.split('\n').length).toBeLessThanOrEqual(120)
  })

  it('keeps habitsData pure logic without JSX', () => {
    expect(searchHistorySectionSource).not.toContain('function inferPersonality')
    expect(fanTiersSectionSource).not.toContain('function getMostActiveDay')
  })

  it('keeps CollectionTab as a thin page-level tab delegate', () => {
    expect(collectionTabSource.split('\n').length).toBeLessThanOrEqual(100)
    expect(collectionTabSource).not.toContain('<table')
  })

  // ── Cross-cutting: no module-level API response caches ───────────────────

  it.each([
    ['AiInsightsExperience.tsx', aiInsightsExperienceSource],
    ['ChatInterface.tsx', chatInterfaceSource],
    ['CommunityExperience.tsx', communityExperienceSource],
    ['CommunityAccountExperience.tsx', communityAccountExperienceSource],
    ['PostDetailExperience.tsx', postDetailExperienceSource],
    ['VersusExperience.tsx', versusExperienceSource],
    ['HabitsTab.tsx', habitsTabSource],
    ['BillboardPage.tsx', billboardPageSource],
    ['AccountCenterPage.tsx', accountCenterPageSource],
    ['TrackDetailPage.tsx', trackDetailSource],
  ])('%s does not keep API responses in module-level Map caches', (_path, content) => {
    expect(content).not.toMatch(/const\s+\w*[Cc]ache\w*\s*=\s*new Map/)
    expect(content).not.toMatch(/const\s+dataCache\s*=\s*new Map/)
    expect(content).not.toMatch(/const\s+responseCache\s*=\s*new Map/)
  })

  // ── Cross-cutting: new GET reads must use queryKeys ──────────────────────

  it('all key experience files fetch data via queryKeys or domain query hooks', () => {
    const mustUseQuery: [string, string][] = [
      ['AiInsightsExperience.tsx', aiInsightsExperienceSource],
      ['ChatInterface.tsx', chatInterfaceSource],
      ['VersusExperience.tsx', versusExperienceSource],
      ['CommunityExperience.tsx', communityExperienceSource],
      ['CommunityAccountExperience.tsx', communityAccountExperienceSource],
    ]
    for (const [name, src] of mustUseQuery) {
      const usesQuery =
        src.includes('queryKeys') ||
        src.includes('useQuery') ||
        src.includes('useAiInsights') ||
        src.includes('useCommunity') ||
        src.includes('useBillboard')
      expect(usesQuery, `${name} must use queryKeys or domain query hooks`).toBe(true)
    }
  })
})
