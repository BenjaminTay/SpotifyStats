import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AccountArchivePhoneRoute } from '@/features/account-archive/route/AccountArchivePhoneRoute'
import { PhoneArchiveNav } from '@/features/account-archive/phone/PhoneArchiveNav'
import { PhoneEntityCard } from '@/features/account-archive/phone/PhoneArchivePrimitives'
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
    expect(screen.getByText('800')).toBeInTheDocument()
    expect(screen.getByText('250')).toBeInTheDocument()
    expect(screen.getByText('59')).toBeInTheDocument()
    expect(screen.getByText('27')).toBeInTheDocument()
    expect(screen.queryByText(/收藏记录：/)).not.toBeInTheDocument()
    expect(screen.queryByText(/播放数据截至/)).not.toBeInTheDocument()
    expect(screen.queryByText(/数据状态/)).not.toBeInTheDocument()
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

    await user.click(within(dialog).getByRole('button', { name: '第 1 / 80 页' }))
    const pageInput = within(dialog).getByRole('spinbutton', { name: '跳转到' })
    await user.clear(pageInput)
    await user.type(pageInput, '40')
    await user.click(within(dialog).getByRole('button', { name: '跳转' }))
    await waitFor(() => expect(get.mock.calls.some(([path, params]) => (
      path === '/account/library/tracks'
      && params
      && (params as { page: number }).page === 40
    ))).toBe(true))

    await user.click(within(dialog).getByRole('tab', { name: '专辑' }))
    expect(await within(dialog).findByText('Blue')).toBeInTheDocument()
    expect(within(dialog).getByRole('tab', { name: '专辑' })).toHaveAttribute('aria-selected', 'true')
    expect(get.mock.calls.some(([path, params]) => path === '/account/library/albums' && params && (params as { limit: number }).limit === 10)).toBe(true)

    await user.click(within(dialog).getByRole('button', { name: '关闭完整收藏库' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '收藏库' })).not.toBeInTheDocument())
    expect(opener).toHaveFocus()
  })

  it('keeps the active archive chapter visible in the horizontal navigation', async () => {
    const scrollTo = vi.fn()
    const { rerender } = render(<PhoneArchiveNav activeSection="cover" onSelect={vi.fn()} />)
    const navigation = screen.getByRole('navigation', { name: '音乐档案章节' })
    const list = navigation.querySelector('ol') as HTMLOListElement
    const target = within(navigation).getByRole('button', { name: /07.*音乐之外/ })
    Object.defineProperties(list, {
      clientWidth: { configurable: true, value: 320 },
      scrollWidth: { configurable: true, value: 640 },
      scrollLeft: { configurable: true, value: 0, writable: true },
      scrollTo: { configurable: true, value: scrollTo },
    })
    Object.defineProperties(target, {
      offsetLeft: { configurable: true, value: 540 },
      offsetWidth: { configurable: true, value: 80 },
    })

    rerender(<PhoneArchiveNav activeSection="other-media" onSelect={vi.fn()} />)

    await waitFor(() => expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ left: 420 })))
  })

  it('keeps long entity titles and return metadata in the same full-width copy column', () => {
    render(
      <MemoryRouter>
        <PhoneEntityCard
          name="Running Up That Hill (A Deal With God) - 2018 Remaster"
          artist="Kate Bush"
          coverUrl={null}
          href={null}
          meta="1240 天未出现"
        />
      </MemoryRouter>,
    )

    const title = screen.getByText('Running Up That Hill (A Deal With God) - 2018 Remaster')
    const copy = title.closest('.phone-archive-entity-copy')
    expect(copy).not.toBeNull()
    expect(within(copy as HTMLElement).getByText('1240 天未出现')).toBeInTheDocument()
    expect(copy?.parentElement?.children).toHaveLength(2)
  })
})
