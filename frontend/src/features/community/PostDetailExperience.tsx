import { useParams, Link } from 'react-router-dom'

import { useCommunityChartParams, useCommunityPost, useCommunityTrending } from '@/hooks/useCommunity'
import type { CommunityPost } from '@/types/community'
import { displayName } from '@/lib/chinese'

import { AccountAvatar } from './AccountAvatar'
import { CommunitySidebar } from './CommunitySidebar'
import { PostCard, PostContent } from './PostCard'
import { ACCOUNT_CONFIG, formatCount } from './communityData'

function parsePost(apiPost: Record<string, unknown>): CommunityPost {
  const metrics = (apiPost.metrics ?? {}) as Record<string, number>
  return {
    id: apiPost.id as string,
    account_handle: apiPost.account_handle as string,
    posted_at: apiPost.posted_at as string,
    content: apiPost.content as string,
    post_type: apiPost.post_type as string,
    images: (apiPost.images as string[]) ?? [],
    linked_entities: (apiPost.linked_entities as CommunityPost['linked_entities']) ?? [],
    tags: (apiPost.tags as string[]) ?? [],
    significance: apiPost.significance as number,
    metrics: {
      likes: metrics.likes ?? 0,
      retweets: metrics.retweets ?? 0,
      replies: metrics.replies ?? 0,
      views: metrics.views ?? 0,
    },
  }
}

export function PostDetailExperience() {
  const { postId } = useParams<{ postId: string }>()
  const chartParams = useCommunityChartParams()
  const { detail, loading, error, refetch } = useCommunityPost(postId ?? '', chartParams)
  const { trending } = useCommunityTrending(chartParams)

  if (loading) {
    return (
      <>
        <section className="mb-6">
          <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
            Community / Post
          </p>
        </section>
        <div className="max-w-[720px] mx-auto space-y-4 animate-pulse">
          <div className="h-8 w-48 bg-white/10 rounded" />
          <div className="h-4 w-full bg-white/10 rounded" />
          <div className="h-4 w-3/4 bg-white/10 rounded" />
        </div>
      </>
    )
  }

  if (error || !detail) {
    return (
      <>
        <section className="mb-6">
          <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
            Community / Post
          </p>
        </section>
        <div className="max-w-[720px] mx-auto text-center py-20">
          <p className="text-[15px] font-medium text-muted-foreground">
            {error ? 'Failed to load' : 'Post not found'}
          </p>
          {error && (
            <button
              type="button"
              className="mt-3 px-5 py-1.5 text-[14px] font-medium rounded-full bg-accent-foreground text-primary-foreground hover:opacity-85"
              onClick={() => refetch()}
            >
              Retry
            </button>
          )}
          <Link to="/community" className="mt-3 inline-block text-[15px] text-accent-foreground hover:underline">
            Back to community
          </Link>
        </div>
      </>
    )
  }

  const post = parsePost(detail.post)
  const replies = (detail.replies ?? []).map(r => parsePost(r))
  const account = ACCOUNT_CONFIG[post.account_handle]
  const m = post.metrics

  return (
    <>
      <section className="mb-6">
        <p className="mb-4 font-sans text-[11px] font-bold uppercase tracking-[1.8px] text-accent-foreground">
          Community / Post
        </p>
        <h1 className="font-serif text-[48px] font-bold leading-[1.06] tracking-[-1.2px]">
          帖子详情
        </h1>
      </section>

      {/* Two-column layout: detail + sidebar */}
      <div className="flex gap-8">
        {/* Main detail column */}
        <div className="flex-1 max-w-[720px] min-h-[70vh]">
          {/* Back button */}
          <Link
            to="/community"
            className="flex items-center justify-center w-9 h-9 rounded-full hover:bg-white/10 transition-colors -ml-1 mb-4"
            aria-label="Back"
          >
            <svg className="w-5 h-5 text-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </Link>

          {/* Account header */}
          {account && (
            <div className="flex items-center gap-3 mb-4">
              <Link to={`/community/account/${encodeURIComponent(post.account_handle)}`}>
                <AccountAvatar handle={post.account_handle} size="md" linkable />
              </Link>
              <div>
                <Link
                  to={`/community/account/${encodeURIComponent(post.account_handle)}`}
                  className="text-[15px] font-bold text-foreground hover:underline"
                >
                  {account.display_name}
                </Link>
                <p className="text-[13px] text-muted-foreground">{post.account_handle}</p>
              </div>
            </div>
          )}

          {/* Full content */}
          <div className="text-[15px] text-foreground leading-6 whitespace-pre-wrap mb-5">
            <PostContent content={post.content} linkedEntities={post.linked_entities} />
          </div>

          {/* Images — full size */}
          {post.images.length > 0 && (
            <div className={`mb-5 ${post.images.length === 1 ? '' : 'grid grid-cols-2 gap-2'}`}>
              {post.images.map((url, i) => (
                <img
                  key={i}
                  src={url}
                  alt=""
                  className={`rounded-2xl object-cover ${post.images.length === 1 ? 'max-h-96 w-full' : 'aspect-square'}`}
                />
              ))}
            </div>
          )}

          {/* Posted time */}
          <p className="text-[13px] text-muted-foreground mb-3">
            {new Date(post.posted_at).toLocaleString('zh-CN', {
              year: 'numeric', month: 'long', day: 'numeric',
              hour: '2-digit', minute: '2-digit',
            })}
          </p>

          {/* Divider */}
          <div className="border-t border-white/10 my-3" />

          {/* Metrics bar — large */}
          <div className="flex items-center gap-4 py-2 text-[13px] text-muted-foreground">
            <span><strong className="text-foreground">{formatCount(m.replies)}</strong> 回复</span>
            <span><strong className="text-foreground">{formatCount(m.retweets)}</strong> 转发</span>
            <span><strong className="text-foreground">{formatCount(m.likes)}</strong> 喜欢</span>
            <span><strong className="text-foreground">{formatCount(m.views)}</strong> 浏览</span>
          </div>

          {/* Divider */}
          <div className="border-t border-white/10 my-3" />

          {/* Linked entities section */}
          {post.linked_entities && post.linked_entities.length > 0 && (
            <div className="my-5">
              <h3 className="text-[13px] font-bold text-muted-foreground mb-3 uppercase tracking-[1px]">关联内容</h3>
              <div className="flex flex-wrap gap-2">
                {post.linked_entities.map((entity, i) => {
                  if (entity.type === 'track' && entity.id) {
                    return (
                      <Link
                        key={i}
                        to={`/music/tracks/${entity.id}`}
                        className="px-3 py-1.5 text-[13px] font-medium rounded-full bg-white/[0.06] border border-white/10 text-foreground hover:bg-white/[0.1] transition-colors"
                      >
                        {displayName(entity.name)}
                        <span className="ml-1 text-[11px] text-muted-foreground">歌曲</span>
                      </Link>
                    )
                  }
                  if (entity.type === 'artist') {
                    return (
                      <Link
                        key={i}
                        to={`/music/artists/${encodeURIComponent(entity.name)}`}
                        className="px-3 py-1.5 text-[13px] font-medium rounded-full bg-white/[0.06] border border-white/10 text-foreground hover:bg-white/[0.1] transition-colors"
                      >
                        {displayName(entity.name)}
                        <span className="ml-1 text-[11px] text-muted-foreground">艺人</span>
                      </Link>
                    )
                  }
                  return null
                })}
              </div>
            </div>
          )}

          {/* Simulated replies */}
          {replies.length > 0 && (
            <div className="mt-6">
              <h3 className="text-[15px] font-bold text-foreground mb-4">相关帖子</h3>
              <div className="space-y-0">
                {replies.map(r => (
                  <PostCard key={r.id} post={r} />
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right sidebar */}
        <aside className="w-[340px] shrink-0 hidden lg:block">
          <div className="sticky top-4 max-h-[calc(100vh-2rem)] overflow-y-auto scrollbar-thin">
            <CommunitySidebar
              posts={[]}
              meta={null}
              trendingArtists={trending?.artists}
              trendingTracks={trending?.tracks}
              latestNo1={trending?.latest_no1}
              latestDebut={trending?.latest_debut}
            />
          </div>
        </aside>
      </div>
    </>
  )
}
