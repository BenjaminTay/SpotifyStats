import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { Masthead } from '../components/layout/Masthead'
import { ThemeProvider } from '../hooks/useTheme'

function mockMatchMedia(matches = false) {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
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

function renderMasthead(path = '/') {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>
        <Masthead />
      </MemoryRouter>
    </ThemeProvider>,
  )
}

describe('masthead navigation', () => {
  beforeEach(() => {
    mockMatchMedia()
    localStorage.clear()
  })

  it('shows five primary destinations in the top navigation', () => {
    renderMasthead('/')

    const nav = screen.getByRole('navigation', { name: '主导航' })

    expect(within(nav).getByRole('link', { name: '首页' })).toHaveAttribute('href', '/')
    expect(within(nav).getByRole('link', { name: '播放分析' })).toHaveAttribute('href', '/analysis')
    expect(within(nav).getByRole('link', { name: '榜单' })).toHaveAttribute('href', '/billboard')
    expect(within(nav).getByRole('link', { name: '社区' })).toHaveAttribute('href', '/community')
    expect(within(nav).getByRole('link', { name: 'AI' })).toHaveAttribute('href', '/ai-insights')

    expect(within(nav).queryByRole('button', { name: '播放分析' })).not.toBeInTheDocument()
    expect(within(nav).queryByRole('button', { name: '榜单' })).not.toBeInTheDocument()
    expect(within(nav).queryByRole('link', { name: '年度总结' })).not.toBeInTheDocument()
    expect(within(nav).queryByRole('link', { name: '音乐档案' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '搜索音乐详情' })).toBeInTheDocument()
  })

  it('keeps secondary destination groups out of the masthead dropdown layer', () => {
    renderMasthead('/analysis/charts')

    expect(screen.queryByRole('button', { name: '播放分析' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '榜单' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '打开账户与设置菜单' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '搜索音乐详情' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '偏好设置' })).toHaveAttribute('href', '/settings')
  })
})
