import { render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ValueBar } from '@/features/billboard/records/RecordsPrimitives'

vi.mock('@/hooks/useViewportMode', () => ({ useViewportMode: () => 'desktop' }))

describe('Billboard records ValueBar', () => {
  it('keeps the fill inside its track when a caller provides a too-small maximum', () => {
    const { container } = render(<ValueBar value={5} max={1} suffix="周" />)
    const track = container.querySelector('.overflow-hidden')
    const fill = track?.firstElementChild

    expect(track).not.toBeNull()
    expect(fill).toHaveStyle({ width: '100%' })
  })

  it('uses the comparison maximum for the intended relative width', () => {
    const { container } = render(<ValueBar value={5} max={11} suffix="周" />)
    const fill = container.querySelector('.overflow-hidden > span')

    expect(fill).toHaveStyle({ width: '45%' })
  })
})
