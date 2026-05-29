import { useEffect, useState } from 'react'
import { GlassCard } from '@/components/shared/GlassCard'
import type { PersonalityResult } from '@/types/yearly-review'

interface PersonalityRevealProps {
  personality: PersonalityResult
}

// 7 维度的 key 和中文标签
const DIMENSION_KEYS = ['explorer', 'loyalist', 'binger', 'night_owl', 'collector', 'trend_chaser', 'globetrotter'] as const

const DIMENSION_LABELS: Record<string, string> = {
  explorer: '探索者',
  loyalist: '专一者',
  binger: '狂听者',
  night_owl: '夜猫子',
  collector: '收藏家',
  trend_chaser: '新潮派',
  globetrotter: '地球村',
}

export function PersonalityReveal({ personality }: PersonalityRevealProps) {
  const [step, setStep] = useState(0)  // 0-6: revealing dimensions, 7: show primary

  // 逐维展开动画
  useEffect(() => {
    if (step >= 7) return
    const timer = setTimeout(() => {
      setStep(s => Math.min(s + 1, 7))
    }, 300)
    return () => clearTimeout(timer)
  }, [step])

  // 简化：使用 CSS 绘制静态雷达图（避免 ECharts 动态加载复杂度）
  // 呈现 7 个维度条 + 主人格标签
  return (
    <section className="mb-12">
      <h2 className="font-serif text-[28px] font-bold tracking-[-0.5px] mb-6">听歌人格</h2>

      <GlassCard className="p-8">
        {/* 主人格揭示 */}
        <div
          className={`text-center transition-all duration-700 mb-8 ${step >= 7 ? 'opacity-100 scale-100' : 'opacity-0 scale-90'}`}
        >
          <div className="inline-block px-4 py-1.5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 font-sans text-[11px] font-bold uppercase tracking-[1.5px] mb-3">
            你的听歌人格
          </div>
          <p className="font-serif text-[40px] font-bold tracking-[-1px] mb-2">{personality.primary_label}</p>
          <p className="font-sans text-[15px] text-muted-foreground max-w-md mx-auto leading-relaxed">{personality.primary_desc}</p>
        </div>

        {/* 7 维条形图 */}
        <div className="space-y-3">
          {DIMENSION_KEYS.map((key, i) => {
            const dim = personality.dimensions[key]
            const visible = step >= i + 1
            const score = dim?.score ?? 0
            return (
              <div key={key} className="flex items-center gap-3">
                <span className="font-sans text-[12px] text-muted-foreground w-16 text-right flex-shrink-0">
                  {DIMENSION_LABELS[key]}
                </span>
                <div className="flex-1 h-6 bg-muted rounded-full overflow-hidden relative">
                  <div
                    className="h-full rounded-full transition-all duration-700 ease-out"
                    style={{
                      width: `${visible ? score : 0}%`,
                      background: `linear-gradient(90deg, ${key === personality.primary ? '#f59e0b' : '#6366f1'}, ${key === personality.primary ? '#d97706' : '#818cf8'})`,
                      opacity: visible ? 1 : 0,
                    }}
                  />
                </div>
                <span
                  className="font-sans text-[13px] font-semibold tabular-nums w-10 text-right transition-opacity duration-500"
                  style={{ opacity: visible ? 1 : 0 }}
                >
                  {score}
                </span>
              </div>
            )
          })}
        </div>
      </GlassCard>
    </section>
  )
}
