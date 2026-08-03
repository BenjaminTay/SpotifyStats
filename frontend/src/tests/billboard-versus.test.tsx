import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { buildBillboardContextParams } from '@/features/billboard/billboardContext'
import { SearchableAddSelect } from '@/features/billboard/versus/versusPrimitives'

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
