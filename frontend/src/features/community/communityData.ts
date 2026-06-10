/** Community feed — constants, avatar configs, and utility functions. */

import type { AccountInfo } from '@/types/community'

export const ACCOUNT_CONFIG: Record<string, AccountInfo> = {
  '@chartdata': {
    handle: '@chartdata',
    display_name: 'chart data',
    bio: 'Billboard Hot 100 weekly updates. Charts, stats, and music news.',
    avatar: { bg_gradient: 'linear-gradient(135deg, #1DB954, #191414)', initials: 'CD', icon: '' },
    avatar_url: 'https://pbs.twimg.com/profile_images/1946594761130786816/_7KMjnaA_400x400.jpg',
    follower_tier: 'megastar',
    content_tags: ['weekly', 'no1', 'top10', 'debut'],
  },
  '@billboardcharts': {
    handle: '@billboardcharts',
    display_name: 'billboard charts',
    bio: 'Official Billboard chart summaries.',
    avatar: { bg_gradient: 'linear-gradient(135deg, #E13300, #B02800)', initials: 'BB', icon: '' },
    avatar_url: 'https://pbs.twimg.com/profile_images/1901646155009658880/p-_zyNrY_400x400.jpg',
    follower_tier: 'megastar',
    content_tags: ['weekly', 'top10', 'summary'],
  },
  '@talkofthecharts': {
    handle: '@talkofthecharts',
    display_name: 'Talk of the Charts',
    bio: 'Deep dives into chart statistics, historical analysis, and record tracking.',
    avatar: { bg_gradient: 'linear-gradient(135deg, #4A90D9, #2C5F8A)', initials: 'TC', icon: '' },
    avatar_url: 'https://pbs.twimg.com/profile_images/1700256819283656704/tcktqQD5_400x400.jpg',
    follower_tier: 'major',
    content_tags: ['stat', 'record', 'history', 'analysis'],
  },
  '@popcrave': {
    handle: '@popcrave',
    display_name: 'Pop Crave',
    bio: 'Pop music news, artist milestones, and chart achievements.',
    avatar: { bg_gradient: 'linear-gradient(135deg, #E91E63, #880E4F)', initials: 'PC', icon: '' },
    avatar_url: 'https://pbs.twimg.com/profile_images/1394266006395228162/qIjjvzl7_400x400.jpg',
    follower_tier: 'megastar',
    content_tags: ['milestone', 'news', 'artist'],
  },
  '@chartstats': {
    handle: '@chartstats',
    display_name: 'ChartStats',
    bio: 'Pure chart statistics. Numbers, rankings, and data analysis.',
    avatar: { bg_gradient: 'linear-gradient(135deg, #7C4DFF, #4A148C)', initials: 'CS', icon: '' },
    avatar_url: 'https://pbs.twimg.com/profile_images/1335168437220421632/VCHg78Nf_400x400.jpg',
    follower_tier: 'major',
    content_tags: ['stat', 'history', 'alltime', 'analysis'],
  },
  '@debutwatch': {
    handle: '@debutwatch',
    display_name: 'Debut Watch',
    bio: 'Tracking first-week entries and debut achievements on the Hot 100.',
    avatar: { bg_gradient: 'linear-gradient(135deg, #FF9800, #E65100)', initials: 'DW', icon: '' },
    avatar_url: 'https://pbs.twimg.com/profile_images/1268086791443230737/BRGz4AiW_400x400.jpg',
    follower_tier: 'mid',
    content_tags: ['debut', 'new_entry'],
  },
  '@recordwatch': {
    handle: '@recordwatch',
    display_name: 'Record Watch',
    bio: 'Monitoring chart records — close calls and broken records.',
    avatar: { bg_gradient: 'linear-gradient(135deg, #F44336, #B71C1C)', initials: 'RW', icon: '' },
    avatar_url: 'https://pbs.twimg.com/profile_images/1482519386829340681/68Il6Wnp_400x400.jpg',
    follower_tier: 'mid',
    content_tags: ['record', 'milestone', 'history'],
  },
  '@throwbackcharts': {
    handle: '@throwbackcharts',
    display_name: 'throwback charts',
    bio: 'On this week in Billboard history.',
    avatar: { bg_gradient: 'linear-gradient(135deg, #795548, #4E342E)', initials: 'TB', icon: '' },
    avatar_url: 'https://pbs.twimg.com/profile_images/1901646155009658880/p-_zyNrY_400x400.jpg',
    follower_tier: 'mid',
    content_tags: ['history', 'throwback', 'weekly'],
  },
  '@spotifystats': {
    handle: '@spotifystats',
    display_name: 'Spotify Stats',
    bio: 'Your personal listening data, analyzed and narrated.',
    avatar: { bg_gradient: 'linear-gradient(135deg, #1DB954, #0D7A3E)', initials: 'SS', icon: '' },
    avatar_url: 'https://pbs.twimg.com/profile_images/1793315484961591301/DiEXUJEV_400x400.jpg',
    follower_tier: 'major',
    content_tags: ['personal', 'weekly', 'monthly', 'yearly', 'milestone'],
  },
  '@collectionvault': {
    handle: '@collectionvault',
    display_name: 'Collection Vault',
    bio: 'Saved tracks analysis and library insights.',
    avatar: { bg_gradient: 'linear-gradient(135deg, #607D8B, #37474F)', initials: 'CV', icon: '' },
    avatar_url: '',
    follower_tier: 'niche',
    content_tags: ['collection', 'insight', 'personal'],
  },
}

export function getAccountInfo(handle: string): AccountInfo | undefined {
  return ACCOUNT_CONFIG[handle]
}

export function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

export function formatFollowerCount(tier: string): string {
  const counts: Record<string, string> = {
    megastar: '2.3M',
    major: '542K',
    mid: '128K',
    niche: '24K',
  }
  return counts[tier] ?? '0'
}

export function formatRelativeTime(isoStr: string): string {
  const now = new Date()
  const then = new Date(isoStr)
  const diffSec = Math.floor((now.getTime() - then.getTime()) / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHr = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHr / 24)

  if (diffSec < 60) return 'now'
  if (diffMin < 60) return `${diffMin}m`
  if (diffHr < 24) return `${diffHr}h`
  if (diffDay < 7) return `${diffDay}d`
  if (diffDay < 365) {
    return then.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }
  return then.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export function formatAbsoluteTime(isoStr: string): string {
  const then = new Date(isoStr)
  const parts: Intl.DateTimeFormatOptions = {
    hour: 'numeric',
    minute: '2-digit',
  }
  parts.month = 'short'
  parts.day = 'numeric'
  parts.year = 'numeric'
  return then.toLocaleString('en-US', parts).replace(',', ' ·')
}

export function buildEntityLink(entity: { type: string; id?: string | number; name: string }): string | null {
  switch (entity.type) {
    case 'track':
      if (entity.id) return `/music/tracks/${entity.id}`
      return null
    case 'artist':
      return `/music/artists/${encodeURIComponent(entity.name)}`
    case 'album':
      return `/music/albums/${encodeURIComponent(entity.name)}`
    default:
      return null
  }
}
