import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AITaskProgress } from '@/features/ai-tasks/AITaskProgress'
import { AIToolTrace } from '@/features/ai-tasks/AIToolTrace'

describe('AITaskProgress', () => {
  it('renders the current task stage, message, percentage, and completed events', () => {
    render(
      <AITaskProgress
        task={{
          found: true,
          task_id: 'task-1',
          task_type: 'ai_report_weekly',
          status: 'running',
          stage: 'calling_llm',
          progress_pct: 0.6,
          message: 'AI 正在生成周报',
          result: null,
          error: null,
          created_at: '2026-06-28T00:00:00',
          updated_at: '2026-06-28T00:00:01',
        }}
        events={[
          {
            event_id: 1,
            task_id: 'task-1',
            event_type: 'stage_completed',
            stage: 'gathering_local_data',
            message: '已汇总播放数据',
            payload: null,
            created_at: '2026-06-28T00:00:00',
          },
        ]}
      />,
    )

    expect(screen.getByText('AI 任务进度')).toBeInTheDocument()
    expect(screen.getByText('调用 LLM 生成')).toBeInTheDocument()
    expect(screen.getByText('AI 正在生成周报')).toBeInTheDocument()
    expect(screen.getByText('60%')).toBeInTheDocument()
    expect(screen.getByText('已汇总播放数据')).toBeInTheDocument()
  })

  it('renders visual yearly artifact stages with readable labels', () => {
    render(
      <AITaskProgress
        task={{
          found: true,
          task_id: 'task-visual-yearly',
          task_type: 'ai_report_yearly',
          status: 'running',
          stage: 'building_chart_data',
          progress_pct: 72,
          message: '正在准备年度图表数据',
          result: null,
          error: null,
          created_at: '2026-07-04T00:00:00',
          updated_at: '2026-07-04T00:00:01',
        }}
        events={[]}
      />,
    )

    expect(screen.getByText('准备图表数据')).toBeInTheDocument()
    expect(screen.getByText('72%')).toBeInTheDocument()
  })

  it('renders agent synthesis writer stage with readable label', () => {
    render(
      <AITaskProgress
        task={{
          found: true,
          task_id: 'task-synthesis-yearly',
          task_type: 'ai_report_yearly',
          status: 'running',
          stage: 'generating_report_prose',
          progress_pct: 0.75,
          message: '正在撰写年度报告',
          result: null,
          error: null,
          created_at: '2026-07-05T00:00:00',
          updated_at: '2026-07-05T00:00:01',
        }}
        events={[
          {
            event_id: 1,
            task_id: 'task-synthesis-yearly',
            event_type: 'stage_started',
            stage: 'building_chart_data',
            message: '正在准备图表数据',
            payload: null,
            created_at: '2026-07-05T00:00:00',
          },
        ]}
      />,
    )

    expect(screen.getByText('撰写年度报告')).toBeInTheDocument()
    expect(screen.getByText('正在准备图表数据')).toBeInTheDocument()
    expect(screen.getByText('75%')).toBeInTheDocument()
  })

  it('renders task errors when the task fails', () => {
    render(
      <AITaskProgress
        task={{
          found: true,
          status: 'error',
          stage: 'failed',
          progress_pct: 0.4,
          message: '生成失败',
          error: 'LLM 服务不可用',
        }}
        events={[]}
      />,
    )

    expect(screen.getByText('生成失败')).toBeInTheDocument()
    expect(screen.getByText('LLM 服务不可用')).toBeInTheDocument()
  })
})

describe('AIToolTrace', () => {
  it('renders readable tool evidence', () => {
    render(
      <AIToolTrace
        toolCalls={[
          {
            tool_call_id: 1,
            task_id: 'task-1',
            tool_name: 'analysis_charts',
            status: 'done',
            params_summary: '2026 artist plays top 10',
            result_summary: 'Artist A ranked #1',
            source_range: '2026-01-01 to 2026-12-31',
            error: null,
            started_at: '2026-06-28T00:00:00',
            completed_at: '2026-06-28T00:00:01',
          },
        ]}
      />,
    )

    expect(screen.getByText('数据查询轨迹')).toBeInTheDocument()
    expect(screen.getByText('排行榜')).toBeInTheDocument()
    expect(screen.getByText('done')).toBeInTheDocument()
    expect(screen.getByText('2026 artist plays top 10')).toBeInTheDocument()
    expect(screen.getByText('Artist A ranked #1')).toBeInTheDocument()
    expect(screen.getByText('2026-01-01 to 2026-12-31')).toBeInTheDocument()
  })
})
