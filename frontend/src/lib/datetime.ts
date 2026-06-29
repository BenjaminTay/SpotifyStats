const SQLITE_UTC_TIMESTAMP = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?$/

export function parseBackendTimestamp(value: string | null | undefined): Date | null {
  const raw = value?.trim()
  if (!raw) return null

  const normalized = SQLITE_UTC_TIMESTAMP.test(raw)
    ? `${raw.replace(' ', 'T')}Z`
    : raw
  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatRelativeTimeZh(value: string | null | undefined, nowMs = Date.now()): string {
  const date = parseBackendTimestamp(value)
  if (!date) return ''

  const diffMs = Math.max(0, nowMs - date.getTime())
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days} 天前`
  const weeks = Math.floor(days / 7)
  if (weeks < 5) return `${weeks} 周前`
  const months = Math.floor(days / 30)
  return `${months} 个月前`
}
