import { Link } from 'react-router-dom'
import { GlassCard } from '@/components/shared/GlassCard'

function NotFoundPage() {
  return (
    <section className="flex items-center justify-center py-20">
      <GlassCard className="max-w-md text-center p-10">
        <p className="font-serif text-[80px] font-bold leading-none mb-2 text-accent-foreground/40">
          404
        </p>
        <p className="font-serif text-[28px] font-bold mb-3">页面未找到</p>
        <p className="font-sans text-[14px] text-muted-foreground mb-6">
          你访问的页面不存在或已被移除。
        </p>
        <Link
          to="/"
          className="inline-flex items-center gap-2 rounded-full bg-accent-foreground px-6 py-2.5 font-sans text-[14px] font-medium text-accent-foreground-foreground transition-opacity hover:opacity-90"
        >
          返回首页
        </Link>
      </GlassCard>
    </section>
  )
}

export { NotFoundPage }
