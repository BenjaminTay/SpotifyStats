/** Optional captured-HTTP parity calibration; fixtures stay outside the repository. */
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { cleanup, render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { buildAllTimeRows, selectAllTimeRows, getColumnsForTab } from '@/features/billboard/all-time/allTimeData'
import { buildNumberOnes, availableYearsForTab, filterNumberOnesByYear } from '@/features/billboard/number-ones/numberOnesData'
import { buildWeeklySummary, computeWeeklyRankChange } from '@/features/billboard/weekly/weeklyPresentation'
import { buildCoverMaps, projectedCoverMaps } from '@/features/billboard/records/recordsData'
import { CuriositiesSection } from '@/features/billboard/records/CuriositiesSection'
import type { BillboardAllTimeResponse, BillboardDataResponse, BillboardRecordsProjection, BillboardWeeklyProjection } from '@/types/billboard'

const directory = process.env.BILLBOARD_PARITY_DIR
const load = (name: string) => JSON.parse(readFileSync(join(directory!, name+'.json'), 'utf8'))
describe.skipIf(!directory)('captured published facts vs page projections', () => {
  it('matches every All-Time row, column, sorting, filtering and search', () => {
    const legacy = buildAllTimeRows(load('all-time-before'))
    for (const entity of ['tracks','albums','artists'] as const) {
      const projected = { tracks: [], albums: [], artists: [], [entity]: load('all-'+entity+'-after').rows }
      expect(projected[entity]).toEqual(legacy[entity])
      for (const column of getColumnsForTab(entity)) for (const direction of ['asc','desc'] as const) for (const peak of ['all','no1','top5','top10','debut_no1'] as const) {
        expect(selectAllTimeRows(projected,entity,peak,column.key,direction,'')).toEqual(selectAllTimeRows(legacy,entity,peak,column.key,direction,''))
        expect(selectAllTimeRows(projected,entity,peak,column.key,direction,'a')).toEqual(selectAllTimeRows(legacy,entity,peak,column.key,direction,'a'))
      }
    }
  })
  it('matches every weekly row, previous week, NEW/RE and summary for every published week', () => {
    const legacy: BillboardAllTimeResponse = load('all-time-before')
    const fields = { tracks: 'weekly', albums: 'weekly_album', artists:'weekly_artist' } as const
    for (const projected of load('weekly-all-projections') as BillboardWeeklyProjection[]) {
      const rows = legacy[fields[projected.entity]]
      const index = legacy.meta.all_weeks_desc.indexOf(projected.selected_week)
      const current = rows.filter(r=>r.billboard_week===projected.selected_week).sort((a,b)=>a.rank-b.rank)
      const previous = rows.filter(r=>r.billboard_week===legacy.meta.all_weeks_desc[index+1])
      const history = rows.filter(r=>legacy.meta.all_weeks_desc.slice(index+1).includes(r.billboard_week))
      expect(projected.current).toEqual(current)
      expect(projected.previous).toEqual(previous)
      expect(buildWeeklySummary(projected.current,projected.previous,projected.historical,projected.entity)).toEqual(buildWeeklySummary(current,previous,history,projected.entity))
      current.forEach(row=>expect(computeWeeklyRankChange(row,previous,projected.historical,projected.entity)).toEqual(computeWeeklyRankChange(row,previous,history,projected.entity)))
    }
  })
  it('matches all #1 histories, power scores, streaks, cumulative weeks and year filters', () => {
    const legacy = buildNumberOnes(load('all-time-before'))
    const projected = buildNumberOnes(load('number-ones-after'))
    expect(projected).toEqual(legacy)
    for (const entity of ['tracks','albums','artists'] as const) for (const year of availableYearsForTab(legacy,entity)) expect(filterNumberOnesByYear(projected,year)).toEqual(filterNumberOnesByYear(legacy,year))
  })
  it('matches all six record families, cover selection and rendered Curiosities facts/links', () => {
    const legacy: BillboardDataResponse = load('data-before')
    const projected: BillboardRecordsProjection = load('records-after')
    expect(projected.records).toEqual(legacy.records)
    const covers = buildCoverMaps(legacy), slimCovers = projectedCoverMaps(projected.covers)
    for (const kind of ['track','album','artist'] as const) for (const [key,url] of slimCovers[kind]) expect((covers[kind] as Map<string|number,string|null>).get(key)).toEqual(url)
    const factDOM = (summary: typeof legacy.track_summary, counts: typeof legacy.artist_track_counts, artwork: typeof covers) => {
      const { container } = render(<MemoryRouter><CuriositiesSection rec={legacy.records} covers={artwork} trackSummary={summary} artistTrackCounts={counts}/></MemoryRouter>)
      const facts = { text: container.textContent, links: [...container.querySelectorAll('a')].map(x=>x.getAttribute('href')), images:[...container.querySelectorAll('img')].map(x=>x.getAttribute('src')) }
      cleanup(); return facts
    }
    expect(factDOM(projected.curiosity_tracks,projected.artist_track_counts,slimCovers)).toEqual(factDOM(legacy.track_summary,legacy.artist_track_counts,covers))
  })
})
