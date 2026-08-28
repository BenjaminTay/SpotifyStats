import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowLeft,
  ChevronDown,
  CornerUpLeft,
  History,
  House,
  MoreHorizontal,
  Search,
  Settings,
  Settings2,
  Share2,
  SlidersHorizontal,
} from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { getMastheadRouteContext } from './routeContext'
import { MobileSectionSwitcher } from './MobileSectionSwitcher'
import {
  isMusicDetailPath,
  mobileDetailOriginFromState,
  navigateMobileBack,
  type MobileDetailOrigin,
} from '@/lib/mobile-navigation'
import { MobileBottomSheet } from '@/components/mobile'
import { useRuntimeCapabilities } from '@/hooks/useRuntimeCapabilities'
import { displayName, useChineseTextVersion } from '@/lib/chinese'

let rememberedDetailOrigin: MobileDetailOrigin | null = null

function currentLocationTarget(pathname: string, search: string): string {
  return `${pathname}${search}`
}

function decodePathSegment(value: string): string {
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

export function MobileTopBar() {
  useChineseTextVersion()
  const { capabilities } = useRuntimeCapabilities()
  const location = useLocation()
  const navigate = useNavigate()
  const [sectionOpen, setSectionOpen] = useState(false)
  const [detailActionsOpen, setDetailActionsOpen] = useState(false)
  const [shared, setShared] = useState(false)
  const sectionTriggerRef = useRef<HTMLButtonElement>(null)
  const context = useMemo(
    () => getMastheadRouteContext(location.pathname, location.search),
    [location.pathname, location.search],
  )

  const returnState = useMemo(
    () => ({
      returnTo: currentLocationTarget(location.pathname, location.search),
    }),
    [location.pathname, location.search],
  )
  const searchState = useMemo(
    () => ({
      ...returnState,
      autofocusSearch: true,
    }),
    [returnState],
  )
  const isMusicDetail = isMusicDetailPath(location.pathname)
  const currentTarget = currentLocationTarget(location.pathname, location.search)
  const displayedMobileTitle = isMusicDetail ? displayName(context.mobileTitle) : context.mobileTitle
  const currentNonDetailOrigin = useMemo<MobileDetailOrigin>(
    () => ({ to: currentTarget, label: displayedMobileTitle }),
    [displayedMobileTitle, currentTarget],
  )
  const detailOrigin = mobileDetailOriginFromState(location.state) ?? rememberedDetailOrigin

  useEffect(() => {
    if (isMusicDetail) return
    rememberedDetailOrigin = currentNonDetailOrigin
  }, [currentNonDetailOrigin, isMusicDetail])

  useEffect(() => () => {
    rememberedDetailOrigin = null
  }, [])

  useEffect(() => {
    if (!isMusicDetail || mobileDetailOriginFromState(location.state) || !detailOrigin) return
    const currentState = location.state && typeof location.state === 'object'
      ? location.state as Record<string, unknown>
      : {}
    navigate(currentTarget, {
      replace: true,
      state: { ...currentState, detailOrigin },
    })
  }, [currentTarget, detailOrigin, isMusicDetail, location.state, navigate])

  const canShare = location.pathname.startsWith('/music/tracks/')
    || location.pathname.startsWith('/music/albums/')
    || location.pathname.startsWith('/music/artists/')
    || location.pathname.startsWith('/community/post/')
    || location.pathname.startsWith('/community/account/')

  const musicDetailManagement = useMemo(() => {
    if (!capabilities.editing || !capabilities.metadata_governance) return null
    const returnTo = currentLocationTarget(location.pathname, location.search)
    if (location.pathname.startsWith('/music/tracks/')) {
      const trackId = location.pathname.split('/')[3] ?? ''
      return {
        label: '管理曲目信息',
        to: `/settings?metadata=merge&merge_type=track&track_id=${encodeURIComponent(trackId)}&return_to=${encodeURIComponent(returnTo)}#music-metadata-management`,
      }
    }
    if (location.pathname.startsWith('/music/albums/')) {
      const albumName = decodePathSegment(location.pathname.split('/')[3] ?? '')
      const artistName = new URLSearchParams(location.search).get('artist') ?? ''
      return {
        label: '管理专辑版本',
        to: `/settings?metadata=album-projects&album_name=${encodeURIComponent(albumName)}&artist=${encodeURIComponent(artistName)}&return_to=${encodeURIComponent(returnTo)}#music-metadata-management`,
      }
    }
    if (location.pathname.startsWith('/music/artists/')) {
      const artistName = decodePathSegment(location.pathname.split('/')[3] ?? '')
      return {
        label: '管理艺人身份',
        to: `/settings?metadata=artist-identities&artist=${encodeURIComponent(artistName)}&return_to=${encodeURIComponent(returnTo)}#music-metadata-management`,
      }
    }
    return null
  }, [capabilities.editing, capabilities.metadata_governance, location.pathname, location.search])

  const handleShare = async () => {
    try {
      if (navigator.share) {
        await navigator.share({ title: document.title, url: window.location.href })
      } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(window.location.href)
        setShared(true)
        window.setTimeout(() => setShared(false), 1_800)
      }
    } catch {
      // 用户取消系统分享时保持静默。
    }
  }

  const rightActions = (() => {
    if (context.mobileTopBarMode === 'push') {
      if (!canShare) return null
      if (musicDetailManagement) {
        return (
          <div className="flex items-center gap-1">
            <Link to="/" className="mobile-icon-button" aria-label="返回首页">
              <House className="h-[18px] w-[18px]" aria-hidden="true" />
            </Link>
            <button
              type="button"
              className="mobile-icon-button mobile-detail-actions-button"
              onClick={() => setDetailActionsOpen(true)}
              aria-label="打开详情更多操作"
              aria-haspopup="dialog"
              aria-expanded={detailActionsOpen}
            >
              <MoreHorizontal className="h-[19px] w-[19px]" aria-hidden="true" />
            </button>
          </div>
        )
      }
      return (
        <button type="button" className="mobile-icon-button" onClick={() => void handleShare()} aria-label={shared ? '链接已复制' : '分享当前页面'}>
          <Share2 className="h-[18px] w-[18px]" aria-hidden="true" />
        </button>
      )
    }

    if (location.pathname === '/community') {
      return (
        <button
          type="button"
          className="mobile-icon-button"
          onClick={() => window.dispatchEvent(new CustomEvent('spotify-stats:open-community-explore'))}
          aria-label="打开社区趋势"
        >
          <SlidersHorizontal className="h-[18px] w-[18px]" aria-hidden="true" />
        </button>
      )
    }

    if (location.pathname === '/ai-insights' && new URLSearchParams(location.search).get('mode') === 'chat') {
      return (
        <button
          type="button"
          className="mobile-icon-button"
          onClick={() => window.dispatchEvent(new CustomEvent('spotify-stats:open-ai-history'))}
          aria-label="打开对话历史"
        >
          <History className="h-[18px] w-[18px]" aria-hidden="true" />
        </button>
      )
    }

    return (
      <div className="flex items-center gap-1">
        <Link to="/music/search" state={searchState} className="mobile-icon-button" aria-label="查找音乐">
          <Search className="h-[18px] w-[18px]" aria-hidden="true" />
        </Link>
        {capabilities.settings && (
          <Link to="/settings" state={returnState} className="mobile-icon-button" aria-label="打开设置">
            <Settings className="h-[18px] w-[18px]" aria-hidden="true" />
          </Link>
        )}
      </div>
    )
  })()

  return (
    <>
      <header className="mobile-top-bar" aria-label="移动顶部导航" data-mobile-shell="top-bar">
        <div className="mobile-top-bar-inner">
          {context.mobileTopBarMode === 'push' ? (
            <button
              type="button"
              className="mobile-icon-button -ml-2"
              aria-label="返回上一页"
              onClick={() => navigateMobileBack(navigate, location, context.mobileFallbackTo)}
            >
              <ArrowLeft className="h-5 w-5" aria-hidden="true" />
            </button>
          ) : context.mobileTopBarMode === 'root' && location.pathname === '/' ? (
            <Link to="/" className="mobile-wordmark" aria-label="Spotify Stats 首页">
              Spotify <em>Stats</em>
              {capabilities.surface === 'public-readonly' && (
                <span className="ml-1.5 rounded-full border border-accent-foreground/25 px-1.5 py-0.5 align-middle text-[8px] font-bold not-italic tracking-[0.6px] text-accent-foreground">
                  公开
                </span>
              )}
            </Link>
          ) : (
            <span aria-hidden="true" className="mobile-topbar-rule" />
          )}

          <div className="min-w-0 flex-1">
            {context.mobileSectionGroup ? (
              <button
                ref={sectionTriggerRef}
                type="button"
                className="mobile-section-trigger"
                aria-label={`切换${context.mobileEyebrow ?? ''}栏目，当前${displayedMobileTitle}`}
                aria-haspopup="dialog"
                aria-expanded={sectionOpen}
                onClick={() => setSectionOpen(true)}
              >
                <span className="min-w-0 text-left">
                  {context.mobileEyebrow && <span className="mobile-topbar-eyebrow">{context.mobileEyebrow}</span>}
                  <span className="mobile-topbar-title">{displayedMobileTitle}</span>
                </span>
                <ChevronDown className="h-4 w-4 shrink-0 text-accent-foreground" aria-hidden="true" />
              </button>
            ) : context.mobileTopBarMode !== 'root' || location.pathname !== '/' ? (
              <div className="min-w-0">
                {context.mobileEyebrow && <span className="mobile-topbar-eyebrow">{context.mobileEyebrow}</span>}
                <span className="mobile-topbar-title truncate">{displayedMobileTitle}</span>
              </div>
            ) : null}
          </div>

          <div className="flex min-w-11 items-center justify-end">{rightActions}</div>
        </div>

        {context.mobileSectionGroup && (
          <MobileSectionSwitcher
            group={context.mobileSectionGroup}
            open={sectionOpen}
            onOpenChange={setSectionOpen}
            triggerRef={sectionTriggerRef}
          />
        )}
      </header>

      {musicDetailManagement && (
        <MobileBottomSheet
          open={detailActionsOpen}
          onOpenChange={setDetailActionsOpen}
          title="详情操作"
          eyebrow="Music / More"
          description="快速退出详情层级，或继续分享、查找与管理音乐源数据。"
          dataSheet="music-detail-actions"
        >
          <div className="mobile-detail-action-list">
            {detailOrigin && (
              <Link
                to={detailOrigin.to}
                className="mobile-detail-action-row"
                onClick={() => setDetailActionsOpen(false)}
              >
                <CornerUpLeft aria-hidden="true" />
                <span><strong>返回{detailOrigin.label}</strong><small>跳过中间详情页，回到进入详情前的位置</small></span>
              </Link>
            )}
            <button
              type="button"
              className="mobile-detail-action-row"
              onClick={() => {
                setDetailActionsOpen(false)
                void handleShare()
              }}
            >
              <Share2 aria-hidden="true" />
              <span><strong>分享详情</strong><small>使用系统分享或复制当前链接</small></span>
            </button>
            <Link
              to={musicDetailManagement.to}
              className="mobile-detail-action-row"
              onClick={() => setDetailActionsOpen(false)}
            >
              <Settings2 aria-hidden="true" />
              <span><strong>{musicDetailManagement.label}</strong><small>打开 Settings 中对应的管理位置</small></span>
            </Link>
            <Link
              to="/music/search"
              state={searchState}
              className="mobile-detail-action-row"
              onClick={() => setDetailActionsOpen(false)}
            >
              <Search aria-hidden="true" />
              <span><strong>继续查找音乐</strong><small>搜索歌曲、专辑或艺人</small></span>
            </Link>
          </div>
        </MobileBottomSheet>
      )}
    </>
  )
}
