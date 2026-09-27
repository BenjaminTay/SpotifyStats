import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ProgressiveReportSections } from '@/features/ai-insights/ProgressiveReportSections'

describe('ProgressiveReportSections', () => {
  it('shows only reviewed sections and labels deterministic completion', () => {
    render(<ProgressiveReportSections sections={[
      {
        task_id: 'task-1',
        generation: 1,
        section_id: 'opening',
        section_order: 0,
        section_version: 1,
        status: 'validated',
        source_kind: 'deterministic',
        section: { heading: '开场', prose: '已审核正文' },
        attempt_count: 2,
        updated_at: '2026-09-22 10:00:00',
      },
      {
        task_id: 'task-1',
        generation: 1,
        section_id: 'hidden',
        section_order: 1,
        section_version: 1,
        status: 'invalidated',
        source_kind: 'model',
        section: { heading: '不应展示', prose: '未通过' },
        attempt_count: 1,
        updated_at: '2026-09-22 10:01:00',
      },
    ]} />)

    expect(screen.getByText('已完成 1/6 章')).toBeInTheDocument()
    expect(screen.getByText('开场')).toBeInTheDocument()
    expect(screen.getByText('本章由已验证的本地数据补齐。')).toBeInTheDocument()
    expect(screen.queryByText('不应展示')).not.toBeInTheDocument()
  })
})
