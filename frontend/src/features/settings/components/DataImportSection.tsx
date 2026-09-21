import { useState } from 'react'
import { CheckCircle2 } from 'lucide-react'

import { GlassCard } from '@/components/shared/GlassCard'
import { CollapsibleSection } from '@/features/settings/components/SettingsHelpers'
import { DataImportWorkspace } from '@/features/settings/components/DataImportWorkspace'
import { DataHealthSummary } from '@/features/settings/components/DataHealthSummary'
import { useDataImportHealth } from '@/hooks/useDataImportHealth'
import { useViewportMode } from '@/hooks/useViewportMode'

export function DataImportSection({
  dbRecordCount,
  accountImported,
}: {
  dbRecordCount: number
  accountImported: boolean
}) {
  const imported = dbRecordCount > 0
  const [open, setOpen] = useState(!imported)
  const viewport = useViewportMode()
  const presentation = viewport === 'compact' ? 'compact' : 'desktop'
  const dataHealth = useDataImportHealth(open)

  return (
    <div id="data-import" className="scroll-mt-24">
      <GlassCard className="p-6">
        <CollapsibleSection
          num={2}
          title="数据导入"
          desc="选择数据包，核对绑定批次与活动基线的计划，再执行并查看持久运行结果。"
          defaultOpen={!imported}
          onOpenChange={setOpen}
          summary={imported ? (
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle2 className="size-3.5 text-green-600 dark:text-green-400" />
              已有 {new Intl.NumberFormat('zh-CN').format(dbRecordCount)} 条播放记录 · 运行历史可追踪
            </span>
          ) : undefined}
        >
          {open && (
            <div className="space-y-4">
              <DataHealthSummary
                health={dataHealth.health}
                loading={dataHealth.healthLoading}
                error={dataHealth.healthError}
                onRefresh={() => { void dataHealth.refetchHealth() }}
                preview={dataHealth.cleanupPreview}
                previewLoading={dataHealth.cleanupPreviewLoading}
                previewError={dataHealth.cleanupPreviewError}
                onPreview={() => { void dataHealth.runCleanupPreview() }}
              />
              <DataImportWorkspace
                presentation={presentation}
                dbRecordCount={dbRecordCount}
                accountImported={accountImported}
              />
            </div>
          )}
        </CollapsibleSection>
      </GlassCard>
    </div>
  )
}
