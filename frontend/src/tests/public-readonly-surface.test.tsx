import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { Masthead } from '@/components/layout/Masthead'
import { MobileBottomNav } from '@/components/layout/MobileBottomNav'
import { MobileTopBar } from '@/components/layout/MobileTopBar'
import { RuntimeCapabilitiesProvider, type RuntimeCapabilities } from '@/hooks/useRuntimeCapabilities'
import { ThemeProvider } from '@/hooks/useTheme'
import { api } from '@/lib/api'

const PUBLIC_CAPABILITIES: RuntimeCapabilities = {
  surface: 'public-readonly',
  settings: false,
  editing: false,
  imports: false,
  ai: false,
  spotify_oauth: false,
  lyrics: false,
}

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

function renderPublic(children: ReactNode, path = '/') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
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

describe('public readonly presentation', () => {
  beforeEach(() => {
    installMatchMedia()
    localStorage.clear()
    vi.spyOn(api, 'get').mockResolvedValue(PUBLIC_CAPABILITIES)
  })

  it('marks the desktop surface and removes management and AI navigation', async () => {
    renderPublic(<Masthead />)

    await waitFor(() => expect(screen.getByText('公开展示')).toBeInTheDocument())
    const nav = screen.getByRole('navigation', { name: '主导航' })
    expect(within(nav).queryByRole('link', { name: 'AI' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '偏好设置' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '搜索音乐详情' })).toBeInTheDocument()
  })

  it('keeps the mobile data destinations while removing AI and settings', async () => {
    renderPublic(
      <>
        <MobileTopBar />
        <MobileBottomNav />
      </>,
    )

    await waitFor(() => expect(screen.getByText('公开')).toBeInTheDocument())
    const nav = screen.getByRole('navigation', { name: '移动主导航' })
    expect(within(nav).getByRole('link', { name: '首页' })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: '播放' })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: '榜单' })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: '社区' })).toBeInTheDocument()
    expect(within(nav).queryByRole('link', { name: 'AI' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '偏好设置' })).not.toBeInTheDocument()
  })
})
