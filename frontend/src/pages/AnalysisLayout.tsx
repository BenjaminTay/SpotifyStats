import { Outlet } from 'react-router-dom'
import { AnalysisSubNav } from '@/components/shared/AnalysisSubNav'

export function AnalysisLayout() {
  return (
    <>
      <section className="mb-9">
        <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          Playback / Analysis
        </p>
        <h1 className="mb-3 font-serif text-[48px] font-bold leading-[1.06] tracking-[-1.2px]">
          播放分析
        </h1>
        <p className="max-w-[620px] font-sans text-[16px] leading-relaxed text-muted-foreground">
          像查个人音乐档案一样查看任意时间段里的整体统计与歌曲、专辑、艺人排行。清洗口径仍统一由设置页控制。
        </p>
      </section>

      <AnalysisSubNav />
      <Outlet />
    </>
  )
}
