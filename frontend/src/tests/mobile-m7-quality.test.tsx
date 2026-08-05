import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ListeningClock } from '@/components/charts/ListeningClock'
import { ThemeProvider } from '@/hooks/useTheme'
import statsSource from '../features/mobile/analysis/MobileAnalysisStats.tsx?raw'

beforeEach(() => {
  localStorage.setItem('theme', 'light')
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  })
})

describe('M7 mobile quality gates', () => {
  it('supports touch and keyboard disclosure on the listening clock', () => {
    render(
      <ThemeProvider>
        <ListeningClock data={[{ hour: 12, plays: 42, hours: 2 }]} metricLabel="次" />
      </ThemeProvider>,
    )

    const segment = screen.getByRole('button', { name: '12:00 · 42 次' })
    fireEvent.touchStart(segment)
    expect(screen.getByText('12:00 · 42 次')).toBeInTheDocument()
  })

  it('wires each mobile stats chart to the shared fullscreen dialog', () => {
    expect(statsSource).toContain('MobileFullscreenChart')
    expect(statsSource).toContain("setFullscreenChart('trend')")
    expect(statsSource).toContain("setFullscreenChart('clock')")
    expect(statsSource).toContain("setFullscreenChart('distribution')")
    expect(statsSource).toContain('fullscreenTriggerRef={trendFullscreenRef}')
  })
})
