import { describe, expect, it } from 'vitest'

import { getMastheadRouteContext } from '../components/layout/routeContext'

describe('masthead route context', () => {
  it('marks top-level pages without a mobile context strip', () => {
    expect(getMastheadRouteContext('/', '')).toMatchObject({
      activeNavTo: '/',
      contextSegments: ['首页'],
      title: null,
      showMobileContext: false,
    })
  })

  it('maps nested analysis routes to the analysis nav item', () => {
    expect(getMastheadRouteContext('/analysis/charts', '?entity=artist')).toMatchObject({
      activeNavTo: '/analysis',
      contextSegments: ['播放分析', '播放排行'],
      title: null,
      showMobileContext: true,
    })
  })

  it('keeps yearly review and account under the playback analysis nav owner', () => {
    expect(getMastheadRouteContext('/yearly-review', '')).toMatchObject({
      activeNavTo: '/analysis',
      contextSegments: ['播放分析', '年度总结'],
      title: null,
      showMobileContext: true,
    })

    expect(getMastheadRouteContext('/account', '')).toMatchObject({
      activeNavTo: '/analysis',
      contextSegments: ['播放分析', '账号中心'],
      title: null,
      showMobileContext: true,
    })
  })

  it('maps nested billboard routes to the billboard nav item', () => {
    expect(getMastheadRouteContext('/billboard/records', '')).toMatchObject({
      activeNavTo: '/billboard',
      contextSegments: ['榜单', '纪录'],
      title: null,
      showMobileContext: true,
    })
  })

  it('keeps music artist detail routes as detail context without a fake nav owner', () => {
    expect(getMastheadRouteContext('/music/artists/21%20Savage', '')).toMatchObject({
      activeNavTo: null,
      contextSegments: ['音乐详情', '艺人'],
      title: '21 Savage',
      showMobileContext: false,
    })
  })

  it('uses album artist query text when available', () => {
    expect(getMastheadRouteContext('/music/albums/Midnights', '?artist=Taylor%20Swift')).toMatchObject({
      activeNavTo: null,
      contextSegments: ['音乐详情', '专辑'],
      title: 'Midnights · Taylor Swift',
      showMobileContext: false,
    })
  })

  it('keeps music search as a utility route without a primary nav owner', () => {
    expect(getMastheadRouteContext('/music/search', '?q=love')).toMatchObject({
      activeNavTo: null,
      contextSegments: ['音乐查找'],
      title: null,
      showMobileContext: false,
    })
  })

  it('maps community detail routes to the community nav item', () => {
    expect(getMastheadRouteContext('/community/post/abc123', '')).toMatchObject({
      activeNavTo: '/community',
      contextSegments: ['社区', '帖子'],
      title: null,
      showMobileContext: true,
    })
  })
})
