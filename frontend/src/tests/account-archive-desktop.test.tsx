import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AccountArchiveDesktopRoute } from '@/features/account-archive/route/AccountArchiveDesktopRoute'
import { api } from '@/lib/api'

const overview = {
  schema_version: 'account_archive_v1',
  content_version: 'account_archive_v1_0',
  data_revision: 'test-revision',
  status: 'ready',
  counts: { saved_tracks: 800, saved_albums: 250, saved_artists: 59, saved_shows: 0, playlists: 27, playlist_items: 681 },
  coverage: { saved_tracks_with_date: 800, saved_tracks_with_date_pct: 100, saved_tracks_linked_to_history: 762, saved_tracks_linked_to_history_pct: 95.3, saved_tracks_with_known_duration: 800, saved_tracks_with_known_duration_pct: 100, known_duration_ms: 195475714 },
  period: { first_saved_at: '2022-01-01', latest_saved_at: '2026-05-01', first_play_date: '2022-07-01', latest_play_date: '2026-07-24' },
  date_provenance: { oauth: 0, manual: 0, legacy: 800, missing: 0 },
  capabilities: { collection_browse: 'available', collection_timeline: 'available', playback_cross_analysis: 'partial' },
  featured_items: [],
}

describe('Account archive Desktop route', () => {
  afterEach(() => vi.restoreAllMocks())

  it('renders the local archive cover and never requests the legacy account summary', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (path) => {
      if (path === '/account/archive-overview') return overview
      return new Promise(() => undefined)
    })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })

    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/account']}>
          <AccountArchiveDesktopRoute />
        </MemoryRouter>
      </QueryClientProvider>,
    )

    await screen.findByRole('heading', { name: '音乐档案' })
    expect(screen.getByText('哪些音乐只是路过，哪些真正留了下来？')).toBeInTheDocument()
    expect(screen.getByText('95.3%')).toBeInTheDocument()
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/account/collection-journey', expect.anything()))
    expect(api.get).not.toHaveBeenCalledWith('/account')
    expect(api.get).not.toHaveBeenCalledWith('/profile')
  })
})
