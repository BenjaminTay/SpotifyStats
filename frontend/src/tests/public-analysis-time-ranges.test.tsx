import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { SnapshotUnavailableError } from '@/api/errors'
import { useAnalysisQueryState } from '@/components/shared/AnalysisControls'
import { AnalysisTimeRangeSelector } from '@/components/shared/AnalysisTimeRangeSelector'
import { MobileAnalysisTimeControl } from '@/features/mobile/analysis/MobileAnalysisTimeControl'
import { usePreparedAnalysisData } from '@/hooks/useAnalysis'
import { PUBLIC_CAPABILITIES } from '@/hooks/runtimeCapabilities'

vi.mock('@/hooks/useRuntimeCapabilities', () => ({
  useRuntimeCapabilities: () => ({ capabilities: PUBLIC_CAPABILITIES, loading: false }),
}))

afterEach(() => {
  vi.useRealTimers()
  document.body.style.overflow = ''
})

function TimeRangeHarness({ phone }: { phone: boolean }) {
  const { period, periodValue, startDate, endDate, setQuery, apiParams } = useAnalysisQueryState()
  const props = { period, periodValue, startDate, endDate, onChange: setQuery }
  return <>
    {phone ? <MobileAnalysisTimeControl {...props} /> : <AnalysisTimeRangeSelector {...props} />}
    <output data-testid="range-params">{JSON.stringify(apiParams)}</output>
  </>
}

function renderRange(phone: boolean, search = '') {
  return render(<MemoryRouter initialEntries={[`/analysis/stats${search}`]}><TimeRangeHarness phone={phone} /></MemoryRouter>)
}

const ranges = [
  ['年', '按年', '2026-01-01', '2026-12-31'],
  ['月', '按月', '2026-10-01', '2026-10-31'],
  ['周', '按周', '2026-09-28', '2026-10-04'],
  ['天', '按日', '2026-10-03', '2026-10-03'],
] as const

describe('public analysis time ranges', () => {
  it('shows all eight desktop choices on the public surface', () => {
    renderRange(false)
    for (const name of ['全部时间', '最近6月', '最近4周', '年', '月', '周', '天', '自定义']) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument()
    }
  })

  it('shows all eight phone choices on the public surface', () => {
    renderRange(true)
    fireEvent.click(screen.getByRole('button', { name: '选择时间范围，当前全部时间' }))
    const dialog = screen.getByRole('dialog', { name: '时间范围' })
    expect(within(dialog).getAllByRole('radio')).toHaveLength(8)
    for (const name of ['按年', '按月', '按周', '按日', '自定义']) {
      expect(within(dialog).getByRole('radio', { name: new RegExp(`^${name}`) })).toBeInTheDocument()
    }
  })

  it.each(ranges)('sends the selected %s as the same exact date range on desktop and phone', (desktop, phone, start, end) => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 9, 3, 12))
    for (const isPhone of [false, true]) {
      const view = renderRange(isPhone)
      if (isPhone) {
        fireEvent.click(screen.getByRole('button', { name: '选择时间范围，当前全部时间' }))
        fireEvent.click(screen.getByRole('radio', { name: new RegExp(`^${phone}`) }))
        fireEvent.click(screen.getByRole('button', { name: '打开日期选择器' }))
        if (desktop === '年') {
          fireEvent.click(screen.getByRole('button', { name: '10月' }))
        } else {
          const day = document.querySelector('[data-day="2026-10-03"] button')
          expect(day).not.toBeNull()
          fireEvent.click(day!)
        }
        fireEvent.click(screen.getByRole('heading', { name: '时间范围' }))
        fireEvent.click(screen.getByRole('button', { name: '应用时间范围' }))
      } else {
        fireEvent.click(screen.getByRole('button', { name: desktop }))
      }
      expect(JSON.parse(screen.getByTestId('range-params').textContent!)).toEqual({
        period: 'custom', start_date: start, end_date: end,
      })
      view.unmount()
    }
  })

  it.each([false, true])('retains custom dates from a shared URL (phone=%s)', phone => {
    renderRange(phone, '?period=custom&start=2026-07-01&end=2026-09-30')
    if (phone) {
      fireEvent.click(screen.getByRole('button', { name: /选择时间范围/ }))
      expect(screen.getByRole('radio', { name: /^自定义/ })).toHaveAttribute('aria-checked', 'true')
      fireEvent.click(screen.getByRole('button', { name: '应用时间范围' }))
    } else {
      expect(screen.getByRole('button', { name: '2026-07-01' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: '2026-09-30' })).toBeInTheDocument()
    }
    expect(JSON.parse(screen.getByTestId('range-params').textContent!)).toEqual({
      period: 'custom', start_date: '2026-07-01', end_date: '2026-09-30',
    })
  })

  it('keeps a missing public range read-only without preparing or showing an active build', async () => {
    const loader = vi.fn().mockRejectedValue(new SnapshotUnavailableError({
      error: 'snapshot_unavailable', status: 'unavailable', family: 'analysis_stats', message: 'missing range',
    }))
    const prepare = vi.fn().mockResolvedValue({ status: 'queued' })
    function MissingRange() {
      const result = usePreparedAnalysisData('analysis_stats', loader, prepare, ['custom', '2026-01-01', '2026-12-31'])
      return <output>{result.error ? `unavailable:${result.switching}` : 'loading'}</output>
    }
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const view = render(<QueryClientProvider client={client}><MissingRange /></QueryClientProvider>)
    await waitFor(() => expect(screen.getByText('unavailable:false')).toBeInTheDocument())
    expect(loader).toHaveBeenCalledTimes(1)
    expect(prepare).not.toHaveBeenCalled()
    view.unmount()
    client.clear()
  })
})
