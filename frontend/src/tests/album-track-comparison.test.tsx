import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { TrackComparePanel } from '@/features/settings/components/SettingsHelpers'

describe('complete album track comparison', () => {
  it('keeps disc and track numbers in their API positions', () => {
    render(<TrackComparePanel data={{ shared: [['Second Disc Song', 'Artist', 2, 7]], only_in_a: [], only_in_b: [] }} />)
    expect(screen.getByText('Track 7 · Disc 2')).toBeInTheDocument()
  })

  it('keeps membership visible and labels unknown release positions', () => {
    render(<TrackComparePanel data={{ shared: [['A&W', 'Lana Del Rey', null, null]], only_in_a: [], only_in_b: [], position_incomplete_album_ids: [181] }} />)
    expect(screen.getByText('A&W')).toBeInTheDocument()
    expect(screen.getByText('位置未知')).toBeInTheDocument()
    expect(screen.getByText(/曲目异同可用/)).toBeInTheDocument()
    expect(screen.queryByText('Track 1 · Disc 1')).not.toBeInTheDocument()
  })

  it('explains incomplete evidence without presenting empty or exclusive tracks', () => {
    render(<TrackComparePanel data={{ shared: [], only_in_a: [], only_in_b: [], incomplete_album_ids: [1] }} />)
    expect(screen.getByText(/专辑完整曲目表尚未就绪/)).toBeInTheDocument()
    expect(screen.queryByText('无曲目数据')).not.toBeInTheDocument()
  })
})
