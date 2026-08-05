import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import indexSource from '../../index.html?raw'
import manifestSource from '../../public/manifest.webmanifest?raw'
import serviceWorkerSource from '../../public/sw.js?raw'
import { PwaInstallCardView } from '@/features/mobile/settings/PwaInstallCard'

describe('PWA Phase A baseline', () => {
  it('declares an installable standalone manifest with maskable 192 and 512 icons', () => {
    const manifest = JSON.parse(manifestSource) as {
      display: string
      start_url: string
      scope: string
      icons: Array<{ sizes: string; purpose: string }>
    }
    expect(manifest.display).toBe('standalone')
    expect(manifest.start_url).toBe('/')
    expect(manifest.scope).toBe('/')
    expect(manifest.icons.map((icon) => icon.sizes)).toEqual(['192x192', '512x512'])
    expect(manifest.icons.every((icon) => icon.purpose.includes('maskable'))).toBe(true)
    expect(indexSource).toContain('rel="manifest"')
    expect(indexSource).toContain('rel="apple-touch-icon"')
    expect(indexSource).toContain('viewport-fit=cover')
    expect(indexSource).toContain('name="mobile-web-app-capable" content="yes"')
  })

  it('keeps personal API and cover data outside service-worker caching', () => {
    expect(serviceWorkerSource).toContain("url.pathname.startsWith('/api/')")
    expect(serviceWorkerSource).toContain("url.pathname.startsWith('/covers/')")
    expect(serviceWorkerSource).toContain("caches.match('/offline.html')")
    expect(serviceWorkerSource).not.toContain("cache.addAll(['/api")
  })

  it('offers a direct install action when the browser exposes an install prompt', async () => {
    const user = userEvent.setup()
    const onInstall = vi.fn()
    render(<PwaInstallCardView state="available" onInstall={onInstall} />)
    await user.click(screen.getByRole('button', { name: '安装到手机' }))
    expect(onInstall).toHaveBeenCalledOnce()
  })

  it('uses iOS-specific add-to-home-screen guidance and an installed state', () => {
    const { rerender } = render(<PwaInstallCardView state="ios" onInstall={vi.fn()} />)
    expect(screen.getByText(/点 Safari 分享/)).toBeInTheDocument()
    rerender(<PwaInstallCardView state="installed" onInstall={vi.fn()} />)
    expect(screen.getByLabelText('App 模式已启用')).toBeInTheDocument()
  })
})
