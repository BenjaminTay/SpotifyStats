export type MastheadNavTo =
  | '/'
  | '/analysis'
  | '/yearly-review'
  | '/billboard'
  | '/community'
  | '/ai-insights'
  | '/account'
  | '/settings'

export type MobileTopBarMode = 'root' | 'section' | 'push'
export type MobileBottomNavItem = 'home' | 'analysis' | 'billboard' | 'community' | 'ai'
export type MobileSectionGroup = 'analysis' | 'billboard'

export type MastheadRouteContext = {
  activeNavTo: MastheadNavTo | null
  contextSegments: string[]
  title: string | null
  showMobileContext: boolean
  mobileTopBarMode: MobileTopBarMode
  mobileEyebrow: string | null
  mobileTitle: string
  mobileBottomNavItem: MobileBottomNavItem | null
  showMobileBottomNav: boolean
  mobileSectionGroup: MobileSectionGroup | null
  mobileFallbackTo: string
}

interface RouteContextInput {
  activeNavTo: MastheadNavTo | null
  contextSegments: string[]
  title?: string | null
  showMobileContext?: boolean
  mobileTopBarMode: MobileTopBarMode
  mobileEyebrow?: string | null
  mobileTitle: string
  mobileBottomNavItem?: MobileBottomNavItem | null
  showMobileBottomNav?: boolean
  mobileSectionGroup?: MobileSectionGroup | null
  mobileFallbackTo?: string
}

function routeContext(input: RouteContextInput): MastheadRouteContext {
  return {
    title: null,
    showMobileContext: false,
    mobileEyebrow: null,
    mobileBottomNavItem: null,
    showMobileBottomNav: false,
    mobileSectionGroup: null,
    mobileFallbackTo: '/',
    ...input,
  }
}

function decodePathSegment(value: string | undefined): string | null {
  if (!value) return null
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

function queryParam(search: string, key: string): string | null {
  const params = new URLSearchParams(search)
  return params.get(key)
}

function analysisContext(title: string, contextLabel = title): MastheadRouteContext {
  return routeContext({
    activeNavTo: '/analysis',
    contextSegments: ['播放分析', contextLabel],
    showMobileContext: title !== '播放统计',
    mobileTopBarMode: 'section',
    mobileEyebrow: '播放分析',
    mobileTitle: title,
    mobileBottomNavItem: 'analysis',
    showMobileBottomNav: true,
    mobileSectionGroup: 'analysis',
    mobileFallbackTo: '/analysis/stats',
  })
}

function billboardContext(title: string, contextLabel = title): MastheadRouteContext {
  return routeContext({
    activeNavTo: '/billboard',
    contextSegments: ['榜单', contextLabel],
    showMobileContext: title !== '周榜',
    mobileTopBarMode: 'section',
    mobileEyebrow: '个人 Billboard',
    mobileTitle: title,
    mobileBottomNavItem: 'billboard',
    showMobileBottomNav: true,
    mobileSectionGroup: 'billboard',
    mobileFallbackTo: '/billboard',
  })
}

export function getMastheadRouteContext(pathname: string, search = ''): MastheadRouteContext {
  if (pathname === '/') {
    return routeContext({
      activeNavTo: '/',
      contextSegments: ['首页'],
      mobileTopBarMode: 'root',
      mobileTitle: 'Spotify Stats',
      mobileBottomNavItem: 'home',
      showMobileBottomNav: true,
    })
  }

  if (pathname === '/analysis' || pathname === '/analysis/stats') return analysisContext('播放统计')
  if (pathname === '/analysis/charts') return analysisContext('播放排行')
  if (pathname === '/analysis/records') return analysisContext('播放记录')
  if (pathname.startsWith('/analysis/')) return analysisContext('播放分析', '分析')
  if (pathname === '/yearly-review') return analysisContext('年度总结')
  if (pathname === '/account') return analysisContext('账号中心')

  if (pathname === '/billboard') return billboardContext('周榜')
  if (pathname === '/billboard/number-ones') return billboardContext('每周榜首', '冠军')
  if (pathname === '/billboard/year-end') return billboardContext('年榜')
  if (pathname === '/billboard/all-time') return billboardContext('总榜')
  if (pathname === '/billboard/records') return billboardContext('榜单记录', '纪录')
  if (pathname === '/billboard/versus') return billboardContext('对决')
  if (pathname.startsWith('/billboard/')) return billboardContext('榜单')

  if (pathname === '/community') {
    return routeContext({
      activeNavTo: '/community',
      contextSegments: ['社区'],
      mobileTopBarMode: 'root',
      mobileEyebrow: 'Listening Club',
      mobileTitle: '社区',
      mobileBottomNavItem: 'community',
      showMobileBottomNav: true,
      mobileFallbackTo: '/community',
    })
  }

  if (pathname.startsWith('/community/post/')) {
    return routeContext({
      activeNavTo: '/community',
      contextSegments: ['社区', '帖子'],
      showMobileContext: true,
      mobileTopBarMode: 'push',
      mobileEyebrow: '社区',
      mobileTitle: '帖子',
      mobileFallbackTo: '/community',
    })
  }

  if (pathname.startsWith('/community/account/')) {
    const handle = decodePathSegment(pathname.split('/')[3])
    return routeContext({
      activeNavTo: '/community',
      contextSegments: ['社区', '账号'],
      title: handle ? `@${handle}` : null,
      showMobileContext: true,
      mobileTopBarMode: 'push',
      mobileEyebrow: '社区账号',
      mobileTitle: handle ? `@${handle}` : '账号',
      mobileFallbackTo: '/community',
    })
  }

  if (pathname === '/ai-insights') {
    const mode = queryParam(search, 'mode') === 'chat' ? 'chat' : 'reports'
    return routeContext({
      activeNavTo: '/ai-insights',
      contextSegments: ['AI 洞察'],
      mobileTopBarMode: 'section',
      mobileEyebrow: 'AI 洞察',
      mobileTitle: mode === 'chat' ? '问答' : '报告',
      mobileBottomNavItem: 'ai',
      showMobileBottomNav: true,
      mobileFallbackTo: '/ai-insights?mode=reports',
    })
  }

  if (pathname === '/settings') {
    return routeContext({
      activeNavTo: '/settings',
      contextSegments: ['设置'],
      mobileTopBarMode: 'push',
      mobileTitle: '设置',
      mobileFallbackTo: '/',
    })
  }

  if (pathname === '/music/search') {
    return routeContext({
      activeNavTo: null,
      contextSegments: ['音乐查找'],
      mobileTopBarMode: 'push',
      mobileTitle: '音乐查找',
      mobileFallbackTo: '/',
    })
  }

  if (pathname.startsWith('/music/artists/')) {
    const artistName = decodePathSegment(pathname.split('/')[3])
    return routeContext({
      activeNavTo: null,
      contextSegments: ['音乐详情', '艺人'],
      title: artistName,
      mobileTopBarMode: 'push',
      mobileEyebrow: '艺人详情',
      mobileTitle: artistName ?? '艺人详情',
      mobileFallbackTo: '/music/search',
    })
  }

  if (pathname.startsWith('/music/albums/')) {
    const albumName = decodePathSegment(pathname.split('/')[3])
    const artistName = queryParam(search, 'artist')
    return routeContext({
      activeNavTo: null,
      contextSegments: ['音乐详情', '专辑'],
      title: albumName && artistName ? `${albumName} · ${artistName}` : albumName,
      mobileTopBarMode: 'push',
      mobileEyebrow: '专辑详情',
      mobileTitle: albumName ?? '专辑详情',
      mobileFallbackTo: '/music/search',
    })
  }

  if (pathname.startsWith('/music/tracks/')) {
    return routeContext({
      activeNavTo: null,
      contextSegments: ['音乐详情', '单曲'],
      mobileTopBarMode: 'push',
      mobileEyebrow: '单曲详情',
      mobileTitle: '单曲详情',
      mobileFallbackTo: '/music/search',
    })
  }

  return routeContext({
    activeNavTo: null,
    contextSegments: ['页面'],
    mobileTopBarMode: 'push',
    mobileTitle: '页面未找到',
    mobileFallbackTo: '/',
  })
}
