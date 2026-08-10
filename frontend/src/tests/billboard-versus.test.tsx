import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { buildBillboardContextParams } from '@/features/billboard/billboardContext'
import { VersusReleaseCycleSection } from '@/features/billboard/versus/VersusReleaseCycleSection'
import { SearchableAddSelect } from '@/features/billboard/versus/versusPrimitives'

const useReleaseCycleCompareMock = vi.hoisted(() => vi.fn())

vi.mock('@/hooks/useBillboard', () => ({
  useReleaseCycleCompare: useReleaseCycleCompareMock,
}))

describe('Billboard versus context', () => {
  it('builds a complete cache and request fingerprint', () => {
    expect(buildBillboardContextParams({
      min_ms: 30000,
      music_only: true,
      merge_enabled: true,
      dynamic_threshold: false,
      max_merge_gap_minutes: 45,
      merge_level: 3,
      include_compilations: true,
      bb_top_n: 40,
      bb_album_top_n: 25,
      bb_artist_top_n: 15,
      bb_week_start_dow: 1,
      bb_week_start_hour: 8,
    })).toEqual({
      min_ms: 30000,
      music_only: true,
      merge_enabled: true,
      dynamic_threshold: false,
      max_merge_gap_minutes: 45,
      merge_level: 3,
      include_compilations: true,
      bb_top_n: 40,
      bb_album_top_n: 25,
      bb_artist_top_n: 15,
      bb_week_start_dow: 1,
      bb_week_start_hour: 8,
    })
  })
})

describe('versus searchable picker', () => {
  it('keeps the query and result list open after adding an item', async () => {
    const user = userEvent.setup()
    const onAdd = vi.fn()
    render(
      <SearchableAddSelect
        items={[
          { display: 'GUTS — Olivia Rodrigo', album_name: 'GUTS', artist_name: 'Olivia Rodrigo' },
          { display: 'GUTS (spilled) — Olivia Rodrigo', album_name: 'GUTS (spilled)', artist_name: 'Olivia Rodrigo' },
        ]}
        alreadySelected={[]}
        onAdd={onAdd}
        placeholder="搜索专辑以添加..."
        disabled={false}
      />,
    )

    await user.click(screen.getByRole('button', { name: /搜索专辑以添加/ }))
    const input = screen.getByPlaceholderText('输入关键词搜索...')
    await user.type(input, 'GUTS')
    await user.click(screen.getByRole('button', { name: /GUTS — Olivia Rodrigo/ }))

    expect(onAdd).toHaveBeenCalledTimes(1)
    expect(input).toHaveValue('GUTS')
    expect(screen.getByRole('button', { name: /GUTS \(spilled\)/ })).toBeVisible()
  })
})

describe('versus release cycle comparison', () => {
  it('hides the removed peak timing and 24-week chart-window metrics', () => {
    useReleaseCycleCompareMock.mockReturnValue({
      data: {
        comparisons: [
          { metrics: { debut_rank: 1, peak_rank: 1, weeks_to_peak: 0, weeks_on_chart: 24, release_week_plays: 718, artist_impact: 1.8, market_impact: 2.2, half_life: 6 } },
          { metrics: { debut_rank: 1, peak_rank: 1, weeks_to_peak: 0, weeks_on_chart: 24, release_week_plays: 311, artist_impact: 1.5, market_impact: 1.6, half_life: 20 } },
        ],
      },
      loading: false,
    })

    render(
      <VersusReleaseCycleSection
        albums={[
          { albumName: 'Midnights', artistName: 'Taylor Swift', name: 'Midnights — Taylor Swift' },
          { albumName: 'THE TORTURED POETS DEPARTMENT', artistName: 'Taylor Swift', name: 'THE TORTURED POETS DEPARTMENT — Taylor Swift' },
        ]}
        billboardParams={{}}
      />,
    )

    expect(screen.getByText('首发排名')).toBeInTheDocument()
    expect(screen.getByText('最高排名')).toBeInTheDocument()
    expect(screen.getByText('发行周播放')).toBeInTheDocument()
    expect(screen.queryByText('到达峰值周数')).not.toBeInTheDocument()
    expect(screen.queryByText('发行后 24 周窗口在榜周数')).not.toBeInTheDocument()
  })
})
