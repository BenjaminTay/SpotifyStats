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
})
