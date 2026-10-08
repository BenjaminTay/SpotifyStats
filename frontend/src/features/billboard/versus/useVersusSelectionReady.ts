import { useEffect, useState } from 'react'
import type { EntityListItem } from '@/types/billboard'
import type { VersusKind } from './versusData'
import { personalBatchBody } from './useVersusPersonal'

export const VERSUS_SELECTION_SETTLE_MS = 220

/** Let rapid third/fourth additions settle before sending bounded reads. */
export function useVersusSelectionReady(kind: VersusKind, queue: EntityListItem[], filters: Record<string, string | number | boolean>) {
  const context = JSON.stringify({ kind, body: personalBatchBody(kind, queue), filters: Object.keys(filters).sort().map((key) => [key, filters[key]]) })
  const [settledContext, setSettledContext] = useState(context)
  const immediate = queue.length <= 2
  useEffect(() => {
    if (context === settledContext) return
    const timer = setTimeout(() => setSettledContext(context), immediate ? 0 : VERSUS_SELECTION_SETTLE_MS)
    return () => clearTimeout(timer)
  }, [context, settledContext, immediate])
  return immediate || context === settledContext
}
