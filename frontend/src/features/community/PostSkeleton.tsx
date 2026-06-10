export function PostSkeleton() {
  return (
    <div className="flex gap-3 px-4 py-3 border-b border-white/10 animate-pulse">
      <div className="w-10 h-10 rounded-full bg-white/10 shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="flex gap-2">
          <div className="h-3 w-24 bg-white/10 rounded" />
          <div className="h-3 w-16 bg-white/10 rounded" />
        </div>
        <div className="space-y-1.5">
          <div className="h-3 w-full bg-white/10 rounded" />
          <div className="h-3 w-3/4 bg-white/10 rounded" />
        </div>
        <div className="flex gap-4">
          <div className="h-3 w-10 bg-white/10 rounded" />
          <div className="h-3 w-10 bg-white/10 rounded" />
          <div className="h-3 w-10 bg-white/10 rounded" />
          <div className="h-3 w-12 bg-white/10 rounded" />
        </div>
      </div>
    </div>
  )
}
