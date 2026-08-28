import { useSyncExternalStore } from 'react'
import type { ConverterFunction } from 'opencc-js/core'

export type ChineseStyle = 'original' | 'simplified' | 'traditional'

const STORAGE_KEY = 'chineseStyle'

// ── Lazy converters ─────────────────────────────────────────

let s2tConverter: ConverterFunction | null = null
let t2sConverter: ConverterFunction | null = null
let s2tLoading: Promise<void> | null = null
let t2sLoading: Promise<void> | null = null

const subscribers = new Set<() => void>()
let changeVersion = 0

function notifyChange() {
  changeVersion += 1
  subscribers.forEach((subscriber) => subscriber())
  window.dispatchEvent(new Event('chinese-style-change'))
}

function subscribe(listener: () => void) {
  subscribers.add(listener)
  return () => subscribers.delete(listener)
}

function getSnapshot() {
  return changeVersion
}

async function loadSimplifiedConverter() {
  if (t2sConverter) return
  if (t2sLoading) return t2sLoading

  t2sLoading = import('opencc-js/t2cn').then(({ Converter }) => {
    t2sConverter = Converter({ from: 'twp', to: 'cn' })
    notifyChange()
  }).finally(() => {
    t2sLoading = null
  })

  return t2sLoading
}

async function loadTraditionalConverter() {
  if (s2tConverter) return
  if (s2tLoading) return s2tLoading

  s2tLoading = import('opencc-js/cn2t').then(({ Converter }) => {
    s2tConverter = Converter({ from: 'cn', to: 'twp' })
    notifyChange()
  }).finally(() => {
    s2tLoading = null
  })

  return s2tLoading
}

function ensureConverter(style: ChineseStyle) {
  if (style === 'simplified') void loadSimplifiedConverter()
  if (style === 'traditional') void loadTraditionalConverter()
}

// ── Public API ──────────────────────────────────────────────

export function getChineseStyle(): ChineseStyle {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'simplified' || stored === 'traditional') return stored
  return 'original'
}

export function setChineseStyle(style: ChineseStyle) {
  localStorage.setItem(STORAGE_KEY, style)
  notifyChange()
  ensureConverter(style)
}

export function displayName(name: string): string {
  if (!name) return name
  const style = getChineseStyle()
  if (style === 'original') return name

  if (style === 'simplified') {
    if (!t2sConverter) ensureConverter(style)
    return t2sConverter ? t2sConverter(name) : name
  }
  // traditional
  if (!s2tConverter) ensureConverter(style)
  return s2tConverter ? s2tConverter(name) : name
}

export function useChineseTextVersion(): number {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}

/**
 * A display-only name that also rerenders when the preference or lazy
 * converter changes. Keep raw values for URLs, keys, search identity and API
 * payloads; use this hook only at the presentation boundary.
 */
export function useDisplayName(name: string): string {
  useChineseTextVersion()
  return displayName(name)
}
