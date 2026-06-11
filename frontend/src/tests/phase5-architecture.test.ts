import { describe, expect, it } from 'vitest'

import trackDetailSource from '../pages/TrackDetailPage.tsx?raw'
import albumDetailSource from '../pages/AlbumDetailPage.tsx?raw'
import artistDetailSource from '../pages/ArtistDetailPage.tsx?raw'
import recordsPageSource from '../pages/RecordsPage.tsx?raw'
import allTimeChartsPageSource from '../pages/AllTimeChartsPage.tsx?raw'
import numberOnesPageSource from '../pages/NumberOnesPage.tsx?raw'
import numberOnesExperienceSource from '../features/billboard/number-ones/NumberOnesExperience.tsx?raw'
import artistDetailExperienceSource from '../features/music/details/ArtistDetailExperience.tsx?raw'
import albumDetailExperienceSource from '../features/music/details/AlbumDetailExperience.tsx?raw'
import albumEraSectionSource from '../features/music/details/AlbumEraSection.tsx?raw'
import communityExperienceSource from '../features/community/CommunityExperience.tsx?raw'
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
})
