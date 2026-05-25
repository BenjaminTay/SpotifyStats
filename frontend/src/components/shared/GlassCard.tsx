import { cn } from '@/lib/utils'

interface GlassCardProps {
  children: React.ReactNode
  className?: string
}

export function GlassCard({ children, className }: GlassCardProps) {
  return (
    <div
      className={cn(
        'rounded-[16px] border border-border bg-card backdrop-blur-[12px] shadow-sm',
        'transition-[background,border,box-shadow] duration-400',
        'hover:bg-card hover:shadow-lg',
        className,
      )}
    >
      {children}
    </div>
  )
}
