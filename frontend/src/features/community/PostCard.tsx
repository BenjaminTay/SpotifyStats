import { useState } from 'react'
import { Link } from 'react-router-dom'

import type { CommunityPost } from '@/types/community'
import { displayName } from '@/lib/chinese'

import { AccountAvatar } from './AccountAvatar'
import { PostMetricsBar } from './PostMetrics'
import {
  ACCOUNT_CONFIG,
  buildEntityLink,
  formatAbsoluteTime,
  formatRelativeTime,
} from './communityData'

const COLLAPSE_THRESHOLD = 280

interface PostCardProps {
  post: CommunityPost
}

export function PostCard({ post }: PostCardProps) {
  const account = ACCOUNT_CONFIG[post.account_handle]
  const relativeTime = formatRelativeTime(post.posted_at)
  const absoluteTime = formatAbsoluteTime(post.posted_at)
  const images = post.images ?? []
  const multiImage = images.length > 1
  const isLong = post.content.length > COLLAPSE_THRESHOLD
  const [expanded, setExpanded] = useState(false)

  return (
    <article className="flex gap-3 py-3 cursor-pointer hover:bg-white/[0.03] transition-colors border-b border-white/10">
      {/* Left: avatar — links to account profile */}
      <Link
        to={`/community/account/${encodeURIComponent(post.account_handle)}`}
        className="shrink-0"
      >
        <AccountAvatar handle={post.account_handle} />
      </Link>

      {/* Right: content */}
      <div className="min-w-0 flex-1">
        {/* Header row */}
        <div className="flex items-center gap-1 text-[15px] leading-5 flex-wrap">
          <Link
            to={`/community/account/${encodeURIComponent(post.account_handle)}`}
            className="font-bold text-foreground hover:underline truncate"
          >
            {account?.display_name ?? post.account_handle}
          </Link>
          <span className="text-muted-foreground truncate">{post.account_handle}</span>
          <span className="text-muted-foreground">·</span>
          <time
            dateTime={post.posted_at}
            title={absoluteTime}
            className="text-muted-foreground whitespace-nowrap hover:underline"
          >
            {relativeTime}
          </time>
        </div>

        {/* Body text */}
        <div className="mt-0.5 text-[15px] leading-5 text-foreground whitespace-pre-wrap break-words">
          {isLong && !expanded ? (
            <>
              <PostContent
                content={post.content.slice(0, COLLAPSE_THRESHOLD) + '…'}
                linkedEntities={post.linked_entities}
              />
              {' '}
              <button
                type="button"
                className="text-accent-foreground hover:underline whitespace-nowrap"
                onClick={(e) => { e.stopPropagation(); setExpanded(true) }}
              >
                展开
              </button>
            </>
          ) : (
            <>
              <PostContent content={post.content} linkedEntities={post.linked_entities} />
              {isLong && (
                <>
                  {' '}
                  <button
                    type="button"
                    className="text-accent-foreground hover:underline whitespace-nowrap"
                    onClick={(e) => { e.stopPropagation(); setExpanded(false) }}
                  >
                    收起
                  </button>
                </>
              )}
            </>
          )}
        </div>

        {/* Images — single cover or multi-cover grid */}
        {images.length > 0 && !multiImage && (
          <div className="mt-3 rounded-2xl border border-white/15 overflow-hidden w-52 h-52">
            <img
              src={images[0]}
              alt=""
              className="w-full h-full object-cover"
              loading="lazy"
            />
          </div>
        )}
        {multiImage && (
          <div className="mt-3 grid grid-cols-2 gap-0.5 rounded-2xl border border-white/15 overflow-hidden max-w-[424px]">
            {images.slice(0, 4).map((url, i) => (
              <div key={i} className="aspect-square overflow-hidden">
                <img
                  src={url}
                  alt=""
                  className="w-full h-full object-cover"
                  loading="lazy"
                />
              </div>
            ))}
          </div>
        )}

        {/* Metrics bar */}
        <PostMetricsBar metrics={post.metrics} />
      </div>
    </article>
  )
}

/** Renders post content with linked entity names as clickable <Link> elements. */
function PostContent({ content, linkedEntities }: { content: string; linkedEntities?: CommunityPost['linked_entities'] }) {
  if (!linkedEntities || linkedEntities.length === 0) {
    return <span>{displayName(content)}</span>
  }

  const linkMap = new Map<string, string>()
  for (const entity of linkedEntities) {
    const link = buildEntityLink(entity)
    if (link) linkMap.set(entity.name, link)
  }
  if (linkMap.size === 0) return <span>{displayName(content)}</span>

  const sorted = [...linkMap.keys()].sort((a, b) => b.length - a.length)
  const escaped = sorted.map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const pattern = new RegExp(`(${escaped.join('|')})`, 'g')
  const parts = content.split(pattern)

  return (
    <span>
      {parts.map((part, i) => {
        const href = linkMap.get(part)
        if (href) {
          return (
            <Link key={i} to={href} className="text-accent-foreground hover:underline">
              {displayName(part)}
            </Link>
          )
        }
        return <span key={i}>{displayName(part)}</span>
      })}
    </span>
  )
}
