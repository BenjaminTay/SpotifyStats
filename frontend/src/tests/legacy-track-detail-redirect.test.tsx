import { render, screen } from '@testing-library/react'
import { useLocation, Outlet } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '@/App'

function LocationProbe() {
  const location = useLocation()
  return <output aria-label="当前歌曲地址">{location.pathname}{location.search}</output>
}

vi.mock('@/components/layout/AppLayout', () => ({ AppLayout: () => <Outlet /> }))
vi.mock('@/pages/TrackDetailPage', () => ({ TrackDetailPage: LocationProbe }))

beforeEach(() => {
  window.history.replaceState({}, '', '/')
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
})
afterEach(() => vi.restoreAllMocks())

describe('registered legacy track routes', () => {
  it.each([
    '/billboard/track/77',
    '/music/tracks/canonical/77',
    '/music/tracks/l1/77',
  ])('preserves query parameters when redirecting %s to the current route', async (path) => {
    window.history.replaceState({}, '', `${path}?tab=overview&merge_level=3`)
    render(<App />)
    expect(await screen.findByLabelText('当前歌曲地址')).toHaveTextContent('/music/tracks/77?tab=overview&merge_level=3')
  })
})
