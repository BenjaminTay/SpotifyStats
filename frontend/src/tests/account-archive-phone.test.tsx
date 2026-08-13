import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AccountArchivePhoneRoute } from '@/features/account-archive/route/AccountArchivePhoneRoute'
import { api } from '@/lib/api'

const overview = {
  schema_version: 'account_archive_v1',
  content_version: 'account_archive_v1_0',
  data_revision: 'test-revision',
  status: 'ready',
  counts: { saved_tracks: 800, saved_albums: 250, saved_artists: 59, saved_shows: 0, playlists: 27, playlist_items: 681 },
  coverage: { saved_tracks_with_date: 800, saved_tracks_with_date_pct: 100, saved_tracks_linked_to_history: 762, saved_tracks_linked_to_history_pct: 95.3, saved_tracks_with_known_duration: 800, saved_tracks_with_known_duration_pct: 100, known_duration_ms: 195_475_714 },
  period: { first_saved_at: '2022-01-01', latest_saved_at: '2026-05-01', first_play_date: '2022-07-01', latest_play_date: '2026-07-24' },
  date_provenance: { oauth: 0, manual: 0, legacy: 800, missing: 0 },
  capabilities: { collection_browse: 'available', collection_timeline: 'available', playback_cross_analysis: 'partial' },
  featured_items: [],
}

function libraryPage(entityType = 'tracks') {
  return {
    schema_version: 'account_archive_library_v1',
    content_version: 'account_archive_library_v1_0',
    data_revision: 'library-revision',
    entity_type: entityType,
    page: 1,
    limit: 10,
    total: entityType === 'albums' ? 250 : 800,
    total_pages: entityType === 'albums' ? 25 : 80,
    sort: entityType === 'albums' ? 'name' : 'recent',
    search_applied: false,
    items: entityType === 'albums'
      ? [{ entity_type: 'album', item_key: 'album-one', album_name: 'Blue', artist_name: 'Joni Mitchell', cover_url: null, deep_link: null }]
      : [{ entity_type: 'track', item_key: 'track-one', track_name: 'A Case of You', artist_name: 'Joni Mitchell', album_name: 'Blue', added_date: '2024-01-01', cover_url: null, deep_link: null }],
  }
}

function renderPhoneArchive() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/account']}>
        <AccountArchivePhoneRoute />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Account archive Phone route', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    document.body.style.overflow = ''
  })

  it('renders the pocket archive from local endpoints without legacy profile reads', async () => {
    const get = vi.spyOn(api, 'get').mockImplementation(async (path) => {
      if (path === '/account/archive-overview') return overview
      if (path.startsWith('/account/library/')) return libraryPage()
      return new Promise(() => undefined)
    })
    renderPhoneArchive()

    expect(await screen.findByRole('heading', { name: /音乐.*档案/ })).toBeInTheDocument()
    expect(screen.getByText('95.3%')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: '音乐档案章节' })).toBeInTheDocument()
    await waitFor(() => expect(get).toHaveBeenCalledWith('/account/archive-overview'))
    expect(get.mock.calls.some(([path]) => path === '/account' || path === '/profile')).toBe(false)
  })

  it('opens the server-paginated library full-screen and restores focus on close', async () => {
    const user = userEvent.setup()
    const get = vi.spyOn(api, 'get').mockImplementation(async (path) => {
      if (path === '/account/archive-overview') return overview
      if (path === '/account/library/albums') return libraryPage('albums')
      if (path.startsWith('/account/library/')) return libraryPage()
      return new Promise(() => undefined)
    })
    renderPhoneArchive()

    const opener = await screen.findByRole('button', { name: '打开完整收藏库' })
    await user.click(opener)
    const dialog = await screen.findByRole('dialog', { name: '收藏库' })
    expect(document.body).toHaveStyle({ overflow: 'hidden' })
    expect(within(dialog).getAllByText('A Case of You').length).toBeGreaterThan(0)
    await user.click(within(dialog).getByRole('tab', { name: '专辑' }))
    expect(await within(dialog).findByText('Blue')).toBeInTheDocument()
    expect(within(dialog).getByRole('tab', { name: '专辑' })).toHaveAttribute('aria-selected', 'true')
    expect(get.mock.calls.some(([path, params]) => path === '/account/library/albums' && params && (params as { limit: number }).limit === 10)).toBe(true)

    await user.click(within(dialog).getByRole('button', { name: '关闭完整收藏库' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '收藏库' })).not.toBeInTheDocument())
    expect(opener).toHaveFocus()
  })
})
