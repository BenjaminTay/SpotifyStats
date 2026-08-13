import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { AnalysisSubNav } from '../components/shared/AnalysisSubNav'

function renderSubNav(path = '/analysis/charts?period=month&period_value=2026-06') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AnalysisSubNav />
    </MemoryRouter>,
  )
}

describe('analysis sub navigation', () => {
  it('keeps all playback analysis secondary destinations in the page tab row', () => {
    renderSubNav()

    expect(screen.getByRole('tab', { name: '播放统计' })).toHaveAttribute(
      'href',
      '/analysis/stats?period=month&period_value=2026-06',
    )
    expect(screen.getByRole('tab', { name: '播放排行' })).toHaveAttribute(
      'href',
      '/analysis/charts?period=month&period_value=2026-06',
    )
    expect(screen.getByRole('tab', { name: '年度总结' })).toHaveAttribute(
      'href',
      '/yearly-review',
    )
    expect(screen.getByRole('tab', { name: '播放记录' })).toHaveAttribute(
      'href',
      '/analysis/records?period=month&period_value=2026-06',
    )
    expect(screen.getByRole('tab', { name: '音乐档案' })).toHaveAttribute('href', '/account')

    const tabNames = screen.getAllByRole('tab').map((tab) => tab.textContent)
    expect(tabNames).toEqual(['播放统计', '播放排行', '年度总结', '播放记录', '音乐档案'])
  })
})
