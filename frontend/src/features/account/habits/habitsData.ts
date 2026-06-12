import type { SearchData, VideoData } from '@/types/account'

export interface PersonalityResult {
  type: string
  description: string
  metrics: { label: string; value: string; detail: string }[]
}

function fmtPct(n: number, total: number): string {
  if (total === 0) return '0%'
  return `${Math.round((n / total) * 100)}%`
}

function safeDiv(a: number, b: number): number {
  return b === 0 ? 0 : a / b
}

export function inferPersonality(
  search: SearchData,
  video: VideoData,
): PersonalityResult {
  let lateNightSearches = 0
  let totalSearches = 0
  if (search.available && !search.empty && search.heatmap?.z) {
    const { z } = search.heatmap
    for (let dow = 0; dow < z.length; dow++) {
      for (let h = 0; h < (z[dow]?.length ?? 0); h++) {
        const v = z[dow][h] ?? 0
        totalSearches += v
        if (h >= 0 && h <= 5) lateNightSearches += v
      }
    }
  }
  const lateNightPct = safeDiv(lateNightSearches, totalSearches)

  let preciseSearches = 0
  let allIntentSearches = 0
  if (search.available && !search.empty && search.intent_dist) {
    for (const item of search.intent_dist) {
      allIntentSearches += item.count
      if (item.intent === '艺人搜索' || item.intent === '曲目搜索') {
        preciseSearches += item.count
      }
    }
  }
  const precisionPct = safeDiv(preciseSearches, allIntentSearches)

  const videoTotal =
    video.available && !video.empty
      ? video.total_video_plays + video.total_audio_plays
      : 0
  const videoPct = safeDiv(
    video.available && !video.empty ? video.total_video_plays : 0,
    videoTotal,
  )

  if (lateNightPct > 0.2 && precisionPct > 0.55) {
    return {
      type: '午夜诗人',
      description: '深夜是你与音乐灵魂共振的时刻，每一次精准搜索都是一场静谧的探险。',
      metrics: [
        { label: '深夜活跃度', value: fmtPct(lateNightSearches, totalSearches), detail: '夜间 0-5 时搜索占比' },
        { label: '搜索精准度', value: fmtPct(preciseSearches, allIntentSearches), detail: '艺人/曲目直接搜索占比' },
        { label: '多媒体指数', value: fmtPct(video.total_video_plays ?? 0, videoTotal), detail: '视频播放占比' },
      ],
    }
  }
  if (precisionPct > 0.6) {
    return {
      type: '精准猎手',
      description: '你从不漫无目的地搜索，每一次查询都直指目标，音乐品味清晰而坚定。',
      metrics: [
        { label: '搜索精准度', value: fmtPct(preciseSearches, allIntentSearches), detail: '艺人/曲目直接搜索占比' },
        { label: '深夜活跃度', value: fmtPct(lateNightSearches, totalSearches), detail: '夜间 0-5 时搜索占比' },
        { label: '多媒体指数', value: fmtPct(video.total_video_plays ?? 0, videoTotal), detail: '视频播放占比' },
      ],
    }
  }
  if (videoPct > 0.3 && (video.available && !video.empty)) {
    return {
      type: '多维旅人',
      description: '你游走于音频与视频之间，用双眼和双耳共同感受音乐的多维魅力。',
      metrics: [
        { label: '多媒体指数', value: fmtPct(video.total_video_plays ?? 0, videoTotal), detail: '视频播放占比' },
        { label: '搜索精准度', value: fmtPct(preciseSearches, allIntentSearches), detail: '艺人/曲目直接搜索占比' },
        { label: '深夜活跃度', value: fmtPct(lateNightSearches, totalSearches), detail: '夜间 0-5 时搜索占比' },
      ],
    }
  }
  if (precisionPct < 0.4) {
    return {
      type: '随性漫游者',
      description: '你喜欢随意浏览探索，享受音乐发现的偶然与惊喜，不设限的搜索带来无限灵感。',
      metrics: [
        { label: '搜索精准度', value: fmtPct(preciseSearches, allIntentSearches), detail: '艺人/曲目直接搜索占比' },
        { label: '深夜活跃度', value: fmtPct(lateNightSearches, totalSearches), detail: '夜间 0-5 时搜索占比' },
        { label: '多媒体指数', value: fmtPct(video.total_video_plays ?? 0, videoTotal), detail: '视频播放占比' },
      ],
    }
  }
  return {
    type: '均衡鉴赏家',
    description: '你的音乐习惯平衡而多元，既是理性的探索者，也是感性的聆听者。',
    metrics: [
      { label: '搜索精准度', value: fmtPct(preciseSearches, allIntentSearches), detail: '艺人/曲目直接搜索占比' },
      { label: '深夜活跃度', value: fmtPct(lateNightSearches, totalSearches), detail: '夜间 0-5 时搜索占比' },
      { label: '多媒体指数', value: fmtPct(video.total_video_plays ?? 0, videoTotal), detail: '视频播放占比' },
    ],
  }
}

export function getMostActiveDay(heatmap: { z: number[][]; y: string[] } | undefined): {
  dayLabel: string
  hours: number[]
  total: number
} | null {
  if (!heatmap?.z || !heatmap.y) return null
  const { z, y } = heatmap
  let maxSum = 0
  let maxIdx = 0
  for (let i = 0; i < z.length; i++) {
    const sum = (z[i] ?? []).reduce((a, b) => a + (b ?? 0), 0)
    if (sum > maxSum) {
      maxSum = sum
      maxIdx = i
    }
  }
  return {
    dayLabel: y[maxIdx] ?? `DOW ${maxIdx}`,
    hours: z[maxIdx] ?? [],
    total: maxSum,
  }
}

export function getIntentColors(): Record<string, string> {
  return {
    '艺人搜索': 'bg-amber-500',
    '曲目搜索': 'bg-sky-500',
    '一般搜索': 'bg-slate-400',
  }
}

export function getIntentLabels(): Record<string, string> {
  return {
    '艺人搜索': '艺人',
    '曲目搜索': '曲目',
    '一般搜索': '一般',
  }
}
