import { useSearchParams } from 'react-router-dom'

import { NumberOnesExperience } from '@/features/billboard/number-ones/NumberOnesExperience'
import { getDefaultMergeLevel } from '@/lib/merge-level'

export function NumberOnesPage() {
  const [searchParams] = useSearchParams()
  const mergeLevel = Number(searchParams.get('merge_level') ?? getDefaultMergeLevel())
  return <NumberOnesExperience mergeLevel={mergeLevel} />
}
