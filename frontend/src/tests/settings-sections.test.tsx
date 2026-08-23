import { act, fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { BillboardParamsSection } from '@/features/settings/components/BillboardParamsSection'
import { DataFilteringSection } from '@/features/settings/components/DataFilteringSection'
import { ImportProgressCard } from '@/features/settings/components/SettingsHelpers'

describe('Settings sections', () => {
  it('uses page-level numbering for statistical settings sections', () => {
    render(
      <>
        <DataFilteringSection
          settings={{ min_ms: 30000, music_only: true, merge_enabled: true, max_merge_gap_minutes: 5 }}
          onUpdate={vi.fn()}
          onRequiresRebuild={vi.fn()}
          chineseStyle="original"
          onChangeChineseStyle={vi.fn()}
        />
        <BillboardParamsSection
          settings={{
            bb_top_n: 30,
            bb_album_top_n: 20,
            bb_artist_top_n: 20,
            bb_week_start_dow: 4,
            bb_week_start_hour: 0,
            include_compilations: false,
          }}
          onUpdate={vi.fn()}
          onRequiresRebuild={vi.fn()}
        />
      </>,
    )

    expect(screen.getByText('03 · 数据与显示')).toBeInTheDocument()
    expect(screen.getByText('04 · 榜单参数')).toBeInTheDocument()
    expect(screen.queryByText('01 · 数据与显示')).not.toBeInTheDocument()
    expect(screen.queryByText('02 · 榜单参数')).not.toBeInTheDocument()
  })

  it('renders data filtering controls without internal rebuild button', () => {
    render(
      <DataFilteringSection
        settings={{ min_ms: 30000, music_only: true, merge_enabled: true, max_merge_gap_minutes: 5 }}
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
        settings={{ min_ms: 30000, music_only: true, merge_enabled: true, max_merge_gap_minutes: 5 }}
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

  it('shows that exact music search statistics continue in the background', () => {
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
            music_search_snapshot_status: 'warming',
          },
        }}
        onStart={vi.fn()}
      />,
    )

    expect(screen.getByText('导入完成，音乐查找统计正在后台更新')).toBeInTheDocument()
  })

  it('shows exact duplicate skips and a partial post-import health result', () => {
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
            duplicate_records_skipped: 57,
            post_import_health: { status: 'partial' },
          },
        }}
        onStart={vi.fn()}
      />,
    )

    expect(screen.getByText('导入完成，数据可用但有健康提醒')).toBeInTheDocument()
    expect(screen.getByText('跳过重复记录 57')).toBeInTheDocument()
  })

  it('explains that a failed import was rolled back', () => {
    render(
      <ImportProgressCard
        title="串流数据"
        label="当前数据库记录数：1,000"
        job={{
          job_id: 'fixture',
          status: 'error',
          progress_pct: 0.4,
          message: 'fixture import failure',
          result: {
            database_snapshot: { status: 'created' },
            rollback: { status: 'restored' },
          },
        }}
        onStart={vi.fn()}
      />,
    )

    expect(screen.getByText('fixture import failure')).toBeInTheDocument()
    expect(screen.getByText('已恢复导入前数据库，原有播放数据保持不变。')).toBeInTheDocument()
  })

  it('explains that a failed first import was removed', () => {
    render(
      <ImportProgressCard
        title="串流数据"
        label="当前数据库记录数：0"
        job={{
          job_id: 'fixture',
          status: 'error',
          progress_pct: 0.2,
          message: 'fixture first import failure',
          result: {
            database_snapshot: { status: 'skipped', reason: 'database_not_found' },
            rollback: { status: 'removed_new_database' },
          },
        }}
        onStart={vi.fn()}
      />,
    )

    expect(screen.getByText('首次导入未完成，已清理本次创建的半成品数据库。')).toBeInTheDocument()
  })

  it('asks for explicit confirmation before importing with warnings', () => {
    const onStart = vi.fn()
    render(
      <ImportProgressCard
        title="串流数据"
        label="当前数据库记录数：1,000"
        job={{
          job_id: 'fixture',
          status: 'needs_confirmation',
          progress_pct: 0,
          message: '导入需要确认：发现导入前警告，数据库尚未修改',
          result: {
            preflight: { warnings: ['日期范围重叠'], confirmation_token: 'token-v1' },
            import_started: false,
          },
        }}
        onStart={onStart}
      />,
    )

    expect(screen.getByText('数据库尚未修改；再次点击按钮表示你已核对这些警告并继续。')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '确认风险并导入' }))
    expect(onStart).toHaveBeenCalledWith({
      mode: 'auto',
      confirmWarnings: true,
      confirmPlan: false,
      confirmationToken: 'token-v1',
    })
  })

  it('allows an ambiguous package to request fail-closed tail validation', () => {
    const onStart = vi.fn()
    render(
      <ImportProgressCard
        title="串流数据"
        label="当前数据库记录数：1,000"
        job={null}
        preflight={{
          status: 'healthy',
          streaming_files: [],
          account_files: [],
          duplicate_file_groups: [],
          date_overlaps: [],
          blockers: [],
          warnings: [],
          detected_relation: 'ambiguous',
          requires_confirmation: true,
          requested_mode: 'auto',
          confirmation_token: 'token-v1',
        }}
        supportsImportMode
        onStart={onStart}
      />,
    )

    expect(screen.getByRole('button', { name: '请先选择处理方式' })).toBeDisabled()
    expect(screen.getByText('追加只接受可证明的尾部记录；完整替换前会创建数据库快照。两种写入后的榜单和其他派生数据暂时都按完整维护流程更新。')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /作为尾部增量验证/ }))
    fireEvent.click(screen.getByRole('button', { name: '验证并追加' }))
    expect(onStart).toHaveBeenCalledWith({
      mode: 'append',
      confirmWarnings: false,
      confirmPlan: false,
      confirmationToken: 'token-v1',
    })
  })

  it('forces a fresh visible preflight after a confirmation token becomes stale', () => {
    const onStart = vi.fn()
    const onRecheck = vi.fn()
    render(
      <ImportProgressCard
        title="串流数据"
        label="当前数据库记录数：1,000"
        job={{
          job_id: 'fixture',
          status: 'needs_confirmation',
          progress_pct: 0,
          message: '输入文件或当前数据已变化，请重新核对最新导入计划',
          result: {
            confirmation_reason: 'stale_plan',
            preflight: {
              detected_relation: 'snapshot_superset',
              requires_confirmation: false,
              confirmation_token: 'token-v2',
              warnings: [],
            },
          },
        }}
        supportsImportMode
        onStart={onStart}
        onRecheck={onRecheck}
      />,
    )

    expect(screen.getByText('旧确认已失效；请重新运行上方检查，查看最新记录数量、关系和策略。')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '重新检查最新计划' }))
    expect(onRecheck).toHaveBeenCalledOnce()
    expect(onStart).not.toHaveBeenCalled()
  })

  it('continues only after the visible preflight matches the refreshed token', () => {
    const onStart = vi.fn()
    render(
      <ImportProgressCard
        title="串流数据"
        label="当前数据库记录数：1,000"
        job={{
          job_id: 'fixture',
          status: 'needs_confirmation',
          progress_pct: 0,
          message: '输入文件或当前数据已变化，请重新核对最新导入计划',
          result: {
            confirmation_reason: 'stale_plan',
            preflight: {
              detected_relation: 'snapshot_superset',
              requires_confirmation: false,
              confirmation_token: 'token-v2',
              warnings: [],
            },
          },
        }}
        preflight={{
          status: 'healthy',
          streaming_files: [],
          account_files: [],
          duplicate_file_groups: [],
          date_overlaps: [],
          blockers: [],
          warnings: [],
          detected_relation: 'snapshot_superset',
          requires_confirmation: false,
          confirmation_token: 'token-v2',
        }}
        supportsImportMode
        onStart={onStart}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '按最新计划导入' }))
    expect(onStart).toHaveBeenCalledWith({
      mode: 'auto',
      confirmWarnings: false,
      confirmPlan: false,
      confirmationToken: 'token-v2',
    })
  })

  it('preserves warning confirmation when a job also needs plan confirmation', () => {
    const onStart = vi.fn()
    render(
      <ImportProgressCard
        title="串流数据"
        label="当前数据库记录数：1,000"
        job={{
          job_id: 'fixture',
          status: 'needs_confirmation',
          progress_pct: 0,
          message: '需要确认追加或替换方式',
          result: {
            preflight: {
              requires_confirmation: true,
              warnings: ['日期范围重叠'],
              confirmation_token: 'token-v1',
            },
          },
        }}
        supportsImportMode
        onStart={onStart}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /使用输入包替换/ }))
    fireEvent.click(screen.getByRole('button', { name: '确认完整替换并导入' }))
    expect(onStart).toHaveBeenCalledWith({
      mode: 'replace',
      confirmWarnings: true,
      confirmPlan: true,
      confirmationToken: 'token-v1',
    })
  })

  it('shows an explicit no-op completion result', () => {
    render(
      <ImportProgressCard
        title="串流数据"
        label="当前数据库记录数：1,000"
        job={{
          job_id: 'fixture',
          status: 'done',
          progress_pct: 1,
          message: '无需更新',
          result: { detected_relation: 'identical', executed_strategy: 'noop', noop: true },
        }}
        onStart={vi.fn()}
      />,
    )

    expect(screen.getByText('数据未变化，已跳过导入')).toBeInTheDocument()
    expect(screen.queryByText('导入完成，派生数据已更新')).not.toBeInTheDocument()
  })

  it('does not mislabel an explicit identical replacement as a no-op', () => {
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
            detected_relation: 'identical',
            executed_strategy: 'full',
            noop: false,
            maintenance_status: 'ok',
          },
        }}
        onStart={vi.fn()}
      />,
    )

    expect(screen.getByText('导入完成，派生数据已更新')).toBeInTheDocument()
    expect(screen.queryByText('数据未变化，已跳过导入')).not.toBeInTheDocument()
  })

  it('keeps a blocked import from looking like a completed job', () => {
    const onStart = vi.fn()
    render(
      <ImportProgressCard
        title="串流数据"
        label="当前数据库记录数：1,000"
        job={{
          job_id: 'fixture',
          status: 'blocked',
          progress_pct: 0,
          message: '导入已阻断：导入前检查发现硬性问题，数据库未修改',
          result: { preflight: { blockers: ['存在完全重复文件'] }, import_started: false },
        }}
        onStart={onStart}
      />,
    )

    expect(screen.getByText('导入已阻断：导入前检查发现硬性问题，数据库未修改')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '重新检查' }))
    expect(onStart).toHaveBeenCalledWith({ mode: 'auto', confirmWarnings: false, confirmPlan: false })
  })
})
