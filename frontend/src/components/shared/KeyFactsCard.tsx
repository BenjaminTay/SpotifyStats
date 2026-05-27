import { type LucideIcon, Info, CalendarDays, Cake, Zap, Disc, Music, Music2, Building2, Users, Tag, Clock, Globe, Trophy, User } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { KeyFact } from '@/types/billboard'

const LABEL_ICONS: Record<string, LucideIcon> = {
  '出生日期': CalendarDays, '出生': Cake, '出道': Zap, '首演': Zap,
  '代表专辑': Disc, '专辑': Disc, '代表作': Music, '代表曲': Music,
  '风格': Music2, '流派': Music2, '厂牌': Building2, '唱片公司': Building2,
  '成员': Users, '类型': Tag, '发行日期': CalendarDays, '发行': CalendarDays,
  '时长': Clock, '制作人': Info, '本名': User, '国籍': Globe, '粉丝': Users,
}

// Color classes for different fact categories
const CATEGORY_COLORS: Record<string, string> = {
  '本名': 'text-rose-500 dark:text-rose-400 bg-rose-500/10',
  '出生': 'text-sky-500 dark:text-sky-400 bg-sky-500/10',
  '出道': 'text-amber-500 dark:text-amber-400 bg-amber-500/10',
  '厂牌': 'text-violet-500 dark:text-violet-400 bg-violet-500/10',
  '代表': 'text-emerald-500 dark:text-emerald-400 bg-emerald-500/10',
  '风格': 'text-fuchsia-500 dark:text-fuchsia-400 bg-fuchsia-500/10',
  '成员': 'text-cyan-500 dark:text-cyan-400 bg-cyan-500/10',
  '粉丝': 'text-pink-500 dark:text-pink-400 bg-pink-500/10',
  '最高': 'text-amber-500 dark:text-amber-400 bg-amber-500/10',
}

function iconForLabel(label: string): LucideIcon {
  for (const [key, icon] of Object.entries(LABEL_ICONS)) {
    if (label.includes(key)) return icon
  }
  return Info
}

function colorForLabel(label: string): string {
  for (const [key, cls] of Object.entries(CATEGORY_COLORS)) {
    if (label.includes(key)) return cls
  }
  return 'text-muted-foreground bg-muted'
}

interface KeyFactsCardProps {
  facts: KeyFact[]
  className?: string
}

export function KeyFactsCard({ facts, className }: KeyFactsCardProps) {
  if (!facts.length) return null
  return (
    <div className={cn('rounded-xl bg-muted/30 p-5', className)}>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {facts.map((fact, i) => {
          const Icon = iconForLabel(fact.label)
          const colorCls = colorForLabel(fact.label)
          return (
            <div key={i} className="group flex items-start gap-3 rounded-lg p-2 -mx-2 transition-colors hover:bg-muted/40">
              <div className={cn(
                'mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg',
                colorCls.split(' ').slice(1).join(' ') || 'bg-muted text-muted-foreground',
              )}>
                <Icon className={cn('h-3.5 w-3.5', colorCls.split(' ')[0])} />
              </div>
              <div className="min-w-0">
                <span className="font-sans text-[10px] font-bold uppercase tracking-[1px] text-muted-foreground">
                  {fact.label}
                </span>
                <p className="font-sans text-[13px] font-medium leading-snug text-foreground/85">{fact.value}</p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
