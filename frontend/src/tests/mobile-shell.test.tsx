import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AppLayout } from '@/components/layout/AppLayout'
import { MobileBottomNav } from '@/components/layout/MobileBottomNav'
import { MobileTopBar } from '@/components/layout/MobileTopBar'
import { ThemeProvider } from '@/hooks/useTheme'

vi.mock('@/hooks/useDashboard', () => ({ preloadDashboardData: vi.fn() }))
vi.mock('@/hooks/useBillboard', () => ({ preloadWeeklyData: vi.fn(), preloadAllTimeData: vi.fn() }))

type ChangeListener = (event: MediaQueryListEvent) => void

let viewportWidth = 390
const queryListeners = new Map<string, Set<ChangeListener>>()

function matchesQuery(query: string): boolean {
  const max = query.match(/max-width:\s*(\d+)px/)
  if (max) return viewportWidth <= Number(max[1])
  const min = query.match(/min-width:\s*(\d+)px/)
  if (min) return viewportWidth >= Number(min[1])
  if (query.includes('prefers-color-scheme')) return false
  return false
}

function installMatchMedia() {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: vi.fn((query: string) => {
      const listeners = queryListeners.get(query) ?? new Set<ChangeListener>()
      queryListeners.set(query, listeners)
      return {
        get matches() { return matchesQuery(query) },
        media: query,
        onchange: null,
        addEventListener: (_event: string, listener: ChangeListener) => listeners.add(listener),
        removeEventListener: (_event: string, listener: ChangeListener) => listeners.delete(listener),
        addListener: (listener: ChangeListener) => listeners.add(listener),
        removeListener: (listener: ChangeListener) => listeners.delete(listener),
        dispatchEvent: vi.fn(),
      }
    }),
  })
}

function setViewport(width: number) {
  viewportWidth = width
  queryListeners.forEach((listeners, query) => {
    const event = { matches: matchesQuery(query), media: query } as MediaQueryListEvent
    listeners.forEach((listener) => listener(event))
  })
}

function renderLayout(path: string) {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="*" element={<div>页面内容</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  )
}

describe('mobile app shell', () => {
  beforeEach(() => {
    viewportWidth = 390
    queryListeners.clear()
    installMatchMedia()
    localStorage.clear()
  })

  afterEach(() => {
    document.body.style.overflow = ''
  })

  it('mounts only the mobile shell below 768px', () => {
    renderLayout('/')

    expect(screen.getByLabelText('移动顶部导航')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: '移动主导航' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: '主导航' })).not.toBeInTheDocument()
    expect(screen.getByRole('main')).toHaveAttribute('data-viewport-mode', 'phone')
  })

  it('mounts only the desktop masthead at the 768px boundary', async () => {
    setViewport(768)
    renderLayout('/')

    expect(screen.getByRole('navigation', { name: '主导航' })).toBeInTheDocument()
    expect(screen.queryByLabelText('移动顶部导航')).not.toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: '移动主导航' })).not.toBeInTheDocument()
    expect(screen.getByRole('main')).toHaveAttribute('data-viewport-mode', 'compact')
  })

  it('hides bottom navigation on push routes', () => {
    renderLayout('/music/search')

    expect(screen.getByRole('button', { name: '返回上一页' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '分享当前页面' })).not.toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: '移动主导航' })).not.toBeInTheDocument()
  })

  it('moves music detail sharing and governance deep links into the top-bar More sheet', async () => {
    render(
      <MemoryRouter initialEntries={['/music/tracks/4455?tab=overview']}>
        <MobileTopBar />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: '打开详情更多操作' }))
    const dialog = screen.getByRole('dialog', { name: '详情操作' })
    expect(within(dialog).getByRole('button', { name: /分享详情/ })).toBeInTheDocument()
    const manageLink = within(dialog).getByRole('link', { name: /管理曲目署名/ })
    expect(manageLink).toHaveAttribute('href', expect.stringContaining('metadata=track-credits'))
    expect(manageLink).toHaveAttribute('href', expect.stringContaining('track_id=4455'))
    expect(manageLink).toHaveAttribute('href', expect.stringContaining('return_to=%2Fmusic%2Ftracks%2F4455%3Ftab%3Doverview'))
  })

  it('opens the analysis section sheet, preserves time state, and restores focus on Escape', async () => {
    render(
      <MemoryRouter initialEntries={['/analysis/charts?period=year&period_value=2025&entity=artist']}>
        <MobileTopBar />
      </MemoryRouter>,
    )

    const trigger = screen.getByRole('button', { name: /切换播放分析栏目/ })
    fireEvent.click(trigger)

    const dialog = screen.getByRole('dialog', { name: '播放分析栏目' })
    expect(within(dialog).getByRole('link', { name: /播放统计/ })).toHaveAttribute(
      'href',
      '/analysis/stats?period=year&period_value=2025',
    )
    expect(document.body.style.overflow).toBe('hidden')

    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(trigger).toHaveFocus())
    expect(document.body.style.overflow).toBe('')
  })

  it('marks the current bottom destination and hides it while the AI composer is focused', async () => {
    render(
      <MemoryRouter initialEntries={['/ai-insights?mode=chat']}>
        <div data-mobile-input-mode="true"><textarea aria-label="问题输入" /></div>
        <MobileBottomNav />
      </MemoryRouter>,
    )

    const nav = screen.getByRole('navigation', { name: '移动主导航' })
    expect(within(nav).getByRole('link', { name: 'AI' })).toHaveAttribute('aria-current', 'page')

    act(() => screen.getByRole('textbox', { name: '问题输入' }).focus())
    await waitFor(() => expect(screen.queryByRole('navigation', { name: '移动主导航' })).not.toBeInTheDocument())
  })
})
