import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { DataFilteringSection } from '@/features/settings/components/DataFilteringSection'

describe('Settings sections', () => {
  it('renders data filtering rebuild controls without throwing', () => {
    render(
      <DataFilteringSection
        settings={{
          min_ms: 30000,
          music_only: true,
          merge_enabled: true,
        }}
        onUpdate={vi.fn()}
        onRebuild={vi.fn()}
        rebuildLoading={false}
        chineseStyle="original"
        onChangeChineseStyle={vi.fn()}
      />,
    )

    expect(screen.getByText('播放过滤')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重建聚合表' })).toBeInTheDocument()
  })
})
