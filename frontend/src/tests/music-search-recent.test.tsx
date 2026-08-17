import { act, render, renderHook, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { RecentMusicEntityList } from '@/features/music/search/RecentMusicEntityList'
import { useRecentMusicEntities } from '@/features/music/search/recentMusicEntities'
import type { MusicSearchCandidate } from '@/types/music-search'

function candidate(id: number): MusicSearchCandidate {
  return {
    entity_key: `track:${id}`,
    kind: 'track',
    label: `Track ${id}`,
    subtitle: null,
    href: `/music/tracks/${id}`,
    track_id: id,
    artist_id: null,
    album_name: null,
    artist_name: null,
    cover_url: null,
    match_field: 'label',
    match_quality: 'exact',
  }
}

describe('private recent music entities', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => vi.restoreAllMocks())

  it('does not read or write private storage when the public capability disables it', async () => {
    const getItem = vi.spyOn(Storage.prototype, 'getItem')
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    const { result } = renderHook(() => useRecentMusicEntities(false))

    await act(async () => Promise.resolve())
    act(() => result.current.record(candidate(1)))

    expect(getItem).not.toHaveBeenCalled()
    expect(setItem).not.toHaveBeenCalled()
    expect(result.current.items).toEqual([])
  })

  it('stores only six stable private entries, deduplicates, and clears them', async () => {
    const { result } = renderHook(() => useRecentMusicEntities(true))
    await waitFor(() => expect(result.current.items).toEqual([]))

    act(() => {
      for (let id = 1; id <= 7; id += 1) result.current.record(candidate(id))
      result.current.record(candidate(6))
    })

    expect(result.current.items).toHaveLength(6)
    expect(result.current.items[0]).toEqual(expect.objectContaining({
      entity_key: 'track:6',
      label: 'Track 6',
      kind: 'track',
      href: '/music/tracks/6',
    }))
    expect(JSON.parse(localStorage.getItem('spotify_stats_recent_music_entities_v1') ?? '[]')).toHaveLength(6)

    act(() => result.current.clear())
    expect(result.current.items).toEqual([])
    expect(localStorage.getItem('spotify_stats_recent_music_entities_v1')).toBeNull()
  })

  it('applies the global Chinese display preference to recent entities', async () => {
    localStorage.setItem('chineseStyle', 'simplified')
    render(
      <MemoryRouter>
        <RecentMusicEntityList
          items={[{
            entity_key: 'track:1',
            label: '認了吧',
            kind: 'track',
            href: '/music/tracks/1',
            viewed_at: '2026-08-17T00:00:00Z',
          }]}
          onClear={vi.fn()}
        />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('认了吧')).toBeInTheDocument())
    expect(screen.queryByText('認了吧')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /认了吧/ })).toHaveAttribute('href', '/music/tracks/1')
  })
})
