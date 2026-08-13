import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { useEffect, type ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CapabilityRoute } from '@/components/capabilities/CapabilityGate'
import { Masthead } from '@/components/layout/Masthead'
import { ArtistDetailExperience } from '@/features/music/details/ArtistDetailExperience'
import { TrackDetailExperience } from '@/features/music/details/TrackDetailExperience'
import { RuntimeCapabilitiesProvider } from '@/hooks/useRuntimeCapabilities'
import {
  FULL_CAPABILITIES,
  PUBLIC_CAPABILITIES,
  normalizeRuntimeCapabilities,
} from '@/hooks/runtimeCapabilities'
import { useStartArtistEnrichmentTask } from '@/hooks/useAiTasks'
import { ThemeProvider } from '@/hooks/useTheme'
import { api } from '@/lib/api'
import { YearlyReviewPage } from '@/pages/YearlyReviewPage'

function installMatchMedia() {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}

function renderWithRuntime(children: ReactNode, path = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <RuntimeCapabilitiesProvider>
        <ThemeProvider>
          <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
        </ThemeProvider>
      </RuntimeCapabilitiesProvider>
    </QueryClientProvider>,
  )
}

function publicResponse() {
  return {
    ...PUBLIC_CAPABILITIES,
    policy_version: 'access-policy-v1',
    release_sha: 'showcase-test-sha',
  }
}

function settingsResponse() {
  return {
    min_ms: 30_000,
    music_only: true,
    merge_enabled: true,
    include_compilations: false,
    bb_top_n: 30,
    bb_album_top_n: 20,
    bb_artist_top_n: 20,
    bb_week_start_dow: 4,
    bb_week_start_hour: 0,
  }
}

describe('deployment profile capability contract', () => {
  beforeEach(() => {
    installMatchMedia()
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('normalizes the versioned nested contract and fails closed for absent fields', () => {
    expect(normalizeRuntimeCapabilities({
      surface: 'private-admin',
      profile: 'full',
      policy_version: 'access-policy-v2',
      release_sha: 'abc123',
      capabilities: {
        settings: true,
        editing: true,
        imports: true,
        ai: true,
        spotify_oauth: true,
        lyrics: true,
        metadata_governance: true,
        yearly_generation: true,
        community_write: true,
        cover_enrichment: true,
      },
    })).toEqual({ ...FULL_CAPABILITIES, policy_version: 'access-policy-v2', release_sha: 'abc123' })

    expect(normalizeRuntimeCapabilities({ surface: 'private-admin', settings: true })).toMatchObject({
      settings: true,
      editing: false,
      imports: false,
      metadata_governance: false,
      yearly_generation: false,
      community_write: false,
      cover_enrichment: false,
    })
    expect(normalizeRuntimeCapabilities(undefined)).toEqual(PUBLIC_CAPABILITIES)
  })

  it('keeps the full desktop navigation unchanged', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      ...FULL_CAPABILITIES,
      policy_version: 'access-policy-v1',
      release_sha: 'full-test-sha',
    })
    renderWithRuntime(<Masthead />)

    await waitFor(() => expect(screen.getByRole('link', { name: 'AI' })).toBeInTheDocument())
    expect(screen.getByRole('link', { name: '偏好设置' })).toBeInTheDocument()
    expect(screen.queryByText('公开展示')).not.toBeInTheDocument()
  })

  it('fails closed while capability discovery fails', async () => {
    vi.spyOn(api, 'get').mockRejectedValue(new Error('discovery unavailable'))
    renderWithRuntime(<Masthead />)

    expect(screen.queryByRole('link', { name: 'AI' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '偏好设置' })).not.toBeInTheDocument()
    expect(screen.getByText('公开展示')).toBeInTheDocument()
  })

  it('redirects disabled routes before their page mounts', async () => {
    const mounted = vi.fn()
    function SensitivePage() {
      useEffect(() => mounted(), [])
      return <p>敏感页面</p>
    }
    vi.spyOn(api, 'get').mockResolvedValue(publicResponse())

    renderWithRuntime(
      <Routes>
        <Route path="/" element={<p>公开首页</p>} />
        <Route path="/settings" element={<CapabilityRoute require="settings"><SensitivePage /></CapabilityRoute>} />
      </Routes>,
      '/settings?metadata=track-credits',
    )

    await waitFor(() => expect(screen.getByText('公开首页')).toBeInTheDocument())
    expect(mounted).not.toHaveBeenCalled()
    expect(screen.queryByText('敏感页面')).not.toBeInTheDocument()
  })

  it('does not request lyrics or track enrichment from a showcase deep link', async () => {
    const get = vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
      if (path === '/runtime/capabilities') return publicResponse()
      if (path === '/settings') return settingsResponse()
      if (path.startsWith('/billboard/track/')) {
        return { found: false, track_id: 'track-1', track_name: 'Track', artist_name: 'Artist' }
      }
      throw new Error(`unexpected GET ${path}`)
    })

    renderWithRuntime(
      <Routes><Route path="/music/tracks/:trackId" element={<TrackDetailExperience />} /></Routes>,
      '/music/tracks/track-1?tab=lyrics',
    )

    await screen.findByText('未找到该曲目的榜单数据')
    const paths = get.mock.calls.map(([path]) => String(path))
    expect(paths.some(path => path.startsWith('/lyrics/'))).toBe(false)
    expect(paths.some(path => path.startsWith('/billboard/enrichment/track/'))).toBe(false)
  })

  it('does not start AI enrichment even if a showcase consumer invokes the mutation', async () => {
    const post = vi.spyOn(api, 'post')
    vi.spyOn(api, 'get').mockResolvedValue(publicResponse())

    function Probe() {
      const mutation = useStartArtistEnrichmentTask()
      useEffect(() => {
        mutation.mutate({ artist_name: 'Artist' })
      }, []) // eslint-disable-line react-hooks/exhaustive-deps
      return <span>{mutation.isError ? 'blocked' : 'pending'}</span>
    }

    renderWithRuntime(<Probe />)
    await screen.findByText('blocked')
    expect(post).not.toHaveBeenCalled()
  })

  it('reads cached yearly reports without polling or prewarming in showcase mode', async () => {
    const never = new Promise<never>(() => undefined)
    const get = vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
      if (path === '/runtime/capabilities') return publicResponse()
      if (path === '/settings') return settingsResponse()
      if (path === '/yearly-review/available-years') return { years: [2026] }
      if (path === '/yearly-review/2026') return never
      throw new Error(`unexpected GET ${path}`)
    })
    const prewarm = vi.spyOn(api, 'postWithParams')

    renderWithRuntime(
      <Routes><Route path="/yearly-review" element={<YearlyReviewPage />} /></Routes>,
      '/yearly-review?year=2026',
    )

    await screen.findByRole('button', { name: '2026' })
    await waitFor(() => expect(get).toHaveBeenCalledWith(
      '/yearly-review/available-years',
    ))
    const paths = get.mock.calls.map(([path]) => String(path))
    expect(paths).not.toContain('/yearly-review/generation-status')
    expect(prewarm).not.toHaveBeenCalled()
  })

  it('normalizes a public artist career deep link without starting enrichment', async () => {
    const post = vi.spyOn(api, 'post')
    const get = vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
      if (path === '/runtime/capabilities') return publicResponse()
      if (path === '/settings') return settingsResponse()
      if (path.startsWith('/billboard/artist/')) {
        return { found: false, artist_name: 'Artist', tracks: [], albums: [] }
      }
      throw new Error(`unexpected GET ${path}`)
    })

    renderWithRuntime(
      <Routes><Route path="/music/artists/:artistName" element={<ArtistDetailExperience />} /></Routes>,
      '/music/artists/Artist?tab=career',
    )

    await screen.findByText('未找到该艺人的榜单数据')
    expect(post).not.toHaveBeenCalled()
    expect(get.mock.calls.some(([path]) => String(path).startsWith('/ai/tasks/'))).toBe(false)
  })
})
