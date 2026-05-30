import { GlassCard } from '@/components/shared/GlassCard'

export function NotAvailable() {
  return (
    <GlassCard className="p-12">
      <div className="flex flex-col items-center justify-center space-y-3 text-center">
        <p className="font-serif text-xl font-semibold">暂无收藏数据</p>
        <p className="font-sans text-sm text-muted-foreground">
          你的 Spotify 账号数据中尚未包含收藏记录。请导入账号数据包后查看收藏分析。
        </p>
      </div>
    </GlassCard>
  )
}
