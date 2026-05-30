import { GlassCard } from '@/components/shared/GlassCard'
import { Badge } from '@/components/ui/badge'
import type { ImportJob } from '@/types/settings'
import { SectionHeader, ImportProgressCard } from '@/features/settings/components/SettingsHelpers'

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
  return (
    <GlassCard className="p-6">
      <SectionHeader num={4} title="Data Import" desc="管理流媒体数据和账号数据的导入。导入过程在后台进行，可以离开页面等待。" />

      <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
        <ImportProgressCard
          title="串流数据"
          label={`当前数据库记录数：${new Intl.NumberFormat('zh-CN').format(dbRecordCount)}`}
          job={streamingJob}
          onStart={onStreamingImport}
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
        />
      </div>
    </GlassCard>
  )
}
