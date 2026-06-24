import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

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
