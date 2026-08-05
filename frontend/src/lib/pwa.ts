import { useSyncExternalStore } from 'react'

export type PwaInstallState = 'available' | 'installed' | 'ios' | 'manual'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>
}

let initialized = false
let installPrompt: BeforeInstallPromptEvent | null = null
let installState: PwaInstallState = 'manual'
const listeners = new Set<() => void>()

function isStandalone(): boolean {
  return window.matchMedia('(display-mode: standalone)').matches
    || Boolean((navigator as Navigator & { standalone?: boolean }).standalone)
}

function isIos(): boolean {
  return /iPad|iPhone|iPod/.test(navigator.userAgent)
}

function deriveState(): PwaInstallState {
  if (isStandalone()) return 'installed'
  if (installPrompt) return 'available'
  if (isIos()) return 'ios'
  return 'manual'
}

function publish(next?: PwaInstallState) {
  installState = next ?? deriveState()
  listeners.forEach((listener) => listener())
}

export function initializePwaRuntime() {
  if (initialized) return
  initialized = true
  installState = deriveState()

  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault()
    installPrompt = event as BeforeInstallPromptEvent
    publish('available')
  })

  window.addEventListener('appinstalled', () => {
    installPrompt = null
    publish('installed')
  })

  if ('serviceWorker' in navigator && import.meta.env.PROD) {
    window.addEventListener('load', () => {
      void navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => undefined)
    }, { once: true })
  }
}

export async function requestPwaInstall(): Promise<'accepted' | 'dismissed' | 'unavailable'> {
  if (!installPrompt) return 'unavailable'
  const prompt = installPrompt
  await prompt.prompt()
  const { outcome } = await prompt.userChoice
  installPrompt = null
  publish(outcome === 'accepted' ? 'installed' : undefined)
  return outcome
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function getSnapshot() {
  return installState
}

export function usePwaInstall() {
  const state = useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
  return { state, install: requestPwaInstall }
}
