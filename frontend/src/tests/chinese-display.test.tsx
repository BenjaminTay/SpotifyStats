import { act, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import { setChineseStyle, useDisplayName } from '@/lib/chinese'

function DisplayNameProbe({ value }: { value: string }) {
  const rendered = useDisplayName(value)
  return <MemoryRouter><a href="/music/tracks/42?title=%E6%B0%B8%E6%81%86%E7%9A%84%E4%B8%BB%E9%A2%98">{rendered}</a></MemoryRouter>
}

describe('Chinese display preference', () => {
  afterEach(() => {
    act(() => setChineseStyle('original'))
  })

  it('converts visible names in both directions', async () => {
    render(<DisplayNameProbe value="永恆的主題" />)

    act(() => setChineseStyle('simplified'))
    await waitFor(() => expect(screen.getByRole('link')).toHaveTextContent('永恒的主题'))

    act(() => setChineseStyle('traditional'))
    await waitFor(() => expect(screen.getByRole('link')).toHaveTextContent('永恆的主題'))
  })

  it('keeps navigation values raw while the visible label changes', async () => {
    render(<DisplayNameProbe value="永恆的主題" />)
    const link = screen.getByRole('link')

    act(() => setChineseStyle('simplified'))
    await waitFor(() => expect(link).toHaveTextContent('永恒的主题'))
    expect(link).toHaveAttribute('href', '/music/tracks/42?title=%E6%B0%B8%E6%81%86%E7%9A%84%E4%B8%BB%E9%A2%98')
  })
})
