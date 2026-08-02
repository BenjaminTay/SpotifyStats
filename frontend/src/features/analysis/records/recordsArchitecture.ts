/**
 * 播放记录页唯一信息架构清单。
 *
 * 导航、模块迁移测试与浏览器验收都以此为准，避免模块在重组时缺失或重复。
 */
export const PLAYBACK_RECORD_SECTIONS = [
  {
    key: 'highlights',
    label: '高光时刻',
    modules: [
      { key: 'daily-peak', title: '单日巅峰' },
      { key: 'daily-total', title: '单日总量记录' },
      { key: 'playback-milestones', title: '播放里程碑' },
      { key: 'fastest-milestone', title: '最快里程碑' },
      { key: 'consecutive-marathon', title: '连续播放马拉松' },
    ],
  },
  {
    key: 'reigns',
    label: '个人王朝',
    modules: [
      { key: 'daily-champion', title: '每日冠军次数' },
      { key: 'monthly-reign', title: '月度统治' },
      { key: 'yearly-reign', title: '年度统治' },
      { key: 'consecutive-champion-days', title: '连续冠军天数' },
    ],
  },
  {
    key: 'longevity',
    label: '长线陪伴',
    modules: [
      { key: 'longest-streak-days', title: '最长连续播放天数' },
      { key: 'longest-span', title: '最长陪伴跨度' },
      { key: 'comeback-after-sleep', title: '沉睡后回归' },
      { key: 'most-active-month', title: '最活跃月份' },
    ],
  },
  {
    key: 'timePatterns',
    label: '时间习惯',
    modules: [
      { key: 'hourly-dominance', title: '时段统计' },
      { key: 'monthly-peak', title: '月度巅峰' },
      { key: 'late-night-trajectory', title: '深夜聆听轨迹' },
    ],
  },
  {
    key: 'discovery',
    label: '探索与品味',
    modules: [
      { key: 'discovery-day', title: '发现日' },
      { key: 'album-full-replays', title: '专辑全碟回放' },
      { key: 'feat-ranking', title: '合作曲排行' },
      { key: 'same-name-different-artist', title: '同名异曲' },
    ],
  },
] as const

export type PlaybackRecordSectionKey = typeof PLAYBACK_RECORD_SECTIONS[number]['key']

export const PLAYBACK_RECORD_MODULE_COUNT = PLAYBACK_RECORD_SECTIONS.reduce(
  (count, section) => count + section.modules.length,
  0,
)
