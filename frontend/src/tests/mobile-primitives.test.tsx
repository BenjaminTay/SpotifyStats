import { createRef, useRef, useState } from 'react'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { format, parseISO, startOfWeek } from 'date-fns'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  MobileBottomSheet,
  MobileChartCard,
  MobileEntityDetailSheet,
  MobileEntityRow,
  MobileFilterSheet,
  MobileFullscreenChart,
  MobilePageHeader,
  MobilePagination,
  MobileRankList,
  MobileStatePanel,
  MobileTimeRangeSheet,
  type MobileFilterValues,
  type MobileTimeRangeValue,
} from '@/components/mobile'

afterEach(() => {
  document.body.style.overflow = ''
})

function BottomSheetHarness() {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLButtonElement>(null)
  return (
    <>
      <button ref={triggerRef} type="button" onClick={() => setOpen(true)}>打开设置</button>
      <MobileBottomSheet
        open={open}
        onOpenChange={setOpen}
        title="测试弹层"
        triggerRef={triggerRef}
        footer={<button type="button">最后一个操作</button>}
      >
        <button type="button">第一个操作</button>
      </MobileBottomSheet>
    </>
  )
}

describe('mobile primitives', () => {
  it('bottom sheet traps focus, locks scrolling, closes on Escape, and restores trigger focus', async () => {
    const user = userEvent.setup()
    render(<BottomSheetHarness />)
    const trigger = screen.getByRole('button', { name: '打开设置' })

    await user.click(trigger)
    const dialog = screen.getByRole('dialog', { name: '测试弹层' })
    expect(document.body.style.overflow).toBe('hidden')
    const closeButton = within(dialog).getByRole('button', { name: /关闭测试弹层/ })
    const lastButton = within(dialog).getByRole('button', { name: '最后一个操作' })
    await waitFor(() => expect(closeButton).toHaveFocus())
    lastButton.focus()
    await user.tab()
    expect(closeButton).toHaveFocus()
    await user.tab({ shift: true })
    expect(lastButton).toHaveFocus()

    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(trigger).toHaveFocus())
    expect(document.body.style.overflow).toBe('')
  })

  it('keeps filter changes as a draft until Apply and discards them on close', async () => {
    const user = userEvent.setup()
    const applied: MobileFilterValues = { metric: 'plays', entity: ['track'] }
    const onApply = vi.fn()
    const { rerender } = render(
      <MobileFilterSheet
        open
        onOpenChange={vi.fn()}
        groups={[
          { id: 'metric', label: '指标', type: 'single', options: [
            { value: 'plays', label: '播放次数' },
            { value: 'hours', label: '播放时长' },
          ] },
          { id: 'entity', label: '实体', type: 'multiple', options: [
            { value: 'track', label: '歌曲' },
            { value: 'album', label: '专辑' },
          ] },
        ]}
        appliedValues={applied}
        defaultValues={{ metric: 'plays', entity: ['track'] }}
        onApply={onApply}
      />,
    )

    await user.click(screen.getByRole('radio', { name: '播放时长' }))
    await user.click(screen.getByRole('checkbox', { name: '专辑' }))
    await user.click(screen.getByRole('button', { name: '关闭筛选条件' }))
    expect(onApply).not.toHaveBeenCalled()

    rerender(
      <MobileFilterSheet
        open={false}
        onOpenChange={vi.fn()}
        groups={[]}
        appliedValues={applied}
        onApply={onApply}
      />,
    )
    rerender(
      <MobileFilterSheet
        open
        onOpenChange={vi.fn()}
        groups={[{ id: 'metric', label: '指标', type: 'single', options: [
          { value: 'plays', label: '播放次数' },
          { value: 'hours', label: '播放时长' },
        ] }]}
        appliedValues={applied}
        defaultValues={{ metric: 'plays' }}
        onApply={onApply}
      />,
    )
    expect(screen.getByRole('radio', { name: '播放次数' })).toHaveAttribute('aria-checked', 'true')
    await user.click(screen.getByRole('radio', { name: '播放时长' }))
    await user.click(screen.getByRole('button', { name: '重置为默认' }))
    expect(screen.getByRole('radio', { name: '播放次数' })).toHaveAttribute('aria-checked', 'true')
    await user.click(screen.getByRole('radio', { name: '播放时长' }))
    await user.click(screen.getByRole('button', { name: '应用筛选' }))
    expect(onApply).toHaveBeenLastCalledWith(expect.objectContaining({ metric: 'hours' }))
  })

  it('offers all time modes and validates custom dates before applying', async () => {
    const user = userEvent.setup()
    const onApply = vi.fn()
    render(
      <MobileTimeRangeSheet
        open
        onOpenChange={vi.fn()}
        value={{ period: 'lifetime' }}
        onApply={onApply}
      />,
    )

    expect(screen.getAllByRole('radio')).toHaveLength(8)
    await user.click(screen.getByRole('radio', { name: /自定义/ }))
    expect(screen.getByRole('button', { name: '应用时间范围' })).toBeDisabled()
    expect(screen.queryByRole('gridcell')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '打开日期范围选择器' }))
    const calendarPopover = document.querySelector('[data-slot="popover-content"]') as HTMLElement
    const selectableDayButtons = () => within(calendarPopover).getAllByRole('gridcell')
      .filter((cell) => cell.querySelector('button:not([disabled])') && !cell.hasAttribute('data-outside'))
      .map((cell) => cell.querySelector('button') as HTMLButtonElement)
    await user.click(selectableDayButtons()[0])
    expect(screen.getByRole('button', { name: '打开日期范围选择器' })).toHaveAttribute('aria-expanded', 'true')
    await user.click(selectableDayButtons()[1])
    expect(screen.getByRole('button', { name: '打开日期范围选择器' })).toHaveAttribute('aria-expanded', 'true')
    await user.click(screen.getByRole('heading', { name: '时间范围' }))
    expect(document.querySelector('[data-slot="popover-content"]')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '应用时间范围' }))
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({
      period: 'custom',
      start: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
      end: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
    }))
  })

  it('selects a whole Monday-based week from the calendar', async () => {
    const user = userEvent.setup()
    const onApply = vi.fn()
    render(
      <MobileTimeRangeSheet
        open
        onOpenChange={vi.fn()}
        value={{ period: 'lifetime' }}
        onApply={onApply}
      />,
    )

    await user.click(screen.getByRole('radio', { name: /按周/ }))
    expect(screen.queryByRole('gridcell')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '打开日期选择器' }))
    const calendarPopover = document.querySelector('[data-slot="popover-content"]') as HTMLElement
    const targetCell = within(calendarPopover).getAllByRole('gridcell').find((cell) =>
      cell.getAttribute('data-day') && !cell.hasAttribute('data-outside') && cell.querySelector('button:not([disabled])'),
    ) as HTMLElement
    const selectedDay = parseISO(targetCell.getAttribute('data-day')!)
    await user.click(targetCell.querySelector('button') as HTMLButtonElement)
    expect(screen.getByRole('button', { name: '打开日期选择器' })).toHaveAttribute('aria-expanded', 'true')
    await user.click(screen.getByRole('button', { name: '应用时间范围' }))

    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({
      period: 'week',
      periodValue: format(startOfWeek(selectedDay, { weekStartsOn: 1 }), 'yyyy-MM-dd'),
    }))
  })

  it('renders long entity names, missing artwork, fixed ranks, and credited artists', () => {
    render(
      <MemoryRouter>
        <MobileEntityRow
          entityType="track"
          rank={41}
          title="这是一首在三百六十像素视口中仍然需要保留辨识度的特别特别长的歌曲名称"
          subtitle="主艺人、合作艺人与另一位署名艺人"
          coverUrl={null}
          metric="1,284"
          metricLabel="播放"
          facts={[{ label: 'PK', value: '#3' }, { label: '在榜', value: '18 周' }]}
          badges={['上升']}
          to="/music/tracks/9"
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('41')).toBeInTheDocument()
    expect(screen.getByText(/主艺人、合作艺人/)).toBeInTheDocument()
    expect(screen.getByRole('link')).toHaveAttribute('href', '/music/tracks/9')
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('preserves supplied ranks in lists and exposes textual pagination controls', async () => {
    const user = userEvent.setup()
    const onPageChange = vi.fn()
    render(
      <MemoryRouter>
        <MobileRankList
          title="单曲总榜"
          rows={[
            { entityType: 'track', rank: 41, title: '第一条可见结果', metric: '91', metricLabel: '播放' },
            { entityType: 'track', rank: 57, title: '第二条可见结果', metric: '73', metricLabel: '播放' },
          ]}
          page={3}
          pageCount={8}
          onPageChange={onPageChange}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('41')).toBeInTheDocument()
    expect(screen.getByText('57')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /上一页/ }))
    expect(onPageChange).toHaveBeenCalledWith(2)
    expect(screen.getByRole('button', { name: /下一页/ })).toBeEnabled()
  })

  it('shows complete entity facts, range note, detail link, and share action', async () => {
    const user = userEvent.setup()
    const onShare = vi.fn()
    render(
      <MemoryRouter>
        <MobileEntityDetailSheet
          open
          onOpenChange={vi.fn()}
          entityType="album"
          title="A Very Long Album Project Name"
          subtitle="Artist Name"
          metric="PK #2"
          metricLabel="个人专辑榜"
          facts={[{ label: '播放', value: '2,048 次' }, { label: '在榜', value: '31 周' }]}
          badges={['年榜 #6']}
          rangeNote="全部时间 · 动态阈值"
          detailTo="/music/albums/example"
          onShare={onShare}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('统计范围：全部时间 · 动态阈值')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /查看完整详情/ })).toHaveAttribute('href', '/music/albums/example')
    await user.click(screen.getByRole('button', { name: '分享' }))
    expect(onShare).toHaveBeenCalledOnce()
  })

  it('supports chart series toggles and an accessible fullscreen chart', async () => {
    const user = userEvent.setup()
    const toggle = vi.fn()
    const triggerRef = createRef<HTMLButtonElement>()
    const { rerender } = render(
      <MobileChartCard
        title="月度趋势"
        chart={<div aria-label="示意图表">Chart</div>}
        conclusion="五月是全年播放高峰。"
        series={[{ id: 'plays', label: '播放次数', active: true }]}
        onToggleSeries={toggle}
      />,
    )
    await user.click(screen.getByRole('switch', { name: '播放次数' }))
    expect(toggle).toHaveBeenCalledWith('plays')

    rerender(
      <MobileFullscreenChart open onOpenChange={vi.fn()} title="月度趋势" triggerRef={triggerRef}>
        <div>全屏图表内容</div>
      </MobileFullscreenChart>,
    )
    expect(screen.getByRole('dialog', { name: '月度趋势' })).toBeInTheDocument()
    expect(screen.queryByText('五月是全年播放高峰。')).not.toBeInTheDocument()
  })

  it('covers page headers, loading/empty/error/config states, and list-end pagination', () => {
    const { rerender } = render(<MobilePageHeader eyebrow="Analysis" title="播放统计" />)
    expect(screen.getByRole('heading', { level: 1, name: '播放统计' })).toBeInTheDocument()

    rerender(<MobileStatePanel variant="loading" />)
    expect(screen.getByRole('status', { name: '正在加载' })).toBeInTheDocument()
    rerender(<MobileStatePanel variant="empty" />)
    expect(screen.getByText('这里还没有内容')).toBeInTheDocument()
    rerender(<MobileStatePanel variant="error" />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
    rerender(<MobileStatePanel variant="config" />)
    expect(screen.getByText('需要先完成设置')).toBeInTheDocument()
    rerender(<MobilePagination mode="load-more" hasMore={false} />)
    expect(screen.getByText(/已经到底了/)).toBeInTheDocument()
  })
})

const _typeOnlyTimeRangeCheck: MobileTimeRangeValue = { period: 'year', periodValue: '2025' }
void _typeOnlyTimeRangeCheck
