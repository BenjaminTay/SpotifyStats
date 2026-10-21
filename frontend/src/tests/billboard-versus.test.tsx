import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { buildBillboardContextParams } from '@/features/billboard/billboardContext'
import { VersusReleaseCycleSection } from '@/features/billboard/versus/VersusReleaseCycleSection'
import { EntityQueue, SearchableAddSelect } from '@/features/billboard/versus/versusPrimitives'

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
  it('gives queue reordering and removal controls a 44 by 44 phone touch target', () => {
    render(<EntityQueue items={[{ display: 'One' }, { display: 'Two' }]} onRemove={vi.fn()} onMoveUp={vi.fn()} onMoveDown={vi.fn()} />)
    for (const button of screen.getAllByRole('button')) {
      expect(button).toHaveClass('max-md:min-h-11', 'max-md:min-w-11')
    }
  })
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
  const albums = [
    { albumName: 'Midnights', artistName: 'Taylor Swift', name: 'Midnights — Taylor Swift' },
    { albumName: 'THE TORTURED POETS DEPARTMENT', artistName: 'Taylor Swift', name: 'THE TORTURED POETS DEPARTMENT — Taylor Swift' },
  ]

  it('hides the removed peak timing and 24-week chart-window metrics', () => {
    useReleaseCycleCompareMock.mockReturnValue({
      results: [
          { metrics: { debut_rank: 1, peak_rank: 1, weeks_to_peak: 0, weeks_on_chart: 24, release_week_plays: 718, artist_impact: 1.8, market_impact: 2.2, half_life: 6 } },
          { metrics: { debut_rank: 1, peak_rank: 1, weeks_to_peak: 0, weeks_on_chart: 24, release_week_plays: 311, artist_impact: 1.5, market_impact: 1.6, half_life: 20 } },
      ],
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

  it('retains every album column when all releases are unavailable and explains each reason', () => {
    useReleaseCycleCompareMock.mockReturnValue({
      results: [{ status: 'unavailable', reason: 'release_day_unconfirmed' }, { status: 'unavailable', reason: 'artist_identity_unconfirmed' }],
      loading: false,
    })
    render(<VersusReleaseCycleSection albums={albums} billboardParams={{}} />)
    expect(screen.getByRole('table', { name: '发行周期对比' })).toBeVisible()
    expect(screen.getByText('缺少已确认的发行日，需补充发行证据。')).toBeVisible()
    expect(screen.getByText('专辑艺人身份尚未确认。')).toBeVisible()
    expect(screen.getAllByRole('columnheader')).toHaveLength(3)
    expect(screen.getAllByText('不可计算')).toHaveLength(12)
  })

  it('keeps real zero separate from missing metrics in a partially successful comparison', () => {
    useReleaseCycleCompareMock.mockReturnValue({
      results: [
        { status: 'unavailable', reason: 'release_date_coarse' },
        { status: 'ready', release_date: '2024-04-19', metrics: { release_week_plays: 0, debut_rank: null, peak_rank: null, half_life: null }, metric_reasons: { debut_rank: 'no_chart_entry', peak_rank: 'no_chart_entry', half_life: 'no_playback' } },
      ],
      loading: false,
    })
    render(<VersusReleaseCycleSection albums={albums} billboardParams={{}} />)
    const row = screen.getByRole('row', { name: '发行周播放 不可计算 0' })
    expect(within(row).getByText('0')).toBeVisible()
    expect(screen.getByText('来源日期仅精确到年或月，无法按发行日对齐。')).toBeVisible()
    expect(screen.getAllByText('窗口内未上榜')).toHaveLength(2)
    expect(screen.getByText('无播放')).toBeVisible()
    expect(screen.getByRole('region', { name: '发行周期对比表格，可横向滚动' })).toHaveClass('overflow-x-auto')
  })

  it.each([
    ['release_source_unconfirmed', '发行版本来源尚未确认。'],
    ['release_date_invalid', '发行日期无效，需核对来源。'],
    ['release_date_conflict', '发行日期存在冲突，需核对目标版本。'],
    ['entity_not_found', '未找到对应的专辑项目或发行版本。'],
    ['release_ambiguous', '无法唯一确定发行版本，需核对版本关联。'],
  ])('shows the precise %s cause', (reason, message) => {
    useReleaseCycleCompareMock.mockReturnValue({ results: [{ status: 'unavailable', reason }], loading: false })
    render(<VersusReleaseCycleSection albums={albums} billboardParams={{}} />)
    expect(screen.getByText(message)).toBeVisible()
  })

  it('preserves columns during a request failure and exposes an accessible retry', async () => {
    const refetch = vi.fn()
    useReleaseCycleCompareMock.mockReturnValue({ results: [], loading: false, error: '榜单数据正在准备，请稍后重新加载。', refetch })
    render(<VersusReleaseCycleSection albums={albums} billboardParams={{}} />)
    expect(screen.getByRole('alert')).toHaveTextContent('榜单数据正在准备')
    expect(screen.getAllByRole('columnheader')).toHaveLength(3)
    const retry = screen.getByRole('button', { name: '重新加载' })
    expect(retry).toHaveClass('min-h-11', 'min-w-11')
    await userEvent.setup().click(retry)
    expect(refetch).toHaveBeenCalledTimes(1)
  })

  it('keeps the table and queue columns visible while loading or waiting for upstream reads', () => {
    useReleaseCycleCompareMock.mockReturnValue({ results: [], loading: true })
    const { rerender } = render(<VersusReleaseCycleSection albums={albums} billboardParams={{}} />)
    expect(screen.getByRole('status')).toHaveTextContent('正在加载发行周期')
    expect(screen.getByRole('table')).toHaveAttribute('aria-busy', 'true')
    expect(screen.getAllByRole('columnheader')).toHaveLength(3)
    rerender(<VersusReleaseCycleSection albums={albums} billboardParams={{}} enabled={false} />)
    expect(screen.getByRole('table')).toBeVisible()
    expect(screen.getByRole('status')).toHaveTextContent('等待当前对决数据就绪')
    expect(screen.getAllByRole('columnheader')).toHaveLength(3)
  })
})
