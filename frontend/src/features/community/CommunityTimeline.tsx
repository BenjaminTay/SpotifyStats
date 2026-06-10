import { useEffect, useRef } from 'react'

import type { CommunityPost } from '@/types/community'

import { PostCard } from './PostCard'
import { PostSkeleton } from './PostSkeleton'

interface CommunityTimelineProps {
  posts: CommunityPost[]
  loading: boolean
  hasMore: boolean
  onLoadMore: () => void
}

export function CommunityTimeline({ posts, loading, hasMore, onLoadMore }: CommunityTimelineProps) {
  const sentinelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return

    const observer = new IntersectionObserver(
      entries => {
        if (entries[0]?.isIntersecting && hasMore && !loading) {
          onLoadMore()
        }
      },
      { rootMargin: '400px' },
    )

    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [hasMore, loading, onLoadMore])

  if (!loading && posts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground px-4">
        <svg className="w-12 h-12 mb-3 opacity-40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
        <p className="text-[15px] font-medium">No posts yet</p>
        <p className="text-[13px] mt-1 opacity-60">Adjust your filters or check back later</p>
      </div>
    )
  }

  return (
    <div>
      {posts.map(post => (
        <PostCard key={post.id} post={post} />
      ))}

      {loading && (
        <div>
          {Array.from({ length: 3 }).map((_, i) => (
            <PostSkeleton key={i} />
          ))}
        </div>
      )}

      <div ref={sentinelRef} className="h-1" />

      {!hasMore && posts.length > 0 && (
        <div className="py-10 text-center">
          <span className="text-[13px] text-muted-foreground">No more posts</span>
        </div>
      )}
    </div>
  )
}
