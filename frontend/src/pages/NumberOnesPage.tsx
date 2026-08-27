import { useSearchParams } from 'react-router-dom'

import { NumberOnesExperience } from '@/features/billboard/number-ones/NumberOnesExperience'
import { getDefaultMergeLevel, normalizeMergeLevel } from '@/lib/merge-level'

export function NumberOnesPage() {
  const [searchParams] = useSearchParams()
  const mergeLevel = normalizeMergeLevel(searchParams.get('merge_level') ?? getDefaultMergeLevel())
  return <NumberOnesExperience mergeLevel={mergeLevel} />
}
