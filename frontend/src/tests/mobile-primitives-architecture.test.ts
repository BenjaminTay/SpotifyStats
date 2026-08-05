import { describe, expect, it } from 'vitest'

import bottomSheetSource from '../components/mobile/MobileBottomSheet.tsx?raw'
import chartCardSource from '../components/mobile/MobileChartCard.tsx?raw'
import detailSheetSource from '../components/mobile/MobileEntityDetailSheet.tsx?raw'
import entityRowSource from '../components/mobile/MobileEntityRow.tsx?raw'
import filterSheetSource from '../components/mobile/MobileFilterSheet.tsx?raw'
import fullscreenChartSource from '../components/mobile/MobileFullscreenChart.tsx?raw'
import pageHeaderSource from '../components/mobile/MobilePageHeader.tsx?raw'
import paginationSource from '../components/mobile/MobilePagination.tsx?raw'
import rankListSource from '../components/mobile/MobileRankList.tsx?raw'
import statePanelSource from '../components/mobile/MobileStatePanel.tsx?raw'
import timeRangeSource from '../components/mobile/MobileTimeRangeSheet.tsx?raw'
import sectionSwitcherSource from '../components/layout/MobileSectionSwitcher.tsx?raw'

const COMPONENT_SOURCES = [
  ['MobileBottomSheet.tsx', bottomSheetSource],
  ['MobileChartCard.tsx', chartCardSource],
  ['MobileEntityDetailSheet.tsx', detailSheetSource],
  ['MobileEntityRow.tsx', entityRowSource],
  ['MobileFilterSheet.tsx', filterSheetSource],
  ['MobileFullscreenChart.tsx', fullscreenChartSource],
  ['MobilePageHeader.tsx', pageHeaderSource],
  ['MobilePagination.tsx', paginationSource],
  ['MobileRankList.tsx', rankListSource],
  ['MobileStatePanel.tsx', statePanelSource],
  ['MobileTimeRangeSheet.tsx', timeRangeSource],
] as const

describe('mobile primitive architecture', () => {
  it.each(COMPONENT_SOURCES)('%s stays independent from requests and query state', (_name, source) => {
    expect(source).not.toMatch(/from ['"]@\/api\//)
    expect(source).not.toMatch(/\bfetch\s*\(/)
    expect(source).not.toMatch(/\buse(Query|Mutation|InfiniteQuery)\b/)
    expect(source).not.toMatch(/from ['"]@\/features\//)
  })

  it.each(COMPONENT_SOURCES)('%s stays within the route-component size guardrail', (_name, source) => {
    expect(source.split('\n').length).toBeLessThanOrEqual(450)
  })

  it('routes the section switcher through the shared bottom-sheet contract', () => {
    expect(sectionSwitcherSource).toContain('MobileBottomSheet')
    expect(sectionSwitcherSource).not.toContain('createPortal')
    expect(sectionSwitcherSource).not.toContain('document.body.style.overflow')
  })
})
