import type { PostMetrics as PostMetricsType } from '@/types/community'
import { formatCount } from './communityData'

interface PostMetricsBarProps {
  metrics: PostMetricsType
  onNavigate?: () => void
}

export function PostMetricsBar({ metrics, onNavigate }: PostMetricsBarProps) {
  return (
    <div className="mt-2 flex items-center gap-5 text-xs text-muted-foreground">
      <MetricButton icon={ReplyIcon} label="replies" count={metrics.replies} onNavigate={onNavigate} />
      <MetricButton icon={RetweetIcon} label="retweets" count={metrics.retweets} onNavigate={onNavigate} />
      <MetricButton icon={HeartIcon} label="likes" count={metrics.likes} onNavigate={onNavigate} />
      <MetricButton icon={ViewIcon} label="views" count={metrics.views} onNavigate={onNavigate} />
    </div>
  )
}

function MetricButton({ icon: Icon, label, count, onNavigate }: { icon: React.ComponentType<{ className?: string }>; label: string; count: number; onNavigate?: () => void }) {
  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); onNavigate?.() }}
      className="group flex items-center gap-1 hover:text-foreground transition-colors"
      title={`${formatCount(count)} ${label}`}
      aria-label={`${formatCount(count)} ${label}`}
    >
      <Icon className="w-4 h-4 group-hover:scale-110 transition-transform" />
      <span className="tabular-nums">{formatCount(count)}</span>
    </button>
  )
}

function ReplyIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function RetweetIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="17 1 21 5 17 9" />
      <path d="M3 11V9a4 4 0 0 1 4-4h14" />
      <polyline points="7 23 3 19 7 15" />
      <path d="M21 13v2a4 4 0 0 1-4 4H3" />
    </svg>
  )
}

function HeartIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
    </svg>
  )
}

function ViewIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}
