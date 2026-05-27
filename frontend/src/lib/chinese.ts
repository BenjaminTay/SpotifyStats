import { useEffect, useState } from 'react'
import type { ConverterFunction } from 'opencc-js'

export type ChineseStyle = 'original' | 'simplified' | 'traditional'

const STORAGE_KEY = 'chineseStyle'

// ── Lazy converters ─────────────────────────────────────────

let s2tConverter: ConverterFunction | null = null
let t2sConverter: ConverterFunction | null = null
let convertersLoading: Promise<void> | null = null

function notifyChange() {
  window.dispatchEvent(new Event('chinese-style-change'))
}

async function loadConverters() {
  if (s2tConverter && t2sConverter) return
  if (convertersLoading) return convertersLoading

  convertersLoading = import('opencc-js').then(({ Converter }) => {
    s2tConverter = Converter({ from: 'cn', to: 'twp' })
    t2sConverter = Converter({ from: 'twp', to: 'cn' })
    notifyChange()
  }).finally(() => {
    convertersLoading = null
  })

  return convertersLoading
}

function ensureConverters() {
  void loadConverters()
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
  if (style !== 'original') ensureConverters()
}

export function displayName(name: string): string {
  if (!name) return name
  const style = getChineseStyle()
  if (style === 'original') return name

  if (style === 'simplified') {
    if (!t2sConverter) ensureConverters()
    return t2sConverter ? t2sConverter(name) : name
  }
  // traditional
  if (!s2tConverter) ensureConverters()
  return s2tConverter ? s2tConverter(name) : name
}

export function useChineseTextVersion(): number {
  const [version, setVersion] = useState(0)

  useEffect(() => {
    const handleChange = () => setVersion((v) => v + 1)
    window.addEventListener('chinese-style-change', handleChange)
    return () => window.removeEventListener('chinese-style-change', handleChange)
  }, [])

  return version
}

// Eager init if a preference is already saved
if (getChineseStyle() !== 'original') {
  ensureConverters()
}
