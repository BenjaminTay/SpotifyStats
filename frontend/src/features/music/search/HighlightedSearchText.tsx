import { Fragment, type ReactNode } from 'react'

import {
  normalizeMusicSearchFragment,
  normalizeMusicSearchQuery,
} from './searchInputController'

type SourceRange = {
  start: number
  end: number
}

type NormalizedTextMap = {
  text: string
  sourceRanges: SourceRange[]
}

type SearchTextSegment = {
  segment: string
  index: number
}

let cachedSegmenterConstructor: unknown
let cachedSegmenter: Intl.Segmenter | null = null

function runtimeGraphemeSegmenter(): Intl.Segmenter | null {
  const constructor = Intl.Segmenter
  if (constructor === cachedSegmenterConstructor) return cachedSegmenter
  cachedSegmenterConstructor = constructor
  cachedSegmenter = null
  if (typeof constructor !== 'function') return null
  try {
    cachedSegmenter = new constructor('und', { granularity: 'grapheme' })
  } catch {
    // Older Firefox/WebKit runtimes may expose a non-constructable placeholder.
  }
  return cachedSegmenter
}

function codePointSafeSegments(value: string): SearchTextSegment[] {
  const segments: SearchTextSegment[] = []
  let sourceIndex = 0
  for (const character of Array.from(value)) {
    const previous = segments[segments.length - 1]
    const codePoint = character.codePointAt(0) ?? 0
    const isEmojiModifier = codePoint >= 0x1f3fb && codePoint <= 0x1f3ff
    const isVariationSelector = codePoint === 0xfe0e || codePoint === 0xfe0f
    const joinsPrevious = Boolean(previous) && (
      /\p{Mark}/u.test(character)
      || isEmojiModifier
      || isVariationSelector
      || character === '\u200d'
      || previous.segment.endsWith('\u200d')
    )
    if (joinsPrevious) {
      previous.segment += character
    } else {
      segments.push({ segment: character, index: sourceIndex })
    }
    sourceIndex += character.length
  }
  return segments
}

function segmentSearchText(value: string): Iterable<SearchTextSegment> {
  return runtimeGraphemeSegmenter()?.segment(value) ?? codePointSafeSegments(value)
}

function appendNormalizedCharacter(
  current: NormalizedTextMap,
  character: string,
  sourceRange: SourceRange,
) {
  if (/\s/u.test(character)) {
    if (!current.text || current.text.endsWith(' ')) {
      if (current.text.endsWith(' ')) {
        current.sourceRanges[current.sourceRanges.length - 1] = {
          ...current.sourceRanges[current.sourceRanges.length - 1],
          end: sourceRange.end,
        }
      }
      return
    }
    current.text += ' '
    current.sourceRanges.push(sourceRange)
    return
  }

  current.text += character
  for (let offset = 0; offset < character.length; offset += 1) {
    current.sourceRanges.push(sourceRange)
  }
}

function buildNormalizedSearchTextMap(value: string): NormalizedTextMap {
  const result: NormalizedTextMap = { text: '', sourceRanges: [] }
  for (const segment of segmentSearchText(value)) {
    const sourceRange = {
      start: segment.index,
      end: segment.index + segment.segment.length,
    }
    const normalized = normalizeMusicSearchFragment(segment.segment)
    for (const character of normalized) {
      appendNormalizedCharacter(result, character, sourceRange)
    }
  }

  if (result.text.endsWith(' ')) {
    result.text = result.text.slice(0, -1)
    result.sourceRanges.pop()
  }
  return result
}

function findOriginalSearchMatchRanges(text: string, query: string): SourceRange[] {
  const needle = normalizeMusicSearchQuery(query)
  if (!needle) return []
  const normalized = buildNormalizedSearchTextMap(text)
  const ranges: SourceRange[] = []
  let searchFrom = 0

  while (searchFrom <= normalized.text.length - needle.length) {
    const matchIndex = normalized.text.indexOf(needle, searchFrom)
    if (matchIndex < 0) break
    const first = normalized.sourceRanges[matchIndex]
    const last = normalized.sourceRanges[matchIndex + needle.length - 1]
    if (first && last) {
      const previous = ranges[ranges.length - 1]
      if (previous && first.start <= previous.end) {
        previous.end = Math.max(previous.end, last.end)
      } else {
        ranges.push({ start: first.start, end: last.end })
      }
    }
    searchFrom = matchIndex + Math.max(needle.length, 1)
  }

  return ranges
}

export function HighlightedSearchText({ text, query }: { text: string; query: string }) {
  const ranges = findOriginalSearchMatchRanges(text, query)
  if (ranges.length === 0) return <>{text}</>

  const nodes: ReactNode[] = []
  let cursor = 0
  ranges.forEach((range, index) => {
    if (range.start > cursor) nodes.push(text.slice(cursor, range.start))
    nodes.push(
      <mark
        key={`${range.start}:${range.end}:${index}`}
        className="rounded-sm bg-accent-foreground/15 text-inherit"
      >
        {text.slice(range.start, range.end)}
      </mark>,
    )
    cursor = range.end
  })
  if (cursor < text.length) nodes.push(text.slice(cursor))

  return <Fragment>{nodes}</Fragment>
}
