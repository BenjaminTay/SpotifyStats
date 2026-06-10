/** Community feed types — simulated X-style music news timeline. */

export interface PostMetrics {
  likes: number
  retweets: number
  replies: number
  views: number
}

export interface LinkedEntity {
  type: 'track' | 'artist' | 'album'
  id?: string | number
  name: string
}

export interface CommunityPost {
  id: string
  account_handle: string
  posted_at: string
  content: string
  post_type: string
  attached_list?: Array<Record<string, unknown>> | null
  linked_entities?: LinkedEntity[]
  images: string[]
  metrics: PostMetrics
  tags: string[]
  significance: number
}

export interface AccountInfo {
  handle: string
  display_name: string
  bio: string
  avatar: {
    bg_gradient: string
    initials: string
    icon: string
  }
  avatar_url?: string
  follower_tier: 'megastar' | 'major' | 'mid' | 'niche'
  content_tags: string[]
}

export interface FeedMeta {
  total: number
  returned: number
  offset: number
  limit: number
}

export interface CommunityFeedResponse {
  meta: FeedMeta
  posts: CommunityPost[]
}

export interface FeedFilters {
  accounts?: string
  tags?: string
  significance_min?: number
  date_from?: string
  date_to?: string
  limit?: number
  offset?: number
}
