import { Outlet, useLocation } from 'react-router-dom'

import { BillboardSubNav, type BillboardSection } from '@/components/shared/BillboardSubNav'

function activeSection(pathname: string): BillboardSection {
  if (pathname.endsWith('/number-ones')) return 'number-ones'
  if (pathname.endsWith('/all-time')) return 'all-time'
  if (pathname.endsWith('/year-end')) return 'year-end'
  if (pathname.endsWith('/records')) return 'records'
  if (pathname.endsWith('/versus')) return 'versus'
  return 'weekly'
}

/** Persistent desktop shell for all Billboard pages. */
export function BillboardLayout() {
  const { pathname } = useLocation()
  return (
    <>
      <BillboardSubNav active={activeSection(pathname)} />
      <Outlet />
    </>
  )
}
