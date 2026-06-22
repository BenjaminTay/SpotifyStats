import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { LLMTranslationSection } from '@/features/settings/components/LLMTranslationSection'
import type { LLMProfileCreatePayload } from '@/types/settings'

describe('LLMTranslationSection', () => {
  it('renders task-oriented LLM status, visible profiles, and cache maintenance', async () => {
    render(
      <LLMTranslationSection
        settings={{
          llm_enabled: true,
          llm_provider: 'deepseek',
          llm_model: 'deepseek-chat',
        }}
        onUpdate={vi.fn()}
        onClearCache={vi.fn().mockResolvedValue({ deleted_count: 0 })}
        hasLlmKey
        onFetchProfiles={vi.fn().mockResolvedValue([
          {
            id: 1,
            profile_name: 'DeepSeek 主配置',
            llm_provider: 'deepseek',
            llm_model: 'deepseek-chat',
            created_at: null,
            updated_at: null,
          },
          {
            id: 2,
            profile_name: 'OpenAI 备用',
            llm_provider: 'openai',
            llm_model: 'gpt-4o-mini',
            created_at: null,
            updated_at: null,
          },
        ])}
        onApplyProfile={vi.fn()}
        onCreateProfile={vi.fn<(_: LLMProfileCreatePayload) => Promise<{ id: number; status: string }>>()}
        onDeleteProfile={vi.fn()}
        onRefetch={vi.fn()}
      />,
    )

    expect(screen.getByText('当前模型')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'DeepSeek 模型头像' })).toHaveAttribute(
      'src',
      expect.stringContaining('image/svg+xml'),
    )
    expect(screen.getByText('DeepSeek')).toBeInTheDocument()
    expect(screen.getByText('deepseek-chat')).toBeInTheDocument()
    expect(screen.getByText('Key 已配置')).toBeInTheDocument()
    expect(screen.queryByText(/来源：/)).not.toBeInTheDocument()
    expect(await screen.findByText('DeepSeek 主配置')).toBeInTheDocument()
    expect(screen.getByText('OpenAI 备用')).toBeInTheDocument()
    expect(screen.getByText('翻译与缓存')).toBeInTheDocument()
    expect(screen.getAllByRole('switch')).toHaveLength(1)
    expect(screen.getByRole('button', { name: '清除翻译缓存' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '添加配置' }))

    expect(screen.getByRole('dialog', { name: '添加 LLM 配置档案' })).toBeInTheDocument()
    expect(screen.getByPlaceholderText('例如：DeepSeek、OpenAI GPT-4o')).toBeInTheDocument()
  })
})
