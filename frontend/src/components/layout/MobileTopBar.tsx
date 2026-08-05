import { useMemo, useRef, useState } from 'react'
import {
  ArrowLeft,
  ChevronDown,
  History,
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
import { navigateMobileBack } from '@/lib/mobile-navigation'
import { MobileBottomSheet } from '@/components/mobile'

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

  const searchState = useMemo(
    () => ({ returnTo: currentLocationTarget(location.pathname, location.search) }),
    [location.pathname, location.search],
  )

  const canShare = location.pathname.startsWith('/music/tracks/')
    || location.pathname.startsWith('/music/albums/')
    || location.pathname.startsWith('/music/artists/')
    || location.pathname.startsWith('/community/post/')
    || location.pathname.startsWith('/community/account/')

  const musicDetailManagement = useMemo(() => {
    const returnTo = currentLocationTarget(location.pathname, location.search)
    if (location.pathname.startsWith('/music/tracks/')) {
      const trackId = location.pathname.split('/')[3] ?? ''
      return {
        label: '管理曲目署名',
        to: `/settings?metadata=track-credits&track_id=${encodeURIComponent(trackId)}&return_to=${encodeURIComponent(returnTo)}#music-metadata-management`,
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
  }, [location.pathname, location.search])

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
          <button
            type="button"
            className="mobile-icon-button"
            onClick={() => setDetailActionsOpen(true)}
            aria-label="打开详情更多操作"
            aria-haspopup="dialog"
            aria-expanded={detailActionsOpen}
          >
            <MoreHorizontal className="h-[19px] w-[19px]" aria-hidden="true" />
          </button>
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
        <Link to="/settings" state={searchState} className="mobile-icon-button" aria-label="打开设置">
          <Settings className="h-[18px] w-[18px]" aria-hidden="true" />
        </Link>
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
                aria-label={`切换${context.mobileEyebrow ?? ''}栏目，当前${context.mobileTitle}`}
                aria-haspopup="dialog"
                aria-expanded={sectionOpen}
                onClick={() => setSectionOpen(true)}
              >
                <span className="min-w-0 text-left">
                  {context.mobileEyebrow && <span className="mobile-topbar-eyebrow">{context.mobileEyebrow}</span>}
                  <span className="mobile-topbar-title">{context.mobileTitle}</span>
                </span>
                <ChevronDown className="h-4 w-4 shrink-0 text-accent-foreground" aria-hidden="true" />
              </button>
            ) : context.mobileTopBarMode !== 'root' || location.pathname !== '/' ? (
              <div className="min-w-0">
                {context.mobileEyebrow && <span className="mobile-topbar-eyebrow">{context.mobileEyebrow}</span>}
                <span className="mobile-topbar-title truncate">{context.mobileTitle}</span>
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
          description="分享当前详情，或进入电脑端更适合处理的音乐源数据管理区。"
          dataSheet="music-detail-actions"
        >
          <div className="mobile-detail-action-list">
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
