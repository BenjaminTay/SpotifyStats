import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { DataFilteringSection } from '@/features/settings/components/DataFilteringSection'

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
})
