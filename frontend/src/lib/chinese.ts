import { Converter, type ConverterFunction } from 'opencc-js'

export type ChineseStyle = 'original' | 'simplified' | 'traditional'

const STORAGE_KEY = 'chineseStyle'

// ── Lazy converters ─────────────────────────────────────────

let s2tConverter: ConverterFunction | null = null
let t2sConverter: ConverterFunction | null = null

function ensureConverters() {
  if (!s2tConverter) s2tConverter = Converter({ from: 'cn', to: 'twp' })
  if (!t2sConverter) t2sConverter = Converter({ from: 'twp', to: 'cn' })
}

// ── Public API ──────────────────────────────────────────────

export function getChineseStyle(): ChineseStyle {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === 'simplified' || stored === 'traditional') return stored
  return 'original'
}

export function setChineseStyle(style: ChineseStyle) {
  localStorage.setItem(STORAGE_KEY, style)
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

// Eager init if a preference is already saved
if (getChineseStyle() !== 'original') {
  ensureConverters()
}
