import { act, fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { BillboardParamsSection } from '@/features/settings/components/BillboardParamsSection'
import { DataFilteringSection } from '@/features/settings/components/DataFilteringSection'
import { ImportProgressCard } from '@/features/settings/components/SettingsHelpers'

describe('Settings sections', () => {
  it('renders data filtering controls without internal rebuild button', () => {
    render(
      <DataFilteringSection
        settings={{ min_ms: 30000, music_only: true, merge_enabled: true }}
        onUpdate={vi.fn()}
        onRequiresRebuild={vi.fn()}
        chineseStyle="original"
        onChangeChineseStyle={vi.fn()}
      />,
    )

    expect(screen.getByText('播放过滤')).toBeInTheDocument()
    expect(screen.getByText('显示偏好')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '重建聚合表' })).not.toBeInTheDocument()
  })

  it('notifies parent when a filtering toggle changes statistics semantics', async () => {
    const onRequiresRebuild = vi.fn()
    const onUpdate = vi.fn()

    render(
      <DataFilteringSection
        settings={{ min_ms: 30000, music_only: true, merge_enabled: true }}
        onUpdate={onUpdate}
        onRequiresRebuild={onRequiresRebuild}
        chineseStyle="original"
        onChangeChineseStyle={vi.fn()}
      />,
    )

    const musicToggle = screen.getByRole('switch', { name: '仅音乐' })
    expect(musicToggle).toBeInTheDocument()
    fireEvent.click(musicToggle)

    // updateAndRequireRebuild calls both onUpdate and onRequiresRebuild
    expect(onUpdate).toHaveBeenCalledWith({ music_only: false })
    expect(onRequiresRebuild).toHaveBeenCalled()
  })

  it.each([
    ['单曲榜 Top N', { bb_top_n: 55 }, 55, 55],
    ['专辑榜 Top N', { bb_album_top_n: 55 }, 55, 55],
    ['艺人榜 Top N', { bb_artist_top_n: 55 }, 55, 55],
  ])('keeps %s responsive while committing only after the slider interaction ends', async (label, payload, expectedValue, clientX) => {
    const onRequiresRebuild = vi.fn()
    const onUpdate = vi.fn()

    render(
      <BillboardParamsSection
        settings={{
          bb_top_n: 30,
          bb_album_top_n: 20,
          bb_artist_top_n: 20,
          bb_week_start_dow: 4,
          bb_week_start_hour: 0,
          include_compilations: false,
        }}
        onUpdate={onUpdate}
        onRequiresRebuild={onRequiresRebuild}
      />,
    )

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /榜单参数/ }))
    })

    const slider = document.querySelector<HTMLInputElement>(`input[type="range"][aria-label="${label}"]`)
    expect(slider).toBeTruthy()
    if (!slider) return
    const root = slider.closest('[data-slot="slider"]')
    const control = root?.firstElementChild as HTMLElement | null
    expect(control).toBeTruthy()
    if (!control) return

    control.getBoundingClientRect = () => ({
      width: 100,
      height: 10,
      bottom: 10,
      left: 0,
      right: 100,
      top: 0,
      x: 0,
      y: 0,
      toJSON: () => {},
    })
    Object.assign(control, {
      hasPointerCapture: () => false,
      releasePointerCapture: vi.fn(),
      setPointerCapture: vi.fn(),
    })

    await act(async () => {
      fireEvent.pointerDown(control, { button: 0, clientX, clientY: 5 })
    })

    expect(slider).toHaveValue(String(expectedValue))
    expect(onUpdate).not.toHaveBeenCalled()
    expect(onRequiresRebuild).not.toHaveBeenCalled()

    await act(async () => {
      fireEvent.pointerUp(document, { button: 0, buttons: 0, clientX, clientY: 5 })
    })

    expect(onUpdate).toHaveBeenCalledWith(payload)
    expect(onRequiresRebuild).toHaveBeenCalledOnce()
  })

  it('uses a shared visual scale for the Billboard Top N sliders', async () => {
    render(
      <BillboardParamsSection
        settings={{
          bb_top_n: 30,
          bb_album_top_n: 30,
          bb_artist_top_n: 30,
          bb_week_start_dow: 4,
          bb_week_start_hour: 0,
          include_compilations: false,
        }}
        onUpdate={vi.fn()}
        onRequiresRebuild={vi.fn()}
      />,
    )

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /榜单参数/ }))
    })

    const sliders = ['单曲榜 Top N', '专辑榜 Top N', '艺人榜 Top N'].map((label) => {
      const slider = document.querySelector<HTMLInputElement>(`input[type="range"][aria-label="${label}"]`)
      expect(slider).toBeTruthy()
      return slider
    })

    for (const slider of sliders) {
      expect(slider).toHaveAttribute('min', '0')
      expect(slider).toHaveAttribute('max', '100')
      expect(slider).toHaveValue('30')
    }
  })

  it('keeps the album compilation switch in settings without requiring aggregation rebuild', async () => {
    const onRequiresRebuild = vi.fn()
    const onUpdate = vi.fn()

    render(
      <BillboardParamsSection
        settings={{
          bb_top_n: 30,
          bb_album_top_n: 20,
          bb_artist_top_n: 20,
          bb_week_start_dow: 4,
          bb_week_start_hour: 0,
          include_compilations: false,
        }}
        onUpdate={onUpdate}
        onRequiresRebuild={onRequiresRebuild}
      />,
    )

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /榜单参数/ }))
    })

    fireEvent.click(screen.getByRole('switch', { name: '专辑榜包含精选集' }))

    expect(onUpdate).toHaveBeenCalledWith({ include_compilations: true })
    expect(onRequiresRebuild).not.toHaveBeenCalled()
  })

  it('shows partial metadata maintenance result after streaming import', () => {
    render(
      <ImportProgressCard
        title="串流数据"
        label="当前数据库记录数：1,000"
        job={{
          job_id: 'fixture',
          status: 'done',
          progress_pct: 1,
          message: '导入完成',
          result: {
            maintenance_status: 'partial',
            unresolved_recent_tracks: 3,
            unresolved_recent_albums: 2,
          },
        }}
        onStart={vi.fn()}
      />,
    )

    expect(screen.getByText('播放数据已导入，部分 Spotify 元数据待补全')).toBeInTheDocument()
    expect(screen.getByText('未解析曲目 3')).toBeInTheDocument()
    expect(screen.getByText('未解析专辑 2')).toBeInTheDocument()
  })

  it('shows derived data refresh success after streaming import', () => {
    render(
      <ImportProgressCard
        title="串流数据"
        label="当前数据库记录数：1,000"
        job={{
          job_id: 'fixture',
          status: 'done',
          progress_pct: 1,
          message: '导入完成',
          result: {
            maintenance_status: 'ok',
            tracks_metadata_updated: 12,
            albums_metadata_updated: 4,
          },
        }}
        onStart={vi.fn()}
      />,
    )

    expect(screen.getByText('导入完成，派生数据已更新')).toBeInTheDocument()
    expect(screen.getByText('曲目元数据 +12')).toBeInTheDocument()
    expect(screen.getByText('专辑元数据 +4')).toBeInTheDocument()
  })
})
