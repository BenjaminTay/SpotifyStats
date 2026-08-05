import { useState } from 'react'
import { ArrowDownToLine, CheckCircle2, Share2, Smartphone } from 'lucide-react'

import { usePwaInstall, type PwaInstallState } from '@/lib/pwa'

interface PwaInstallCardViewProps {
  state: PwaInstallState
  installing?: boolean
  onInstall: () => void
}

export function PwaInstallCardView({ state, installing = false, onInstall }: PwaInstallCardViewProps) {
  if (state === 'installed') {
    return (
      <section className="mobile-pwa-install-card mobile-pwa-install-card-active" aria-label="App 模式已启用">
        <span className="mobile-pwa-install-mark"><CheckCircle2 aria-hidden="true" /></span>
        <div><small>App mode / Active</small><strong>已从主屏幕独立运行</strong><p>导航、统计口径和数据仍与网页版完全一致。</p></div>
      </section>
    )
  }

  const isIos = state === 'ios'
  return (
    <section className="mobile-pwa-install-card" aria-label="安装 Spotify Stats">
      <div className="mobile-pwa-install-copy">
        <span className="mobile-pwa-install-mark"><Smartphone aria-hidden="true" /></span>
        <div>
          <small>App mode / PWA</small>
          <strong>{isIos ? '放到 iPhone 主屏幕' : '把 Spotify Stats 安装到手机'}</strong>
          <p>{isIos ? '使用 Safari 的分享菜单，不需要经过 App Store。' : '独立窗口启动，保留当前移动端导航与安全区。'}</p>
        </div>
      </div>
      {state === 'available' ? (
        <button type="button" className="mobile-pwa-install-action" onClick={onInstall} disabled={installing}>
          <ArrowDownToLine aria-hidden="true" />{installing ? '正在安装…' : '安装到手机'}
        </button>
      ) : (
        <div className="mobile-pwa-install-guide">
          {isIos ? <Share2 aria-hidden="true" /> : <ArrowDownToLine aria-hidden="true" />}
          <span>{isIos ? '点 Safari 分享，再选“添加到主屏幕”' : '在浏览器菜单中选择“安装应用”或“添加到主屏幕”'}</span>
        </div>
      )}
    </section>
  )
}

export function PwaInstallCard() {
  const { state, install } = usePwaInstall()
  const [installing, setInstalling] = useState(false)

  const handleInstall = async () => {
    setInstalling(true)
    try {
      await install()
    } finally {
      setInstalling(false)
    }
  }

  return <PwaInstallCardView state={state} installing={installing} onInstall={() => void handleInstall()} />
}
