import type { AiReportSection } from '@/types/ai-tasks'

import { AiMarkdown } from './AiMarkdown'

function text(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

export function ProgressiveReportSections({ sections }: { sections: AiReportSection[] }) {
  const readable = sections.filter((item) => item.status === 'validated' && item.section)
  if (readable.length === 0) return null

  return (
    <section
      className="space-y-4 rounded-2xl border border-border bg-card/45 p-4 sm:p-5"
      aria-label="年度报告已验证章节"
      aria-live="polite"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-foreground">已完成 {readable.length}/6 章</p>
          <p className="mt-1 text-xs text-muted-foreground">这些章节已通过检查并已保存。</p>
        </div>
      </div>
      <div className="space-y-5">
        {readable.map((item) => {
          const section = item.section ?? {}
          return (
            <article key={`${item.section_id}:${item.section_version}`} className="space-y-2">
              <h3 className="text-base font-semibold text-foreground">
                {text(section.heading) || `第 ${item.section_order + 1} 章`}
              </h3>
              {text(section.deck) && <p className="text-sm text-muted-foreground">{text(section.deck)}</p>}
              <AiMarkdown>{text(section.prose)}</AiMarkdown>
              {item.source_kind === 'deterministic' && (
                <p className="text-xs text-muted-foreground">本章由已验证的本地数据补齐。</p>
              )}
            </article>
          )
        })}
      </div>
    </section>
  )
}
