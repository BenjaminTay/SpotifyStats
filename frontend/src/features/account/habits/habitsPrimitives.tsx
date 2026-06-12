import { Crown, Medal, Hash } from 'lucide-react'

export function fmtInt(n: number): string {
  return n.toLocaleString('zh-CN')
}

export function fmtHours(h: number): string {
  if (h < 1) return `${Math.round(h * 60)} 分钟`
  return `${h.toFixed(1)} 小时`
}

export const medalBorder: Record<number, string> = {
  1: 'border-amber-400 shadow-[0_0_20px_rgba(245,158,11,0.15)]',
  2: 'border-slate-300 shadow-[0_0_14px_rgba(148,163,184,0.12)]',
  3: 'border-orange-400/60 shadow-[0_0_10px_rgba(251,146,60,0.10)]',
}

export const medalBadge: Record<number, string> = {
  1: 'bg-amber-500 text-white',
  2: 'bg-slate-300 text-slate-800',
  3: 'bg-orange-400/80 text-white',
}

export const medalIcon: Record<number, React.ReactNode> = {
  1: <Crown className="h-4 w-4" />,
  2: <Medal className="h-4 w-4" />,
  3: <Medal className="h-4 w-4" />,
}

export function UnavailableBlock({ title }: { title: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-muted-foreground">
      <div className="mb-2 rounded-full border border-border p-3">
        <Hash className="h-5 w-5" />
      </div>
      <p className="font-sans text-sm">{title}数据不可用</p>
    </div>
  )
}
