import { describe, expect, it } from 'vitest'

import { getMastheadRouteContext } from '../components/layout/routeContext'

describe('masthead route context', () => {
  it('marks top-level pages without a mobile context strip', () => {
    expect(getMastheadRouteContext('/', '')).toEqual({
      activeNavTo: '/',
      contextSegments: ['总览'],
      title: null,
      showMobileContext: false,
    })
  })

  it('maps nested analysis routes to the analysis nav item', () => {
    expect(getMastheadRouteContext('/analysis/charts', '?entity=artist')).toEqual({
      activeNavTo: '/analysis',
      contextSegments: ['分析', '排行榜'],
      title: null,
      showMobileContext: true,
    })
  })

  it('maps nested billboard routes to the billboard nav item', () => {
    expect(getMastheadRouteContext('/billboard/records', '')).toEqual({
      activeNavTo: '/billboard',
      contextSegments: ['Billboard', '纪录'],
      title: null,
      showMobileContext: true,
    })
  })

  it('keeps music artist detail routes as detail context without a fake nav owner', () => {
    expect(getMastheadRouteContext('/music/artists/21%20Savage', '')).toEqual({
      activeNavTo: null,
      contextSegments: ['音乐详情', '艺人'],
      title: '21 Savage',
      showMobileContext: false,
    })
  })

  it('uses album artist query text when available', () => {
    expect(getMastheadRouteContext('/music/albums/Midnights', '?artist=Taylor%20Swift')).toEqual({
      activeNavTo: null,
      contextSegments: ['音乐详情', '专辑'],
      title: 'Midnights · Taylor Swift',
      showMobileContext: false,
    })
  })

  it('maps community detail routes to the community nav item', () => {
    expect(getMastheadRouteContext('/community/post/abc123', '')).toEqual({
      activeNavTo: '/community',
      contextSegments: ['社区', '帖子'],
      title: null,
      showMobileContext: true,
    })
  })
})
