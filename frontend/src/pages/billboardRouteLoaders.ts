export const loadBillboardPage = () => import('@/pages/BillboardPage')
export const loadNumberOnesPage = () => import('@/pages/NumberOnesPage')
export const loadAllTimeChartsPage = () => import('@/pages/AllTimeChartsPage')
export const loadBillboardYearEndPage = () => import('@/pages/BillboardYearEndPage')
export const loadRecordsPage = () => import('@/pages/RecordsPage')
export const loadBillboardVersusPage = () => import('@/pages/BillboardVersusPage')

export const BILLBOARD_ROUTE_LOADERS: Record<string, () => Promise<unknown>> = {
  '/billboard': loadBillboardPage,
  '/billboard/number-ones': loadNumberOnesPage,
  '/billboard/all-time': loadAllTimeChartsPage,
  '/billboard/year-end': loadBillboardYearEndPage,
  '/billboard/records': loadRecordsPage,
  '/billboard/versus': loadBillboardVersusPage,
}
