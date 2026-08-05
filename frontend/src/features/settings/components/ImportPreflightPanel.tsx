import { AlertCircle, CheckCircle2, ClipboardCheck, RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { ImportFileReport, ImportPreflightResponse } from '@/types/data-import'

function fileStatusLabel(file: ImportFileReport) {
  if (file.status === 'ok') return `已发现 · ${new Intl.NumberFormat('zh-CN').format(file.record_count)} 条`
  if (file.status === 'empty') return '文件为空'
  if (file.status === 'invalid') return '解析失败'
  return file.required ? '缺少必需文件' : '未提供（可选）'
}

function duplicateRecordTotal(files: ImportFileReport[]) {
  return files.reduce((total, file) => total + (file.duplicate_record_count ?? 0), 0)
}

export function ImportPreflightPanel({
  preflight,
  loading,
  error,
  onRun,
}: {
  preflight: ImportPreflightResponse | null
  loading: boolean
  error: string | null
  onRun: () => void
}) {
  return (
    <div className="rounded-xl border border-border/70 bg-card/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[13.5px] font-semibold">
            <ClipboardCheck className="size-4" />
            导入前检查
          </div>
          <p className="mt-1 text-[12px] text-muted-foreground">只读取本地 Spotify 数据包，不会修改数据库。</p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={onRun} disabled={loading} className="gap-1.5">
          <RefreshCw className={cn('size-3.5', loading && 'animate-spin')} />
          {loading ? '检查中...' : '开始检查'}
        </Button>
      </div>

      {error && <p className="mt-3 text-[12.5px] text-red-600 dark:text-red-400">检查失败：{error}</p>}
      {preflight && (
        <>
          {preflight.blockers.length > 0 && (
            <div className="mt-3 space-y-1 rounded-lg bg-red-500/10 px-3 py-2 text-[12px] text-red-700 dark:text-red-300">
              {preflight.blockers.map((message) => <p key={message}>· {message}</p>)}
            </div>
          )}
          {(preflight.duplicate_file_groups.length > 0 || preflight.date_overlaps.length > 0 || duplicateRecordTotal(preflight.streaming_files) > 0) && (
            <div className="mt-3 space-y-1 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-800 dark:text-amber-200">
              <p className="font-medium">唯一性与日期检查</p>
              <p>完全重复文件：{preflight.duplicate_file_groups.length} 组</p>
              <p>文件内重复记录：{new Intl.NumberFormat('zh-CN').format(duplicateRecordTotal(preflight.streaming_files))} 条</p>
              <p>日期范围重叠：{preflight.date_overlaps.length} 对</p>
              {preflight.date_overlaps.slice(0, 6).map((overlap) => (
                <p key={`${overlap.left_file}:${overlap.right_file}`} className="pl-2 text-[11.5px]">
                  {overlap.left_file} ↔ {overlap.right_file}：{overlap.overlap_start} 至 {overlap.overlap_end}，共同记录 {overlap.shared_record_count} 条
                </p>
              ))}
              {preflight.date_overlaps.length > 6 && <p className="pl-2 text-[11.5px]">其余日期重叠已省略，请查看接口详情。</p>}
            </div>
          )}
          <div className="mt-3 grid gap-1.5 sm:grid-cols-2">
            {[...preflight.streaming_files, ...preflight.account_files].map((file) => (
              <div key={`${file.source_key}:${file.file_name}`} className="flex items-center justify-between gap-3 rounded-lg border border-border/50 px-3 py-2 text-[11.5px]">
                <span className="truncate">{file.label}</span>
                <span className={cn('shrink-0', file.status === 'ok' ? 'text-green-600 dark:text-green-400' : file.required ? 'text-red-600 dark:text-red-400' : 'text-muted-foreground')}>
                  {file.status === 'ok' ? <CheckCircle2 className="mr-1 inline size-3.5" /> : <AlertCircle className="mr-1 inline size-3.5" />}
                  {fileStatusLabel(file)}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
