import type { ReportType } from '@/types/ai-insights'

export const REPORT_LABELS: Record<ReportType, string> = {
  weekly: '周报',
  monthly: '月报',
  yearly: '年度叙事',
}

export const REPORT_DESCRIPTIONS: Record<ReportType, string> = {
  weekly: '基于本周听歌数据生成的 AI 周报',
  monthly: '结合月度数据与年度人格的音乐人格分析',
  yearly: '将年度听歌总结转化为音乐故事',
}
