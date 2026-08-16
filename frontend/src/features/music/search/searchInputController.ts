import { useEffect, useMemo, useState } from 'react'

const PUNCTUATION_VARIANTS: Record<string, string> = {
  '‘': "'", '’': "'", '‚': "'", '‛': "'", '′': "'", '‵': "'", '❛': "'", '❜': "'",
  '“': '"', '”': '"', '„': '"', '‟': '"', '″': '"', '‶': '"', '❝': '"', '❞': '"',
  '〝': '"', '〞': '"', '〟': '"',
  '‐': '-', '‑': '-', '‒': '-', '–': '-', '—': '-', '―': '-', '⁃': '-', '−': '-', '﹘': '-', '﹣': '-',
  '、': ',', '。': '.', '｡': '.', '〜': '~', '…': '...', '・': '·', '･': '·',
}

const CJK_RE = /[\u1100-\u11ff\u2e80-\u2fff\u3040-\u30ff\u3130-\u318f\u31a0-\u31bf\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff\ua960-\ua97f\uac00-\ud7ff\uf900-\ufaff\uff65-\uff9f\u{20000}-\u{2fa1f}\u{30000}-\u{323af}]/u

export type SearchScriptCategory = 'empty' | 'cjk' | 'latin' | 'numeric' | 'mixed' | 'other'

export interface MusicSearchQueryAnalysis {
  normalizedQuery: string
  scriptCategory: SearchScriptCategory
  characterLength: number
  minimumLength: number
  eligible: boolean
}

export function normalizeMusicSearchFragment(value: string): string {
  const normalized = value.normalize('NFKC').replace(
    /[‘’‚‛′‵❛❜“”„‟″‶❝❞〝〞〟‐‑‒–—―⁃−﹘﹣、。｡〜…・･]/gu,
    (character) => PUNCTUATION_VARIANTS[character] ?? character,
  )
  // JavaScript has lowercase but no full Unicode casefold. Keep the stable
  // backend vector for sharp-s explicit so query keys match the final fact.
  return normalized.toLowerCase().replace(/ß/g, 'ss')
}

export function normalizeMusicSearchQuery(value: string): string {
  return normalizeMusicSearchFragment(value).trim().replace(/\s+/gu, ' ')
}

function classifyCharacter(character: string): Exclude<SearchScriptCategory, 'empty' | 'mixed'> | null {
  if (/\s|\p{P}/u.test(character)) return null
  if (CJK_RE.test(character)) return 'cjk'
  if (/\p{Nd}/u.test(character)) return 'numeric'
  if (/\p{Script=Latin}/u.test(character)) return 'latin'
  return 'other'
}

export function analyzeMusicSearchQuery(value: string): MusicSearchQueryAnalysis {
  const normalizedQuery = normalizeMusicSearchQuery(value)
  const categories = new Set<Exclude<SearchScriptCategory, 'empty' | 'mixed'>>()
  let characterLength = 0
  for (const character of normalizedQuery) {
    if (!/\s/u.test(character)) characterLength += 1
    const category = classifyCharacter(character)
    if (category) categories.add(category)
  }
  const scriptCategory: SearchScriptCategory = normalizedQuery.length === 0
    ? 'empty'
    : categories.size === 1
      ? [...categories][0]
      : categories.size > 1
        ? 'mixed'
        : 'other'
  const minimumLength = scriptCategory === 'cjk' ? 1 : 2
  return {
    normalizedQuery,
    scriptCategory,
    characterLength,
    minimumLength,
    eligible: normalizedQuery.length > 0 && characterLength >= minimumLength,
  }
}

export function useMusicSearchInputController(externalValue: string, debounceMs = 220) {
  const [draftState, setDraftState] = useState({ source: externalValue, value: externalValue })
  const [isComposing, setIsComposing] = useState(false)
  const draft = draftState.source === externalValue ? draftState.value : externalValue
  const [settledQuery, setSettledQuery] = useState(draft.trim())

  useEffect(() => {
    if (isComposing) return
    const timer = window.setTimeout(() => setSettledQuery(draft.trim()), debounceMs)
    return () => window.clearTimeout(timer)
  }, [debounceMs, draft, isComposing])

  const analysis = useMemo(() => analyzeMusicSearchQuery(settledQuery), [settledQuery])

  return {
    draft,
    setDraft: (value: string) => setDraftState({ source: externalValue, value }),
    settledQuery,
    normalizedQuery: analysis.normalizedQuery,
    canSearch: analysis.eligible && !isComposing,
    isComposing,
    onCompositionStart: () => setIsComposing(true),
    onCompositionEnd: (value: string) => {
      setDraftState({ source: externalValue, value })
      setIsComposing(false)
    },
  }
}
