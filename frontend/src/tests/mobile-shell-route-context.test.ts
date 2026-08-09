import { describe, expect, it } from 'vitest'

import { getMastheadRouteContext } from '@/components/layout/routeContext'
import { viewportModeForWidth } from '@/hooks/useViewportMode'
import {
  getMobileBackDecision,
  isSafeInternalReturnTo,
  mobileDetailOriginFromState,
} from '@/lib/mobile-navigation'

describe('mobile shell route context', () => {
  it.each([
    ['/', 'root', 'home', true, null, 'Spotify Stats'],
    ['/analysis/stats', 'section', 'analysis', true, 'analysis', '播放统计'],
    ['/analysis/charts', 'section', 'analysis', true, 'analysis', '播放排行'],
    ['/yearly-review', 'section', 'analysis', true, 'analysis', '年度总结'],
    ['/analysis/records', 'section', 'analysis', true, 'analysis', '播放记录'],
    ['/account', 'section', 'analysis', true, 'analysis', '账号中心'],
    ['/billboard', 'section', 'billboard', true, 'billboard', '周榜'],
    ['/billboard/number-ones', 'section', 'billboard', true, 'billboard', '每周榜首'],
    ['/billboard/year-end', 'section', 'billboard', true, 'billboard', '年榜'],
    ['/billboard/all-time', 'section', 'billboard', true, 'billboard', '总榜'],
    ['/billboard/records', 'section', 'billboard', true, 'billboard', '榜单记录'],
    ['/billboard/versus', 'section', 'billboard', true, 'billboard', '对决'],
    ['/community', 'root', 'community', true, null, '社区'],
    ['/community/post/post-1', 'push', null, false, null, '帖子'],
    ['/community/account/ben', 'push', null, false, null, '@ben'],
    ['/ai-insights?mode=reports', 'section', 'ai', true, null, '报告'],
    ['/ai-insights?mode=chat', 'section', 'ai', true, null, '问答'],
    ['/music/search', 'push', null, false, null, '音乐查找'],
    ['/music/tracks/track-1', 'push', null, false, null, '单曲详情'],
    ['/music/albums/Midnights?artist=Taylor%20Swift', 'push', null, false, null, 'Midnights'],
    ['/music/artists/Taylor%20Swift', 'push', null, false, null, 'Taylor Swift'],
    ['/settings', 'push', null, false, null, '设置'],
    ['/missing', 'push', null, false, null, '页面未找到'],
  ])('%s maps to the frozen mobile shell state', (url, mode, owner, showBottom, section, title) => {
    const parsed = new URL(url, 'https://spotify-stats.local')
    const context = getMastheadRouteContext(parsed.pathname, parsed.search)

    expect(context.mobileTopBarMode).toBe(mode)
    expect(context.mobileBottomNavItem).toBe(owner)
    expect(context.showMobileBottomNav).toBe(showBottom)
    expect(context.mobileSectionGroup).toBe(section)
    expect(context.mobileTitle).toBe(title)
  })

  it('freezes the 767/768 and 1023/1024 device boundaries', () => {
    expect(viewportModeForWidth(360)).toBe('phone')
    expect(viewportModeForWidth(767)).toBe('phone')
    expect(viewportModeForWidth(768)).toBe('compact')
    expect(viewportModeForWidth(1023)).toBe('compact')
    expect(viewportModeForWidth(1024)).toBe('desktop')
  })
})

describe('mobile back navigation', () => {
  it('uses history before return_to and fallback', () => {
    expect(getMobileBackDecision({
      historyIndex: 2,
      search: '?return_to=%2Fbillboard',
      fallback: '/',
    })).toEqual({ type: 'history' })
  })

  it('uses a safe query or state return target when history is unavailable', () => {
    expect(getMobileBackDecision({
      historyIndex: 0,
      search: '?return_to=%2Fanalysis%2Fcharts%3Fentity%3Dartist',
      fallback: '/',
    })).toEqual({ type: 'target', to: '/analysis/charts?entity=artist' })

    expect(getMobileBackDecision({
      historyIndex: 0,
      state: { returnTo: '/community?feed=all' },
      fallback: '/',
    })).toEqual({ type: 'target', to: '/community?feed=all' })
  })

  it('rejects external and protocol-relative return targets', () => {
    expect(isSafeInternalReturnTo('https://example.com')).toBe(false)
    expect(isSafeInternalReturnTo('//example.com')).toBe(false)
    expect(getMobileBackDecision({
      historyIndex: 0,
      search: '?return_to=https%3A%2F%2Fexample.com',
      fallback: '/music/search',
    })).toEqual({ type: 'target', to: '/music/search' })
  })

  it('accepts only safe non-detail origins for a fast detail exit', () => {
    expect(mobileDetailOriginFromState({
      detailOrigin: { to: '/billboard?week=2025-10-03', label: '周榜' },
    })).toEqual({ to: '/billboard?week=2025-10-03', label: '周榜' })
    expect(mobileDetailOriginFromState({
      detailOrigin: { to: '/music/artists/Taylor%20Swift', label: '艺人详情' },
    })).toBeNull()
    expect(mobileDetailOriginFromState({
      detailOrigin: { to: 'https://example.com', label: '外部页面' },
    })).toBeNull()
  })
})
