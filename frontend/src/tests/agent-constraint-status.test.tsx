import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AgentConstraintStatus } from '@/features/ai-insights/AgentConstraintStatus'

describe('AgentConstraintStatus', () => {
  it('renders backend session state and explicit steering consumption state', () => {
    render(
      <AgentConstraintStatus
        task={{
          found: true,
          status: 'running',
          result: null,
        }}
        events={[
          {
            event_id: 2,
            task_id: 'task-1',
            event_type: 'session_state_updated',
            stage: 'agent_deciding',
            message: '分析约束已更新',
            payload: {
              inbox_id: 9,
              state: {
                time_range: {
                  label: 'this_year',
                  start_date: '2026-01-01',
                  end_date: '2026-08-31',
                },
                entities: [{ name: 'Taylor Swift' }, { name: 'Olivia Rodrigo' }],
                metrics: ['plays', 'hours'],
                excluded_dimensions: ['个人 Billboard'],
              },
            },
            created_at: '2026-08-31T00:00:00Z',
          },
          {
            event_id: 3,
            task_id: 'task-1',
            event_type: 'session_input_consumed',
            stage: 'agent_deciding',
            message: '补充要求已读取',
            payload: { inbox_id: 9, input_type: 'steer', semantic_action: 'replace_constraints' },
            created_at: '2026-08-31T00:00:00Z',
          },
        ]}
        steeringInputs={[{ inboxId: 9, content: '只看今年，不要 Billboard', status: 'pending' }]}
      />,
    )

    expect(screen.getByRole('region', { name: '当前分析约束' })).toBeInTheDocument()
    expect(screen.getByText(/今年 · 2026-01-01 至 2026-08-31/)).toBeInTheDocument()
    expect(screen.getByText(/Taylor Swift、Olivia Rodrigo/)).toBeInTheDocument()
    expect(screen.getByText(/播放次数、收听时长/)).toBeInTheDocument()
    expect(screen.getByText(/个人 Billboard/)).toBeInTheDocument()
    expect(screen.getByText('只看今年，不要 Billboard')).toBeInTheDocument()
    expect(screen.getByText('已应用到当前分析')).toBeInTheDocument()
  })

  it('stays hidden for legacy task payloads without constraints or steering receipts', () => {
    const { container } = render(
      <AgentConstraintStatus
        task={{ found: true, status: 'running', result: null }}
        events={[]}
        steeringInputs={[]}
      />,
    )

    expect(container).toBeEmptyDOMElement()
  })

  it('does not claim a pending steering input was applied', () => {
    render(
      <AgentConstraintStatus
        task={{ found: true, status: 'running', result: null }}
        events={[]}
        steeringInputs={[{ inboxId: 3, content: '再比较播放时长', status: 'pending' }]}
      />,
    )

    expect(screen.getByText('已接收，等待 Agent 读取')).toBeInTheDocument()
    expect(screen.queryByText('已应用到当前分析')).not.toBeInTheDocument()
  })
})
