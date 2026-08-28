import { memo, useCallback, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import type { CommunityPost } from '@/types/community'
import { displayName, useChineseTextVersion } from '@/lib/chinese'

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

function PostCardInner({ post }: PostCardProps) {
  useChineseTextVersion()
  const navigate = useNavigate()
  const account = ACCOUNT_CONFIG[post.account_handle]
  const relativeTime = formatRelativeTime(post.posted_at)
  const absoluteTime = formatAbsoluteTime(post.posted_at)
  const images = post.images ?? []
  const multiImage = images.length > 1
  const isLong = post.content.length > COLLAPSE_THRESHOLD
  const [expanded, setExpanded] = useState(false)

  const goToDetail = useCallback(() => {
    navigate(`/community/post/${post.id}`)
  }, [navigate, post.id])

  return (
    <article className="mobile-community-post flex gap-3 py-3 border-b border-white/10">
      {/* Left: avatar — links to account profile */}
      <Link
        to={`/community/account/${encodeURIComponent(post.account_handle)}`}
        className="shrink-0 self-start"
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
        <div
          className="mt-0.5 cursor-pointer text-[15px] leading-5 text-foreground whitespace-pre-wrap break-words"
          onClick={goToDetail}
        >
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
          <div
            className="mt-3 rounded-2xl border border-white/15 overflow-hidden w-40 h-40 cursor-pointer"
            onClick={goToDetail}
          >
            <img
              src={images[0]}
              alt=""
              className="w-full h-full object-cover"
              loading="lazy"
            />
          </div>
        )}
        {multiImage && (
          <div
            className="mt-3 grid w-full max-w-[320px] grid-cols-2 gap-0.5 rounded-2xl border border-white/15 overflow-hidden cursor-pointer"
            onClick={goToDetail}
          >
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
        <PostMetricsBar metrics={post.metrics} onNavigate={goToDetail} />
      </div>
    </article>
  )
}

/** Renders post content with linked entity names as clickable <Link> elements. */
export function PostContent({ content, linkedEntities }: { content: string; linkedEntities?: CommunityPost['linked_entities'] }) {
  useChineseTextVersion()
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
            <Link
              key={i}
              to={href}
              className="text-accent-foreground hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {displayName(part)}
            </Link>
          )
        }
        return <span key={i}>{displayName(part)}</span>
      })}
    </span>
  )
}

export const PostCard = memo(PostCardInner)
