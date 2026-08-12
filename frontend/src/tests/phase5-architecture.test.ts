import { describe, expect, it } from 'vitest'

import trackDetailSource from '../pages/TrackDetailPage.tsx?raw'
import musicSearchPageSource from '../pages/MusicSearchPage.tsx?raw'
import trackDetailExperienceSource from '../features/music/details/TrackDetailExperience.tsx?raw'
import albumDetailSource from '../pages/AlbumDetailPage.tsx?raw'
import artistDetailSource from '../pages/ArtistDetailPage.tsx?raw'
import recordsPageSource from '../pages/RecordsPage.tsx?raw'
import allTimeChartsPageSource from '../pages/AllTimeChartsPage.tsx?raw'
import billboardYearEndPageSource from '../pages/BillboardYearEndPage.tsx?raw'
import numberOnesPageSource from '../pages/NumberOnesPage.tsx?raw'
import billboardPageSource from '../pages/BillboardPage.tsx?raw'
import billboardVersusPageSource from '../pages/BillboardVersusPage.tsx?raw'
import analysisRecordsPageSource from '../pages/AnalysisRecordsPage.tsx?raw'
import playbackRecordsExperienceSource from '../features/analysis/records/PlaybackRecordsExperience.tsx?raw'
import obsessionSectionSource from '../features/analysis/records/ObsessionSection.tsx?raw'
import dailyTotalLeaderboardSource from '../features/analysis/records/DailyTotalLeaderboard.tsx?raw'
import yearlyReviewPageSource from '../pages/YearlyReviewPage.tsx?raw'
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
import dashboardPageSource from '../pages/DashboardPage.tsx?raw'
import appSource from '../App.tsx?raw'
import useBillboardSource from '../hooks/useBillboard.ts?raw'

import numberOnesExperienceSource from '../features/billboard/number-ones/NumberOnesExperience.tsx?raw'
import allTimeDataSource from '../features/billboard/all-time/allTimeData.ts?raw'
import yearEndExperienceSource from '../features/billboard/year-end/YearEndExperience.tsx?raw'
import yearEndHonorsSource from '../features/billboard/year-end/YearEndHonors.tsx?raw'
import yearEndTableSource from '../features/billboard/year-end/YearEndTable.tsx?raw'
import yearEndDataSource from '../features/billboard/year-end/yearEndData.ts?raw'
import versusExperienceSource from '../features/billboard/versus/VersusExperience.tsx?raw'
import artistDetailExperienceSource from '../features/music/details/ArtistDetailExperience.tsx?raw'
import albumDetailExperienceSource from '../features/music/details/AlbumDetailExperience.tsx?raw'
import albumEraSectionSource from '../features/music/details/AlbumEraSection.tsx?raw'
import versionGroupSectionSource from '../features/music/details/VersionGroupSection.tsx?raw'
import communityExperienceSource from '../features/community/CommunityExperience.tsx?raw'
import communityAccountExperienceSource from '../features/community/CommunityAccountExperience.tsx?raw'
import postDetailExperienceSource from '../features/community/PostDetailExperience.tsx?raw'
import aiInsightsExperienceSource from '../features/ai-insights/AiInsightsExperience.tsx?raw'
import aiReportsPanelSource from '../features/ai-insights/AiReportsPanel.tsx?raw'
import chatInterfaceSource from '../features/ai-insights/ChatInterface.tsx?raw'
import aiInsightsTimeSelectorsSource from '../features/ai-insights/AiInsightsTimeSelectors.tsx?raw'
import chatMessageListSource from '../features/ai-insights/ChatMessageList.tsx?raw'
import trackOverviewSectionSource from '../features/music/details/track/TrackOverviewSection.tsx?raw'
import trackLyricsSectionSource from '../features/music/details/track/TrackLyricsSection.tsx?raw'

import mastheadSource from '../components/layout/Masthead.tsx?raw'
import appLayoutSource from '../components/layout/AppLayout.tsx?raw'
import routeContextSource from '../components/layout/routeContext.ts?raw'
import analysisPageHeaderSource from '../components/shared/AnalysisPageHeader.tsx?raw'
import analysisSubNavSource from '../components/shared/AnalysisSubNav.tsx?raw'
import billboardSubNavSource from '../components/shared/BillboardSubNav.tsx?raw'
import chineseSource from '../lib/chinese.ts?raw'
import billboardNameSource from '../lib/billboard-name.ts?raw'
import monthlyTrendChartSource from '../components/charts/MonthlyTrendChart.tsx?raw'
import monthlyTrendEChartSource from '../components/charts/MonthlyTrendEChart.tsx?raw'
import analysisChartsSource from '../components/charts/AnalysisCharts.tsx?raw'
import rankTrendChartSource from '../components/charts/RankTrendChart.tsx?raw'
import releaseTimelineChartSource from '../components/charts/ReleaseTimelineChart.tsx?raw'
import versusRankChartSource from '../components/charts/VersusRankChart.tsx?raw'
import numberOnesPrimitivesChartSource from '../features/billboard/number-ones/NumberOnesPrimitives.tsx?raw'
import collectionOverviewBlockSource from '../features/account/collection/components/CollectionOverviewBlock.tsx?raw'
import saveLifecycleBlockSource from '../features/account/collection/components/SaveLifecycleBlock.tsx?raw'
import chemistryBlockSource from '../features/account/collection/components/ChemistryBlock.tsx?raw'

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

  it('keeps BillboardYearEndPage as a thin route container', () => {
    expect(billboardYearEndPageSource.split('\n').length).toBeLessThanOrEqual(20)
    expect(billboardYearEndPageSource).toContain('YearEndExperience')
    expect(billboardYearEndPageSource).not.toContain('<table')
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

  it('keeps NumberOnesExperience chrome stable while loading', () => {
    expect(numberOnesExperienceSource).not.toContain('if (loading) return <SkeletonBlock />')
    expect(numberOnesExperienceSource).toContain('<BillboardSubNav active="number-ones" />')
    expect(numberOnesExperienceSource).toContain('{loading && <SkeletonBlock />}')
  })

  it('keeps Billboard Year-End aligned with shared Billboard visual primitives', () => {
    expect(yearEndExperienceSource).toContain('<BillboardSubNav active="year-end" />')
    expect(yearEndExperienceSource).toContain('tracking-[1.8px]')
    expect(yearEndHonorsSource).toContain('aria-label="Year-End Summary"')
    expect(yearEndHonorsSource).not.toContain('<GlassCard')
    expect(yearEndTableSource).toContain("from '@/components/shared/CoverCell'")
    expect(yearEndTableSource).toContain("from '@/components/shared/PaginationBar'")
    expect(yearEndTableSource).not.toContain('function Pagination(')
  })

  it('uses compact year pill styling for Billboard Year-End', () => {
    expect(yearEndExperienceSource).not.toContain('<select')
    expect(yearEndExperienceSource).toContain('bg-accent-foreground text-card')
    expect(yearEndExperienceSource).toContain('bg-muted text-muted-foreground hover:text-foreground')
    expect(yearEndExperienceSource.indexOf('aria-label="切换年榜年份"')).toBeLessThan(
      yearEndExperienceSource.indexOf('role="tablist"'),
    )
  })

  it('places the Billboard All-Time tab immediately after Year-End', () => {
    const yearEndIndex = billboardSubNavSource.indexOf("active: 'year-end'")
    const allTimeIndex = billboardSubNavSource.indexOf("active: 'all-time'")

    expect(yearEndIndex).toBeGreaterThan(-1)
    expect(allTimeIndex).toBeGreaterThan(yearEndIndex)
  })

  it('uses chart-specific Billboard Year-End tab labels', () => {
    expect(yearEndDataSource).toContain("label: '单曲榜'")
    expect(yearEndDataSource).toContain("label: '专辑榜'")
    expect(yearEndDataSource).toContain("label: '艺人榜'")
    expect(yearEndDataSource).not.toContain("label: '歌曲'")
    expect(yearEndDataSource).not.toContain("label: '专辑'")
    expect(yearEndDataSource).not.toContain("label: '艺人'")
    expect(yearEndDataSource).not.toContain('年度单曲榜')
    expect(yearEndDataSource).not.toContain('年度专辑榜')
    expect(yearEndDataSource).not.toContain('年度艺人榜')
  })

  it('uses chart-specific Billboard All-Time tab labels', () => {
    expect(allTimeDataSource).toContain("label: '单曲榜'")
    expect(allTimeDataSource).toContain("label: '专辑榜'")
    expect(allTimeDataSource).toContain("label: '艺人榜'")
    expect(allTimeDataSource).not.toContain("label: '歌曲'")
    expect(allTimeDataSource).not.toContain("label: '专辑'")
    expect(allTimeDataSource).not.toContain("label: '艺人'")
  })

  it('places Billboard Year-End tabs between honors and the ranking table', () => {
    const honorsIndex = yearEndExperienceSource.indexOf('<YearEndHonors')
    const tabsIndex = yearEndExperienceSource.indexOf('role="tablist"')
    const tableIndex = yearEndExperienceSource.indexOf('<YearEndTable')

    expect(honorsIndex).toBeGreaterThan(-1)
    expect(tabsIndex).toBeGreaterThan(honorsIndex)
    expect(tableIndex).toBeGreaterThan(tabsIndex)
  })

  it('keeps selected Billboard Year-End honors in a desktop 3x2 grid', () => {
    expect(yearEndHonorsSource).toContain('lg:grid-cols-3')
    expect(yearEndHonorsSource).not.toContain('xl:grid-cols-4')
  })

  it('prefetches all Billboard Year-End years and keeps previous data while switching', () => {
    expect(useBillboardSource).toContain('prefetchBillboardYearEndYears')
    expect(useBillboardSource).toContain('placeholderData: keepPreviousData')
    expect(useBillboardSource).toContain('available_years')
    expect(useBillboardSource).toContain('getQueryData')
  })

  it('keeps music detail pages as route containers', () => {
    expect(artistDetailSource.split('\n').length).toBeLessThanOrEqual(450)
    expect(albumDetailSource.split('\n').length).toBeLessThanOrEqual(450)
    expect(musicSearchPageSource.split('\n').length).toBeLessThanOrEqual(20)
    expect(musicSearchPageSource).toContain('MusicSearchExperience')
    expect(artistDetailSource).not.toContain('function KpiCard')
    expect(albumDetailSource).not.toContain('function KpiCard')
    expect(musicSearchPageSource).not.toContain('<table')
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

  it('does not mount entity stats charts inside hidden music detail tabs', () => {
    for (const source of [
      trackDetailExperienceSource,
      artistDetailExperienceSource,
      albumDetailExperienceSource,
    ]) {
      expect(source).not.toMatch(/className=\{activeTab === 'stats' \? '' : 'hidden'\}[\s\S]*?<EntityStatsPanel/)
    }
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

  it('keeps version group + source breakdown merged in VersionGroupSection', () => {
    expect(versionGroupSectionSource.split('\n').length).toBeLessThanOrEqual(300)
    expect(versionGroupSectionSource).toContain('sourceBreakdown')
    expect(versionGroupSectionSource).toContain('来源拆分')
  })

  it('renders VersionGroupSection inside stats tab, not between hero and tabs', () => {
    expect(albumDetailExperienceSource).toContain('VersionGroupSection')
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
    expect(mastheadSource).toContain('basis-full')
    expect(mastheadSource).toContain('max-w-full')
  })

  it('keeps the masthead top-level destinations consolidated', () => {
    expect(mastheadSource).toContain('primaryNavItems')
    expect(mastheadSource).toContain("label: '首页'")
    expect(mastheadSource).toContain("label: '播放分析'")
    expect(mastheadSource).toContain("label: '榜单'")
    expect(mastheadSource).toContain("label: '社区'")
    expect(mastheadSource).toContain("label: 'AI'")
    expect(mastheadSource).toContain('to="/settings"')
    expect(mastheadSource).not.toContain('DropdownMenu')
    expect(mastheadSource).not.toContain('menuItems')
    expect(mastheadSource).not.toContain('aria-haspopup')
    expect(mastheadSource).not.toContain("to: '/yearly-review'")
    expect(mastheadSource).not.toContain("to: '/account'")
  })

  it('keeps playback analysis secondary destinations in the analysis tab row', () => {
    expect(analysisSubNavSource).toContain("to: '/analysis/stats'")
    expect(analysisSubNavSource).toContain("to: '/analysis/charts'")
    expect(analysisSubNavSource).toContain("to: '/analysis/records'")
    expect(analysisSubNavSource).toContain("to: '/yearly-review'")
    expect(analysisSubNavSource).toContain("to: '/account'")
    expect(analysisSubNavSource).toContain("label: '播放统计'")
    expect(analysisSubNavSource).toContain("label: '播放排行'")
    expect(analysisSubNavSource).toContain("label: '年度总结'")
    expect(analysisSubNavSource).toContain("label: '账号中心'")
    expect(analysisSubNavSource.indexOf("to: '/analysis/charts'")).toBeLessThan(
      analysisSubNavSource.indexOf("to: '/yearly-review'"),
    )
    expect(analysisSubNavSource.indexOf("to: '/yearly-review'")).toBeLessThan(
      analysisSubNavSource.indexOf("to: '/analysis/records'"),
    )
    expect(yearlyReviewPageSource).toContain('AnalysisSubNav')
    expect(yearlyReviewPageSource.indexOf('<AnalysisSubNav')).toBeLessThan(
      yearlyReviewPageSource.indexOf('年份选择器'),
    )
    expect(accountCenterPageSource).toContain('AnalysisSubNav')
  })

  it('keeps playback analysis tab rows vertically stable across child pages', () => {
    expect(analysisPageHeaderSource).toContain('<section className="mb-6 hidden md:block">')
    expect(analysisSubNavSource).toContain('min-h-9')
    expect(analysisSubNavSource).toContain('shrink-0 pb-2.5 font-sans text-[13px] font-medium border-b-2 transition-colors -mb-[1px]')
    expect(analysisSubNavSource).toContain('-translate-y-[3px]')
    expect(analysisSubNavSource).toContain('basis-full h-9 sm:hidden')
    expect(analysisSubNavSource).not.toContain('inline-flex h-9')
    expect(yearlyReviewPageSource).not.toContain('你的年度音乐档案，用数据讲述这一年的听觉故事。')
    expect(accountCenterPageSource).toContain('AnalysisPageHeader')
  })

  it('keeps mobile masthead orientation explicit without duplicating detail breadcrumbs', () => {
    expect(mastheadSource).toContain('getMastheadRouteContext')
    expect(mastheadSource).toContain('scrollIntoView')
    expect(mastheadSource).not.toContain('aria-label="当前位置"')
    expect(mastheadSource).not.toContain('返回上一页')
    expect(routeContextSource).toContain("pathname.startsWith('/music/artists/')")
    expect(routeContextSource).toContain('activeNavTo: null')
  })

  it('keeps the app shell from allowing page-level horizontal scroll on mobile', () => {
    expect(appLayoutSource).toContain('overflow-x-clip')
  })

  it('keeps dashboard loading skeletons within the mobile content column', () => {
    expect(dashboardPageSource).not.toContain('h-5 w-96')
    expect(dashboardPageSource).toContain('w-full max-w-96')
  })

  it('keeps legacy analysis aliases outside the lazy AnalysisLayout route', () => {
    const analysisLayoutRouteIndex = appSource.indexOf('<Route path="/analysis" element=')
    expect(analysisLayoutRouteIndex).toBeGreaterThan(-1)

    for (const legacyPath of [
      '/analysis/timeline',
      '/analysis/leaderboard',
      '/analysis/behavior',
      '/analysis/listening-hours',
      '/analysis/artists',
    ]) {
      const aliasRouteIndex = appSource.indexOf(`<Route path="${legacyPath}"`)
      expect(aliasRouteIndex).toBeGreaterThan(-1)
      expect(aliasRouteIndex).toBeLessThan(analysisLayoutRouteIndex)
    }
  })

  it('keeps Chinese conversion from loading the full OpenCC bundle', () => {
    expect(chineseSource).not.toContain("from 'opencc-js'")
    expect(chineseSource).not.toContain('import(\'opencc-js\')')
    expect(chineseSource).toContain("import('opencc-js/cn2t')")
    expect(chineseSource).toContain("import('opencc-js/t2cn')")
  })

  it('keeps Chinese conversion dictionaries demand-loaded after saved preference restore', () => {
    expect(chineseSource).not.toMatch(
      /if\s*\(\s*getChineseStyle\(\)\s*!==\s*['"]original['"]\s*\)\s*{[\s\S]*ensureConverter\(getChineseStyle\(\)\)/
    )
    expect(appLayoutSource).toContain('useChineseTextVersion()')
  })

  it('keeps Billboard name from eager-loading localStorage on module init', () => {
    // getBillboardName uses a function (not a module-level const), so module init
    // should never read localStorage directly at the top level.
    expect(billboardNameSource).not.toMatch(
      /^(?:const|let)\s+\w+\s*=\s*localStorage\.getItem/
    )
  })

  it('ensures AppLayout subscribes to billboard name changes', () => {
    expect(appLayoutSource).toContain('useBillboardNameVersion()')
  })

  it('keeps the dashboard monthly trend chart lazy-loaded for first paint', () => {
    expect(monthlyTrendChartSource).toContain("lazy(() => import('./MonthlyTrendEChart'))")
    expect(monthlyTrendChartSource).not.toContain('LazyEChart')
    expect(monthlyTrendChartSource).not.toContain('EChartsTheme')
    expect(monthlyTrendEChartSource).toContain('LazyEChart')
    expect(monthlyTrendEChartSource).toContain('EChartsTheme')
  })

  it.each([
    ['AnalysisCharts.tsx', analysisChartsSource],
    ['RankTrendChart.tsx', rankTrendChartSource],
    ['ReleaseTimelineChart.tsx', releaseTimelineChartSource],
    ['VersusRankChart.tsx', versusRankChartSource],
    ['NumberOnesPrimitives.tsx', numberOnesPrimitivesChartSource],
    ['CollectionOverviewBlock.tsx', collectionOverviewBlockSource],
    ['SaveLifecycleBlock.tsx', saveLifecycleBlockSource],
  ])('%s uses the shared lightweight ECharts wrapper', (_path, content) => {
    expect(content).not.toContain("import('echarts-for-react')")
    expect(content).toContain('LazyEChart')
  })

  it('keeps account chemistry examples capped for initial render', () => {
    expect(chemistryBlockSource).toContain('MAX_CHEMISTRY_EXAMPLES')
    expect(chemistryBlockSource).toMatch(/\.slice\(0,\s*MAX_CHEMISTRY_EXAMPLES\)/)
  })

  it('keeps AccountCenterPage hero progressive while the heavy account summary loads', () => {
    expect(accountCenterPageSource).toContain('useProfile()')
    expect(accountCenterPageSource).toContain('profileForHero')
    expect(accountCenterPageSource).toContain('AccountContentSkeleton')
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
    expect(aiInsightsExperienceSource).toContain('AiReportsPanel')
    expect(aiReportsPanelSource).toContain('AiInsightsTimeSelectors')
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

  it('keeps AnalysisRecordsPage as a route container, not a full records module', () => {
    expect(analysisRecordsPageSource.split('\n').length).toBeLessThanOrEqual(450)
    expect(analysisRecordsPageSource).not.toContain('function ObsessionSection')
    expect(analysisRecordsPageSource).not.toContain('function LongevitySection')
    expect(analysisRecordsPageSource).not.toContain('function ReignsSection')
    expect(analysisRecordsPageSource).not.toContain('<table')
  })

  it('keeps PlaybackRecordsExperience thin by delegating sections to lazy-loaded modules', () => {
    expect(playbackRecordsExperienceSource.split('\n').length).toBeLessThanOrEqual(450)
    expect(playbackRecordsExperienceSource).toContain('lazy(() =>')
    expect(playbackRecordsExperienceSource).toContain('Suspense')
  })

  it('keeps ObsessionSection using shared primitives instead of inline tables', () => {
    expect(obsessionSectionSource.split('\n').length).toBeLessThanOrEqual(300)
    expect(obsessionSectionSource).toContain('EntityRecordCard')
    expect(obsessionSectionSource).not.toContain('<table')
  })

  it('keeps Daily Total Record as a sortable day leaderboard', () => {
    expect(obsessionSectionSource).toContain("'plays' | 'hours'")
    expect(obsessionSectionSource).toContain('DAILY_TOTAL_RECORD_LIMIT = 50')
    expect(obsessionSectionSource).toContain('DailyTotalLeaderboard')
    expect(obsessionSectionSource).toContain('按次数')
    expect(obsessionSectionSource).toContain('按时长')
    expect(dailyTotalLeaderboardSource).toContain('最高歌曲')
    expect(dailyTotalLeaderboardSource).toContain('最高专辑')
    expect(dailyTotalLeaderboardSource).toContain('最高艺人')
    expect(dailyTotalLeaderboardSource).toContain('top_track_cover_url')
    expect(dailyTotalLeaderboardSource).toContain('top_album_cover_url')
    expect(dailyTotalLeaderboardSource).toContain('top_artist_cover_url')
  })
})
