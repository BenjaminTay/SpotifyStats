export type MastheadNavTo =
  | '/'
  | '/analysis'
  | '/yearly-review'
  | '/billboard'
  | '/community'
  | '/ai-insights'
  | '/account'
  | '/settings'

export type MastheadRouteContext = {
  activeNavTo: MastheadNavTo | null
  contextSegments: string[]
  title: string | null
  showMobileContext: boolean
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

export function getMastheadRouteContext(pathname: string, search = ''): MastheadRouteContext {
  if (pathname === '/') {
    return {
      activeNavTo: '/',
      contextSegments: ['首页'],
      title: null,
      showMobileContext: false,
    }
  }

  if (pathname === '/analysis') {
    return {
      activeNavTo: '/analysis',
      contextSegments: ['播放分析'],
      title: null,
      showMobileContext: false,
    }
  }

  if (pathname.startsWith('/analysis/')) {
    const segment = pathname.split('/')[2]
    const labels: Record<string, string> = {
      stats: '播放统计',
      charts: '播放排行',
      records: '记录',
    }
    return {
      activeNavTo: '/analysis',
      contextSegments: ['播放分析', labels[segment] ?? '分析'],
      title: null,
      showMobileContext: true,
    }
  }

  if (pathname === '/billboard') {
    return {
      activeNavTo: '/billboard',
      contextSegments: ['榜单'],
      title: null,
      showMobileContext: false,
    }
  }

  if (pathname.startsWith('/billboard/')) {
    const segment = pathname.split('/')[2]
    const labels: Record<string, string> = {
      'number-ones': '冠军',
      'all-time': '总榜',
      'year-end': '年榜',
      records: '纪录',
      versus: '对决',
    }
    return {
      activeNavTo: '/billboard',
      contextSegments: ['榜单', labels[segment] ?? '榜单'],
      title: null,
      showMobileContext: true,
    }
  }

  if (pathname === '/yearly-review') {
    return {
      activeNavTo: '/analysis',
      contextSegments: ['播放分析', '年度总结'],
      title: null,
      showMobileContext: true,
    }
  }

  if (pathname === '/community') {
    return {
      activeNavTo: '/community',
      contextSegments: ['社区'],
      title: null,
      showMobileContext: false,
    }
  }

  if (pathname.startsWith('/community/post/')) {
    return {
      activeNavTo: '/community',
      contextSegments: ['社区', '帖子'],
      title: null,
      showMobileContext: true,
    }
  }

  if (pathname.startsWith('/community/account/')) {
    const handle = decodePathSegment(pathname.split('/')[3])
    return {
      activeNavTo: '/community',
      contextSegments: ['社区', '账号'],
      title: handle ? `@${handle}` : null,
      showMobileContext: true,
    }
  }

  if (pathname === '/ai-insights') {
    return {
      activeNavTo: '/ai-insights',
      contextSegments: ['AI 洞察'],
      title: null,
      showMobileContext: false,
    }
  }

  if (pathname === '/account') {
    return {
      activeNavTo: '/analysis',
      contextSegments: ['播放分析', '账号中心'],
      title: null,
      showMobileContext: true,
    }
  }

  if (pathname === '/settings') {
    return {
      activeNavTo: '/settings',
      contextSegments: ['设置'],
      title: null,
      showMobileContext: false,
    }
  }

  if (pathname.startsWith('/music/artists/')) {
    return {
      activeNavTo: null,
      contextSegments: ['音乐详情', '艺人'],
      title: decodePathSegment(pathname.split('/')[3]),
      showMobileContext: false,
    }
  }

  if (pathname.startsWith('/music/albums/')) {
    const albumName = decodePathSegment(pathname.split('/')[3])
    const artistName = queryParam(search, 'artist')
    return {
      activeNavTo: null,
      contextSegments: ['音乐详情', '专辑'],
      title: albumName && artistName ? `${albumName} · ${artistName}` : albumName,
      showMobileContext: false,
    }
  }

  if (pathname.startsWith('/music/tracks/')) {
    const trackId = decodePathSegment(pathname.split('/')[3])
    return {
      activeNavTo: null,
      contextSegments: ['音乐详情', '单曲'],
      title: trackId ? `Track ${trackId}` : null,
      showMobileContext: false,
    }
  }

  return {
    activeNavTo: null,
    contextSegments: ['页面'],
    title: null,
    showMobileContext: false,
  }
}
