import { GlassCard } from '@/components/shared/GlassCard'
import { Badge } from '@/components/ui/badge'
import { CheckCircle2 } from 'lucide-react'
import type { ImportJob } from '@/types/settings'
import { CollapsibleSection, ImportProgressCard } from '@/features/settings/components/SettingsHelpers'

export function DataImportSection({
  dbRecordCount,
  accountImported,
  streamingJob,
  accountJob,
  onStreamingImport,
  onAccountImport,
}: {
  dbRecordCount: number
  accountImported: boolean
  streamingJob: ImportJob | null
  accountJob: ImportJob | null
  onStreamingImport: () => void
  onAccountImport: () => void
}) {
  const imported = dbRecordCount > 0 && accountImported

  return (
    <GlassCard className="p-6">
      <CollapsibleSection
        num={2}
        title="数据导入"
        desc="管理流媒体数据和账号数据的导入。导入过程在后台进行，可以离开页面等待。"
        defaultOpen={!imported}
        summary={
          imported ? (
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle2 className="size-3.5 text-green-600 dark:text-green-400" />
              流媒体数据已导入 ({new Intl.NumberFormat('zh-CN').format(dbRecordCount)} 条) · 账号数据已导入
            </span>
          ) : undefined
        }
      >
      <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
        <ImportProgressCard
          title="串流数据"
          label={`当前数据库记录数：${new Intl.NumberFormat('zh-CN').format(dbRecordCount)}`}
          job={streamingJob}
          onStart={onStreamingImport}
          reimportLabel="重新导入（将覆盖现有数据）"
        />
        <ImportProgressCard
          title="账号数据"
          label="导入 Spotify 账号数据包中的搜索历史、收藏、播客等信息"
          job={accountJob}
          onStart={onAccountImport}
          statusBadge={
            accountImported ? (
              <Badge variant="default" className="text-[11px]">已导入</Badge>
            ) : (
              <Badge variant="secondary" className="text-[11px]">未导入</Badge>
            )
          }
          helpLink={{
            text: '如何获取 Spotify 数据包？',
            href: 'https://www.spotify.com/account/privacy/',
          }}
        />
      </div>
      </CollapsibleSection>
    </GlassCard>
  )
}
